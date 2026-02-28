#!/usr/bin/env python3
"""
ticktick_api.py — TickTick V1 + V2 雙層 API 封裝

V1 (Open API):  官方 REST API，Bearer token 認證
V2 (Internal):  內部 API，帳密 session 認證（逆向工程）

環境變數（由 Doppler 注入）:
  TICKTICK_ACCESS_TOKEN  — V1 OAuth Bearer token
  TICKTICK_USERNAME      — V2 登入帳號（email）
  TICKTICK_PASSWORD      — V2 登入密碼

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
# V1 Open API — 官方 REST API
# =============================================================================

class TickTickV1:
    """TickTick Open API v1 封裝（Bearer token 認證）"""

    BASE_URL = "https://api.ticktick.com/open/v1"

    def __init__(self, access_token: str):
        if not access_token:
            _error_exit("TICKTICK_ACCESS_TOKEN 未設定")
        self.access_token = access_token

    def _request(self, method: str, path: str, data: dict = None) -> dict | list | str:
        """發送 V1 API 請求"""
        url = self.BASE_URL + path
        body = json.dumps(data).encode("utf-8") if data else None

        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        })

        try:
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode("utf-8")
                if not text:
                    return {}
                return json.loads(text)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            _error_exit(f"V1 API 錯誤 HTTP {e.code}: {body_text}")

    # ── Task Operations ──────────────────────────────────────────────────

    def get_task(self, project_id: str, task_id: str) -> dict:
        """取得單一任務"""
        pid = urllib.parse.quote(project_id, safe="")
        tid = urllib.parse.quote(task_id, safe="")
        return self._request("GET", f"/project/{pid}/task/{tid}")

    def create_task(self, task_data: dict) -> dict:
        """建立任務 — 支援所有官方欄位"""
        return self._request("POST", "/task", task_data)

    def update_task(self, task_id: str, task_data: dict) -> dict:
        """更新任務"""
        tid = urllib.parse.quote(task_id, safe="")
        return self._request("POST", f"/task/{tid}", task_data)

    def complete_task(self, project_id: str, task_id: str) -> dict:
        """完成任務"""
        pid = urllib.parse.quote(project_id, safe="")
        tid = urllib.parse.quote(task_id, safe="")
        return self._request("POST", f"/project/{pid}/task/{tid}/complete")

    def delete_task(self, project_id: str, task_id: str) -> dict:
        """刪除任務"""
        pid = urllib.parse.quote(project_id, safe="")
        tid = urllib.parse.quote(task_id, safe="")
        return self._request("DELETE", f"/project/{pid}/task/{tid}")

    # ── Project Operations ───────────────────────────────────────────────

    def list_projects(self) -> list:
        """列出所有專案"""
        return self._request("GET", "/project")

    def get_project(self, project_id: str) -> dict:
        """取得單一專案"""
        pid = urllib.parse.quote(project_id, safe="")
        return self._request("GET", f"/project/{pid}")

    def get_project_data(self, project_id: str) -> dict:
        """取得專案 + 任務 + 欄位"""
        pid = urllib.parse.quote(project_id, safe="")
        return self._request("GET", f"/project/{pid}/data")

    def create_project(self, project_data: dict) -> dict:
        """建立專案"""
        return self._request("POST", "/project", project_data)

    def update_project(self, project_id: str, project_data: dict) -> dict:
        """更新專案"""
        pid = urllib.parse.quote(project_id, safe="")
        return self._request("POST", f"/project/{pid}", project_data)

    def delete_project(self, project_id: str) -> dict:
        """刪除專案"""
        pid = urllib.parse.quote(project_id, safe="")
        return self._request("DELETE", f"/project/{pid}")


# =============================================================================
# V2 Internal API — 逆向工程的內部 API
# =============================================================================

class TickTickV2:
    """TickTick 內部 API v2 封裝（帳密 session 認證）

    使用完整的瀏覽器指紋偽裝，模擬真實的 TickTick Web 客戶端請求。
    """

    BASE_URL = "https://api.ticktick.com/api/v2"
    ORIGIN = "https://ticktick.com"

    # 模擬真實的 macOS Chrome 瀏覽器
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, username: str, password: str):
        if not username or not password:
            _error_exit("TICKTICK_USERNAME 或 TICKTICK_PASSWORD 未設定")
        self.session_token = None
        self.csrf_token = None
        self.inbox_id = None
        # 生成持久的裝置 ID（同一個 client 實例保持同一裝置身份）
        self._device_id = "65a0" + secrets.token_hex(10)
        self._login(username, password)

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

    def _request(self, method: str, path: str, data: dict = None,
                 params: dict = None) -> dict | list | str:
        """發送 V2 API 請求"""
        url = self.BASE_URL + path
        if params:
            qs = urllib.parse.urlencode(params)
            url = f"{url}?{qs}"

        body = json.dumps(data).encode("utf-8") if data else None
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
            _error_exit(f"V2 API 錯誤 HTTP {e.code}: {body_text}")

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

        _error_exit(f"V2 登入失敗（已嘗試所有端點）: {last_error}")

    # ── 全量同步 ──────────────────────────────────────────────────────────

    def sync(self) -> dict:
        """一次取得帳號全部資料（tasks, projects, tags, folders）"""
        return self._request("GET", "/batch/check/0")

    # ── 附件上傳 ──────────────────────────────────────────────────────────

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

        # 使用 V1 attachment endpoint（非 V2）
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

    # ── 已完成任務 ────────────────────────────────────────────────────────

    def get_completed_tasks(self, project_id: str = None,
                            limit: int = 50) -> list:
        """取得已完成任務"""
        if project_id:
            pid = urllib.parse.quote(project_id, safe="")
            path = f"/project/{pid}/completed"
            params = {"from": "", "to": "", "limit": str(limit)}
        else:
            path = "/project/all/completed"
            params = {"from": "", "to": "", "limit": str(limit)}
        return self._request("GET", path, params=params)

    # ── 批次操作 ──────────────────────────────────────────────────────────

    def batch_task(self, add: list = None, update: list = None,
                   delete: list = None) -> dict:
        """批次任務操作（add/update/delete）"""
        payload = {}
        if add:
            payload["add"] = add
        if update:
            payload["update"] = update
        if delete:
            payload["delete"] = delete
        return self._request("POST", "/batch/task", payload)

    # ── Tags ──────────────────────────────────────────────────────────────

    def list_tags(self) -> list:
        """列出所有標籤（從 sync 資料提取）"""
        data = self.sync()
        return data.get("tags", [])

    def batch_tag(self, add: list = None, update: list = None,
                  delete: list = None) -> dict:
        """批次標籤操作"""
        payload = {}
        if add:
            payload["add"] = add
        if update:
            payload["update"] = update
        if delete:
            payload["delete"] = delete
        return self._request("POST", "/batch/tag", payload)

    # ── User & Settings ──────────────────────────────────────────────────

    def get_user_settings(self) -> dict:
        """取得用戶偏好設定（含時區）"""
        return self._request("GET", "/user/preferences/settings",
                             params={"includeWeb": "true"})

    def get_user_profile(self) -> dict:
        """取得用戶基本資訊"""
        return self._request("GET", "/user/profile")


# =============================================================================
# 統一高階介面
# =============================================================================

class TickTickClient:
    """結合 V1 + V2 的統一介面
    
    V1: 用於官方支援的操作（穩定）
    V2: 用於 V1 不支援的進階功能（搜尋、已完成任務、tags 等）
    """

    def __init__(self, access_token: str = None,
                 username: str = None, password: str = None):
        self.v1 = TickTickV1(access_token) if access_token else None
        self.v2 = TickTickV2(username, password) if (username and password) else None

        if not self.v1 and not self.v2:
            _error_exit("至少需要 V1 (TICKTICK_ACCESS_TOKEN) 或 V2 (USERNAME+PASSWORD) 認證")

    # ── Task Operations（優先 V1）────────────────────────────────────────

    def list_projects(self) -> list:
        """列出所有專案"""
        if self.v1:
            return self.v1.list_projects()
        # V2 fallback: 從 sync 取
        data = self.v2.sync()
        return data.get("projectProfiles", [])

    def get_project(self, project_id: str) -> dict:
        """取得單一專案"""
        if self.v1:
            return self.v1.get_project(project_id)
        _error_exit("get_project 需要 V1 認證")

    def get_project_data(self, project_id: str) -> dict:
        """取得專案 + 任務 + 欄位"""
        if self.v1:
            return self.v1.get_project_data(project_id)
        _error_exit("get_project_data 需要 V1 認證")

    def create_project(self, **kwargs) -> dict:
        """建立專案"""
        if self.v1:
            return self.v1.create_project(kwargs)
        _error_exit("create_project 需要 V1 認證")

    def update_project(self, project_id: str, **kwargs) -> dict:
        """更新專案"""
        if self.v1:
            return self.v1.update_project(project_id, kwargs)
        _error_exit("update_project 需要 V1 認證")

    def delete_project(self, project_id: str) -> dict:
        """刪除專案"""
        if self.v1:
            return self.v1.delete_project(project_id)
        _error_exit("delete_project 需要 V1 認證")

    def list_tasks(self, project_id: str = None) -> list:
        """列出任務（指定專案或全部）"""
        if project_id:
            if self.v1:
                data = self.v1.get_project_data(project_id)
                return data.get("tasks", [])
        # 全部任務：用 V2 sync 或遍歷專案
        if self.v2:
            data = self.v2.sync()
            tasks = data.get("syncTaskBean", {}).get("update", [])
            if project_id:
                tasks = [t for t in tasks if t.get("projectId") == project_id]
            return tasks
        # V1 fallback: 遍歷所有專案
        projects = self.v1.list_projects()
        all_tasks = []
        for p in projects:
            try:
                pd = self.v1.get_project_data(p["id"])
                all_tasks.extend(pd.get("tasks", []))
            except SystemExit:
                pass  # 跳過失敗的專案
        return all_tasks

    def get_task(self, project_id: str, task_id: str) -> dict:
        """取得單一任務"""
        if self.v1:
            return self.v1.get_task(project_id, task_id)
        _error_exit("get_task 需要 V1 認證")

    def create_task(self, **kwargs) -> dict:
        """建立任務 — 支援所有欄位"""
        if self.v1:
            return self.v1.create_task(kwargs)
        _error_exit("create_task 需要 V1 認證")

    def update_task(self, task_id: str, **kwargs) -> dict:
        """更新任務（GET-merge-POST，避免覆蓋附件等欄位）"""
        if not self.v1:
            _error_exit("update_task 需要 V1 認證")
        # 先取得完整 task data（含 attachments 等所有欄位）
        project_id = kwargs.get("projectId")
        if not project_id:
            _error_exit("update_task 需要 projectId")
        existing = self.v1.get_task(project_id, task_id)
        # 把更新欄位 merge 上去
        existing.update(kwargs)
        return self.v1.update_task(task_id, existing)

    def complete_task(self, project_id: str, task_id: str) -> dict:
        """完成任務"""
        if self.v1:
            return self.v1.complete_task(project_id, task_id)
        _error_exit("complete_task 需要 V1 認證")

    def delete_task(self, project_id: str, task_id: str) -> dict:
        """刪除任務"""
        if self.v1:
            return self.v1.delete_task(project_id, task_id)
        _error_exit("delete_task 需要 V1 認證")

    # ── V2 增強功能 ──────────────────────────────────────────────────────

    def search_tasks(self, query: str) -> list:
        """搜尋任務（V2 sync + 本地過濾）"""
        if not self.v2:
            _error_exit("search 需要 V2 認證 (USERNAME+PASSWORD)")
        data = self.v2.sync()
        tasks = data.get("syncTaskBean", {}).get("update", [])
        q = query.lower()
        return [t for t in tasks if
                q in t.get("title", "").lower() or
                q in t.get("content", "").lower() or
                q in t.get("desc", "").lower()]

    def get_completed_tasks(self, project_id: str = None,
                            limit: int = 50) -> list:
        """取得已完成任務"""
        if not self.v2:
            _error_exit("completed 需要 V2 認證 (USERNAME+PASSWORD)")
        return self.v2.get_completed_tasks(project_id, limit)

    def list_tags(self) -> list:
        """列出所有標籤"""
        if not self.v2:
            _error_exit("tags 需要 V2 認證 (USERNAME+PASSWORD)")
        return self.v2.list_tags()

    def create_tag(self, name: str, color: str = None,
                   parent: str = None) -> dict:
        """建立標籤"""
        if not self.v2:
            _error_exit("tag-create 需要 V2 認證 (USERNAME+PASSWORD)")
        tag = {"label": name, "name": name.lower(), "sortType": "project"}
        if color:
            tag["color"] = color
        if parent:
            tag["parent"] = parent.lower()
        return self.v2.batch_tag(add=[tag])

    def sync(self) -> dict:
        """全量同步（除錯用）"""
        if not self.v2:
            _error_exit("sync 需要 V2 認證 (USERNAME+PASSWORD)")
        return self.v2.sync()

    def upload_attachment(self, project_id: str, task_id: str,
                          file_path: str) -> dict:
        """上傳附件到指定任務"""
        if not self.v2:
            _error_exit("upload-attachment 需要 V2 認證 (USERNAME+PASSWORD)")
        return self.v2.upload_attachment(project_id, task_id, file_path)


# =============================================================================
# 快捷建構函式
# =============================================================================

def create_client_from_env() -> TickTickClient:
    """從環境變數建立 client（搭配 doppler run 使用）"""
    access_token = os.environ.get("TICKTICK_ACCESS_TOKEN")
    username = os.environ.get("TICKTICK_USERNAME")
    password = os.environ.get("TICKTICK_PASSWORD")

    return TickTickClient(
        access_token=access_token,
        username=username,
        password=password,
    )
