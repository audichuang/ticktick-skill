# TickTick CLI Skill

管理 TickTick 任務、專案、標籤和習慣的 CLI 工具。

## 功能

* Tasks — 完整 CRUD（含子任務、提醒、重複規則）
* Projects — 完整 CRUD
* Search — 任務搜尋、已完成任務歷史
* Tags — CRUD
* Habits — CRUD + 打卡
* Attachments — 檔案上傳

零依賴，純 Python 標準庫（`urllib.request`），搭配 Doppler 管理密鑰。

## 安裝設定

### 1. Doppler 環境變數

```bash
# 建立 Doppler project（如尚未建立）
doppler projects create ticktick

# 設定認證
doppler secrets set TICKTICK_USERNAME="<your_email>" -p ticktick -c dev
doppler secrets set TICKTICK_PASSWORD="<your_password>" -p ticktick -c dev
```

### 2. 執行命令

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

# 搜尋與歷史
ticktick_cli.py search "keyword"
ticktick_cli.py completed --limit 10

# 標籤
ticktick_cli.py tags

# 習慣
ticktick_cli.py habits
ticktick_cli.py habit-checkin --habit <id>

# 同步
ticktick_cli.py sync
```

所有命令輸出 JSON。完整參數說明見 `SKILL.md`。

## 檔案結構

```
ticktick/
├── SKILL.md                  # AI Agent 使用指引
├── README.md                 # 人類安裝設定指引
├── scripts/
│   ├── ticktick_api.py       # 統一 API 封裝
│   └── ticktick_cli.py       # CLI 入口（22 個子命令）
└── references/
    └── api-reference.md      # 端點速查
```

## License

MIT
