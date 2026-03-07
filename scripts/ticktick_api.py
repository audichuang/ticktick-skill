#!/usr/bin/env python3
"""
ticktick_api.py — TickTick 統一 API 封裝

使用 TickTick 內部 API（帳密 session 認證），覆蓋所有操作：
  - Tasks: CRUD + 完成 + 搜尋 + 已完成歷史
  - Projects: CRUD
  - Tags: CRUD
  - Habits: CRUD + 打卡
  - Attachments: 上傳
  - Sync: 全量同步

環境變數（由 Doppler 注入）:
  TICKTICK_USERNAME — 登入帳號（email）
  TICKTICK_PASSWORD — 登入密碼

用法:
  doppler run -p ticktick -c dev -- python3 ticktick_cli.py <command>
"""

import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.request
import urllib.error
import urllib.parse


# =============================================================================
# 共用工具
# =============================================================================

PRIORITY_MAP = {"none": 0, "low": 1, "medium": 3, "high": 5}
PRIORITY_REVERSE = {0: "none", 1: "low", 3: "medium", 5: "high"}


def _json_output(data):
    """統一 JSON 輸出"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _error_exit(msg):
    """錯誤退出"""
    print(json.dumps({"success": False, "error": msg}), file=sys.stderr)
    sys.exit(1)


# =============================================================================
# TickTick API — 統一封裝
# =============================================================================

class TickTickAPI:
    """TickTick API 封裝（帳密 session 認證）

    使用完整的瀏覽器指紋偽裝，模擬真實的 TickTick Web 客戶端請求。
    支援所有操作：Tasks, Projects, Tags, Habits, Attachments, Sync。
    """

    BASE_URL = "https://api.ticktick.com/api/v2"
    ORIGIN = "https://ticktick.com"

    # 模擬真實的 macOS Chrome 瀏覽器
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # Sync 快取 TTL（秒）
    SYNC_CACHE_TTL = 30

    def __init__(self, username: str, password: str):
        if not username or not password:
            _error_exit("TICKTICK_USERNAME 或 TICKTICK_PASSWORD 未設定")
        self.session_token = None
        self.csrf_token = None
        self.inbox_id = None
        # 生成持久的裝置 ID（同一個 client 實例保持同一裝置身份）
        self._device_id = "65a0" + secrets.token_hex(10)
        # Sync 快取
        self._sync_cache = None
        self._sync_cache_time = 0
        self._login(username, password)

    # ── 內部工具 ──────────────────────────────────────────────────────────

    @property
    def x_device(self) -> str:
        """生成 x-device header（模擬 TickTick Web 客戶端的裝置資訊）"""
        return json.dumps({
            "platform": "web",
            "os": "OS X",
            "device": "Chrome 131.0.0.0",
            "name": "",
            "version": 6072,
            "id": self._device_id,
            "channel": "website",
            "campaign": "",
            "websocket": "",
        })

    def _headers(self, extra: dict = None) -> dict:
        """構建完整的瀏覽器指紋 headers"""
        h = {
            # 核心認證 headers
            "User-Agent": self.USER_AGENT,
            "x-device": self.x_device,
            "Content-Type": "application/json",
            # 瀏覽器指紋 headers
            "Origin": self.ORIGIN,
            "Referer": f"{self.ORIGIN}/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "identity",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.session_token:
            h["Cookie"] = f"t={self.session_token}"
        if extra:
            h.update(extra)
        return h

    def _request(self, method: str, path: str, data=None,
                 params: dict = None) -> dict | list | str:
        """發送 API 請求"""
        url = self.BASE_URL + path
        if params:
            qs = urllib.parse.urlencode(params)
            url = f"{url}?{qs}"

        if data is not None:
            body = json.dumps(data).encode("utf-8")
        else:
            body = None
        req = urllib.request.Request(url, data=body, method=method,
                                    headers=self._headers())

        try:
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode("utf-8")
                if not text:
                    return {}
                return json.loads(text)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            _error_exit(f"API 錯誤 HTTP {e.code}: {body_text}")

    def _invalidate_cache(self):
        """清除 sync 快取（修改操作後呼叫）"""
        self._sync_cache = None
        self._sync_cache_time = 0

    # ── 認證 ──────────────────────────────────────────────────────────────

    def _login(self, username: str, password: str):
        """帳密登入取得 session token（嘗試多個端點）"""
        payload = json.dumps({"username": username, "password": password}).encode()
        params = urllib.parse.urlencode({"wc": "true", "remember": "true"})

        # TickTick 有兩個登入端點，依版本不同
        endpoints = ["/user/signon", "/user/signin"]
        last_error = None

        for endpoint in endpoints:
            url = f"{self.BASE_URL}{endpoint}?{params}"
            req = urllib.request.Request(url, data=payload, method="POST",
                                        headers=self._headers())
            try:
                with urllib.request.urlopen(req) as resp:
                    # 從 Set-Cookie 擷取 _csrf_token
                    for header in resp.headers.get_all("Set-Cookie") or []:
                        if "_csrf_token=" in header:
                            self.csrf_token = header.split("_csrf_token=")[1].split(";")[0]
                    result = json.loads(resp.read().decode("utf-8"))
                    self.session_token = result.get("token")
                    self.inbox_id = result.get("inboxId", "")
                    if self.session_token:
                        return  # 登入成功
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
                continue  # 嘗試下一個端點

        _error_exit(f"登入失敗（已嘗試所有端點）: {last_error}")

    # ── 全量同步（帶快取）────────────────────────────────────────────────

    def sync(self, force: bool = False) -> dict:
        """一次取得帳號全部資料（tasks, projects, tags, folders）

        帶有 TTL 快取，避免短時間內重複請求。
        """
        now = time.time()
        if (not force and self._sync_cache is not None
                and now - self._sync_cache_time < self.SYNC_CACHE_TTL):
            return self._sync_cache
        data = self._request("GET", "/batch/check/0")
        self._sync_cache = data
        self._sync_cache_time = now
        return data

    # ── Task Operations ──────────────────────────────────────────────────

    def get_task(self, project_id: str, task_id: str) -> dict:
        """取得單一任務（從 sync 快取過濾）"""
        data = self.sync()
        tasks = data.get("syncTaskBean", {}).get("update", [])
        for t in tasks:
            if t.get("id") == task_id:
                return t
        _error_exit(f"找不到任務 {task_id}")

    def list_tasks(self, project_id: str = None) -> list:
        """列出任務（指定專案或全部）"""
        data = self.sync()
        tasks = data.get("syncTaskBean", {}).get("update", [])
        if project_id:
            tasks = [t for t in tasks if t.get("projectId") == project_id]
        return tasks

    def create_task(self, task_data: dict) -> dict:
        """建立任務"""
        result = self._request("POST", "/batch/task", {"add": [task_data]})
        self._invalidate_cache()
        # 回傳建立的任務（從 id2etag 取得確認）
        if isinstance(result, dict):
            result["_input"] = task_data
        return result

    def update_task(self, task_data: dict) -> dict:
        """更新任務（GET-merge-POST，保留既有欄位）"""
        task_id = task_data.get("id")
        project_id = task_data.get("projectId")
        if not task_id or not project_id:
            _error_exit("update_task 需要 id 和 projectId")
        # 先取完整 task data（含 attachments 等），merge 更新欄位
        existing = self.get_task(project_id, task_id)
        existing.update(task_data)
        result = self._request("POST", "/batch/task", {"update": [existing]})
        self._invalidate_cache()
        return result

    def complete_task(self, project_id: str, task_id: str) -> dict:
        """完成任務（GET 現有資料 → 設 status=2 → batch update）"""
        existing = self.get_task(project_id, task_id)
        existing["status"] = 2
        result = self._request("POST", "/batch/task", {"update": [existing]})
        self._invalidate_cache()
        return result

    def delete_task(self, project_id: str, task_id: str) -> dict:
        """刪除任務"""
        result = self._request("POST", "/batch/task", {"delete": [{
            "taskId": task_id,
            "projectId": project_id,
        }]})
        self._invalidate_cache()
        return result

    def search_tasks(self, query: str, include_completed: bool = True) -> list:
        """搜尋任務（同時搜尋進行中和已完成的任務）

        Args:
            query: 搜尋關鍵字
            include_completed: 是否包含已完成任務（預設 True）
        """
        q = query.lower()

        def _match(t):
            return (q in t.get("title", "").lower() or
                    q in t.get("content", "").lower() or
                    q in t.get("desc", "").lower())

        # 搜尋 active tasks
        data = self.sync()
        active = data.get("syncTaskBean", {}).get("update", [])
        results = [t for t in active if _match(t)]

        # 搜尋 completed tasks
        if include_completed:
            completed = self.get_completed_tasks(limit=200)
            results.extend([t for t in completed if _match(t)])

        return results

    def get_completed_tasks(self, project_id: str = None,
                            limit: int = 50) -> list:
        """取得已完成任務"""
        if project_id:
            pid = urllib.parse.quote(project_id, safe="")
            path = f"/project/{pid}/completed"
        else:
            path = "/project/all/completed"
        params = {"from": "", "to": "", "limit": str(limit)}
        return self._request("GET", path, params=params)

    # ── Project Operations ───────────────────────────────────────────────

    def list_projects(self) -> list:
        """列出所有專案"""
        data = self.sync()
        return data.get("projectProfiles", [])

    def get_project(self, project_id: str) -> dict:
        """取得單一專案"""
        projects = self.list_projects()
        for p in projects:
            if p.get("id") == project_id:
                return p
        _error_exit(f"找不到專案 {project_id}")

    def get_project_data(self, project_id: str) -> dict:
        """取得專案 + 其所有任務"""
        project = self.get_project(project_id)
        tasks = self.list_tasks(project_id)
        return {"project": project, "tasks": tasks}

    def create_project(self, project_data: dict) -> dict:
        """建立專案"""
        result = self._request("POST", "/batch/projectProfile",
                               {"add": [project_data]})
        self._invalidate_cache()
        return result

    def update_project(self, project_id: str, project_data: dict) -> dict:
        """更新專案"""
        existing = self.get_project(project_id)
        existing.update(project_data)
        result = self._request("POST", "/batch/projectProfile",
                               {"update": [existing]})
        self._invalidate_cache()
        return result

    def delete_project(self, project_id: str) -> dict:
        """刪除專案"""
        result = self._request("POST", "/batch/projectProfile",
                               {"delete": [project_id]})
        self._invalidate_cache()
        return result

    # ── Tags ──────────────────────────────────────────────────────────────

    def list_tags(self) -> list:
        """列出所有標籤（從 sync 資料提取）"""
        data = self.sync()
        return data.get("tags", [])

    def create_tag(self, name: str, color: str = None,
                   parent: str = None) -> dict:
        """建立標籤"""
        tag = {"label": name, "name": name.lower(), "sortType": "project"}
        if color:
            tag["color"] = color
        if parent:
            tag["parent"] = parent.lower()
        result = self._request("POST", "/batch/tag", {"add": [tag]})
        self._invalidate_cache()
        return result

    # ── Habits ────────────────────────────────────────────────────────────

    def list_habits(self) -> list:
        """列出所有習慣"""
        return self._request("GET", "/habits")

    def create_habit(self, name: str, frequency: int = 1,
                     period: str = "day", icon: str = None,
                     color: str = None, reminder: str = None) -> dict:
        """建立習慣

        Args:
            name: 習慣名稱
            frequency: 目標次數（預設 1）
            period: day / week
            icon: emoji icon
            color: 顏色 hex
            reminder: 提醒時間，如 "09:00"
        """
        habit_id = format(int(time.time()), '08x') + secrets.token_hex(8)
        # 根據週期建立 RRULE
        if period == "week":
            repeat = f"RRULE:FREQ=WEEKLY;INTERVAL=1;TT_TIMES={frequency}"
        else:
            repeat = "RRULE:FREQ=DAILY;INTERVAL=1"
        habit = {
            "id": habit_id,
            "name": name,
            "type": "Boolean",
            "goal": float(frequency),
            "unit": "Count",
            "step": 1.0,
            "repeatRule": repeat,
            "status": 0,
            "encouragement": "",
            "totalCheckIns": 0,
            "sectionId": "",
        }
        if icon:
            habit["iconRes"] = icon
        if color:
            habit["color"] = color
        if reminder:
            habit["reminders"] = [reminder]
        return self._request("POST", "/habits/batch", {
            "add": [habit], "update": [], "delete": [],
        })

    def checkin_habit(self, habit_id: str, date: str = None,
                      value: float = 1.0) -> dict:
        """習慣打卡

        Args:
            habit_id: 習慣 ID
            date: 日期 YYYYMMDD（預設今天）
            value: 打卡值（預設 1）
        """
        if not date:
            from datetime import datetime
            date = datetime.now().strftime("%Y%m%d")
        checkin_id = format(int(time.time()), '08x') + secrets.token_hex(8)
        checkin = {
            "id": checkin_id,
            "habitId": habit_id,
            "checkinStamp": int(date),
            "status": 2,
            "value": value,
            "goal": 0,
        }
        return self._request("POST", "/habitCheckins/batch", {
            "add": [checkin], "update": [], "delete": [],
        })

    def delete_habit(self, habit_id: str) -> dict:
        """刪除習慣"""
        return self._request("POST", "/habits/batch", {
            "add": [], "update": [], "delete": [habit_id],
        })

    # ── Attachments ──────────────────────────────────────────────────────

    def upload_attachment(self, project_id: str, task_id: str,
                          file_path: str) -> dict:
        """上傳附件到指定任務

        Args:
            project_id: 專案 ID
            task_id: 任務 ID
            file_path: 本地檔案路徑

        Returns:
            API 回應 dict，包含 id, path, size, fileName, fileType, createdTime
        """
        if not os.path.exists(file_path):
            _error_exit(f"檔案不存在: {file_path}")

        # 生成 attachment ID（24 位 hex，類似 MongoDB ObjectId）
        timestamp_hex = format(int(time.time()), '08x')
        random_hex = secrets.token_hex(8)
        attachment_id = timestamp_hex + random_hex

        filename = os.path.basename(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        # 構建 multipart/form-data body
        boundary = "----WebKitFormBoundary" + secrets.token_hex(8)
        with open(file_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n"
        ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        # 使用 V1 attachment endpoint
        pid = urllib.parse.quote(project_id, safe="")
        tid = urllib.parse.quote(task_id, safe="")
        url = f"https://api.ticktick.com/api/v1/attachment/upload/{pid}/{tid}/{attachment_id}"

        headers = self._headers()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Accept"] = "*/*"
        if self.csrf_token:
            headers["x-csrftoken"] = self.csrf_token
            headers["Cookie"] = f"t={self.session_token}; _csrf_token={self.csrf_token}"

        req = urllib.request.Request(url, data=body, method="POST", headers=headers)

        try:
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode("utf-8")
                result = json.loads(text) if text else {}
                result["attachmentUrl"] = (
                    f"https://ticktick.com/api/v1/attachment/{pid}/{tid}/{attachment_id}"
                )
                return result
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            _error_exit(f"附件上傳失敗 HTTP {e.code}: {body_text}")

    # ── User & Settings ──────────────────────────────────────────────────

    def get_user_settings(self) -> dict:
        """取得用戶偏好設定（含時區）"""
        return self._request("GET", "/user/preferences/settings",
                             params={"includeWeb": "true"})

    def get_user_profile(self) -> dict:
        """取得用戶基本資訊"""
        return self._request("GET", "/user/profile")


# =============================================================================
# 快捷建構函式
# =============================================================================

def create_client_from_env() -> TickTickAPI:
    """從環境變數建立 client（搭配 doppler run 使用）"""
    username = os.environ.get("TICKTICK_USERNAME")
    password = os.environ.get("TICKTICK_PASSWORD")

    if not username or not password:
        _error_exit("需要設定 TICKTICK_USERNAME 和 TICKTICK_PASSWORD 環境變數")

    return TickTickAPI(username=username, password=password)
