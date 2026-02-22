# TickTick CLI Skill

管理 TickTick 任務和專案的 CLI 工具，結合 V1 官方 API 和 V2 內部 API。

## 功能

* **V1 Official API** — Tasks / Projects 完整 CRUD（含子任務、提醒、重複規則）
* **V2 Internal API** — 任務搜尋、已完成任務歷史、標籤 CRUD、全量同步

零依賴，純 Python 標準庫（`urllib.request`），搭配 Doppler 管理密鑰。

## 安裝設定

### 1. Doppler 環境變數

```bash
# 建立 Doppler project
doppler projects create ticktick

# V1 認證（OAuth Bearer token）
doppler secrets set TICKTICK_ACCESS_TOKEN="<your_token>" -p ticktick -c dev

# V2 認證（帳密登入）
doppler secrets set TICKTICK_USERNAME="<your_email>" -p ticktick -c dev
doppler secrets set TICKTICK_PASSWORD="<your_password>" -p ticktick -c dev
```

### 2. 取得 V1 Access Token

1. 前往 [TickTick Developer Center](https://developer.ticktick.com/manage)
2. 建立 App，設定 Redirect URI 為 `http://localhost:8080`
3. 完成 OAuth 授權流程取得 `access_token`
4. 將 token 存入 Doppler

### 3. 執行命令

```bash
doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py <command>
```

## 命令速查

```bash
# 專案
ticktick_cli.py projects
ticktick_cli.py project-create --name "Work" --color "#FF5733"

# 任務
ticktick_cli.py tasks --project <pid>
ticktick_cli.py task-create --project <pid> --title "Title" --priority high
ticktick_cli.py task-complete <pid> <tid>
ticktick_cli.py task-delete <pid> <tid>

# V2 增強
ticktick_cli.py search "keyword"
ticktick_cli.py completed --limit 10
ticktick_cli.py tags
ticktick_cli.py sync
```

所有命令輸出 JSON。完整參數說明見 `SKILL.md`。

## 檔案結構

```
ticktick/
├── SKILL.md                  # AI Agent 使用指引
├── README.md                 # 人類安裝設定指引
├── scripts/
│   ├── ticktick_api.py       # V1+V2 雙層 API 封裝
│   └── ticktick_cli.py       # CLI 入口（16 個子命令）
└── references/
    └── api-reference.md      # V1+V2 端點速查
```

## License

MIT
