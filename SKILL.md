---
name: ticktick
description: "Manages TickTick tasks, projects, tags, and habits via CLI. Supports tasks CRUD, subtasks, reminders, repeat rules, search, completed task history, tags CRUD, habits with check-ins, and file attachments. Use when the user asks to create, query, update, complete, or delete tasks; manage projects or tags; search for tasks; view task completion history; or track habits in TickTick."
---

# TickTick Skill

管理 TickTick 任務、專案、標籤和習慣的 CLI 工具。

## Running Commands

所有命令透過 Doppler 注入認證：

```bash
doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py <command>
```

**Workflow**: 先用 `projects` 取得 project ID，再進行 task 操作。

## ⚠️ 建立任務的標準工作流程（必須遵守）

每次建立任務前，**必須**依序執行以下步驟：

1. **查看最近任務（含已完成）**：先用 `task-recent --project <PID>` 查看該專案最近任務。此命令**預設包含已完成任務**，每筆會標記 `status: active/completed`
2. **確認無重複**：檢查是否已有同名或同類型的任務（含已完成的）。如果有，**直接更新該任務**而非新建
3. **分析格式**：觀察 title 命名風格、content 結構、reminder 設定、priority、tags、**startDate / dueDate / isAllDay** 等模式
4. **模仿格式**：新任務的 title / content / reminder / priority / tags / **startDate / dueDate / isAllDay** 等欄位，必須與同類型既有任務保持一致的風格
5. **建立任務**：確認無重複且格式一致後，才執行 `task-create`（記得加上正確的 `--tag`）

**嚴禁**：未查看既有任務就直接建立任務、自行發明 title 格式或 content 結構、忽略已完成的同名任務而重複建立。

**範例**：如果 `task-recent` 列出的任務中，「羽球課」已經 `status: completed`，就不該新建一筆，而是用 `task-update` 把內容寫進那筆已完成的任務。

## ⚠️ 完成任務時自動打卡（必須遵守）

完成以下 tag 的任務時，**必須同時打卡對應的習慣**：

| Task Tag | 對應 Habit | Habit ID | 目標 |
|----------|-----------|----------|------|
| `健身` | 🏋️ 健身 | `69a5a5414180e1beee860c71` | 4 次/週 |
| `funday` | 📚 英文課 | `69a5a543ba87b313f90deb78` | 5 堂/週 |
| `tutorabc` | 📚 英文課 | `69a5a543ba87b313f90deb78` | 5 堂/週 |

**流程**：`task-complete` → 檢查 tag → 自動 `habit-checkin --habit <對應ID>`

## Commands

### Projects

```bash
ticktick_cli.py projects                                          # List all
ticktick_cli.py project-get <project_id>                          # Get with tasks
ticktick_cli.py project-create --name "Work" [--color "#FF5733"] [--view kanban]
ticktick_cli.py project-update <project_id> [--name "..."] [--color "..."]
ticktick_cli.py project-delete <project_id>
```

### Tasks

```bash
ticktick_cli.py task-recent --project <pid> [--limit 5] [--tag TAG]   # ⚠️ 建立前先看（含已完成）
ticktick_cli.py task-recent --project <pid> --active-only             # 只看進行中
ticktick_cli.py tasks [--project PID] [--status pending|completed] [--tag TAG]
ticktick_cli.py task-get <project_id> <task_id>
ticktick_cli.py task-create --project <pid> --title "Title" \
  [--content "Notes"] [--priority none|low|medium|high] \
  [--due "2026-03-01T09:00:00+0800"] [--start "..."] [--all-day] \
  [--timezone "Asia/Taipei"] [--kind TEXT|NOTE|CHECKLIST] \
  [--reminder "TRIGGER:-PT30M"] [--repeat "RRULE:FREQ=DAILY"] \
  [--subtask "Sub 1" --subtask "Sub 2"] [--tag "健身" --tag "重訓"]
ticktick_cli.py task-update <task_id> --project <pid> [--title "..."] [--priority high] [--tag "健身"]
ticktick_cli.py task-complete <project_id> <task_id>
ticktick_cli.py task-delete <project_id> <task_id>
```

### ⚠️ 時段任務 vs 全天任務（必須遵守）

建立有**具體時間段**的任務（課程、會議、健身等），**必須**遵守以下規則：

| 情境 | 正確做法 | 錯誤做法 |
|------|----------|----------|
| 有明確時段（如 13:00-14:00） | 用 `--start` + `--due` 設定起止時間 | ❌ 只設 `--due` 不設 `--start` |
| 整天事件（如生日、截止日） | 用 `--due` + `--all-day` | ❌ 有時段卻用 `--all-day` |
| 時間資訊 | 放在 `--start` / `--due` 參數 | ❌ 把時間塞在 title 裡 |

**嚴禁**：

* ❌ 把時間寫在 title 裡（如 `--title "羽球課 13:00-14:00"`），時間必須用 `--start` + `--due`
* ❌ 有明確時段卻用 `--all-day` 或完全不設時間
* ❌ 只設 `--due` 不設 `--start`（這會讓 TickTick 顯示為截止日而非時段）

```bash
# ✅ 正確：時段任務（羽球課 13:00-14:00）
ticktick_cli.py task-create --project <pid> --title "🏸 羽球課" \
  --start "2026-03-13T13:00:00+0800" --due "2026-03-13T14:00:00+0800" \
  --reminder "TRIGGER:-PT30M" --tag "運動"

# ✅ 正確：全天任務（整天截止日）
ticktick_cli.py task-create --project <pid> --title "報告截止" \
  --due "2026-03-15T00:00:00+0800" --all-day

# ❌ 錯誤：把時間塞在 title 裡
ticktick_cli.py task-create --project <pid> --title "羽球課 03/13 13:00-14:00"
```

**Multi-line content**: Use `\n` in `--content` / `--desc` for line breaks. The CLI auto-converts literal `\n` to real newlines.

```bash
# Example: multi-line description
ticktick_cli.py task-create --project <pid> --title "Meeting" \
  --content "時間：2026/03/21 14:00-16:00\n地點：台北市中山區\n費用：NT$100"
```

### Search & History

```bash
ticktick_cli.py search "keyword"                                  # Search active + completed tasks
ticktick_cli.py search "keyword" --active-only                    # Search active tasks only
ticktick_cli.py completed [--project PID] [--limit 50] [--tag TAG]  # Completed tasks (filterable)
```

### Tags

```bash
ticktick_cli.py tags                                              # List tags
ticktick_cli.py tag-create --name "Important" [--color "#FF0000"]
```

### Habits

```bash
ticktick_cli.py habits                                             # List habits
ticktick_cli.py habit-create --name "🏋️ 健身" --frequency 4 --period week
ticktick_cli.py habit-checkin --habit <id> [--date YYYYMMDD]       # Check in (default: today)
ticktick_cli.py habit-delete --habit <id>
```

**Tasks + Habits 搭配**：完成運動/上課 Task 後，同時用 `habit-checkin` 打卡追蹤週目標。

### Utilities

```bash
ticktick_cli.py upload-attachment --project <pid> --task <tid> --file /path/to/file  # Upload attachment
ticktick_cli.py sync [--full]                                     # Full sync (debug)
```

## Key Parameters

* `--project` is **required** for task-create and task-update
* `--tag` supports multiple values for create/update (`--tag "健身" --tag "重訓"`), single value for filter (`--tag "健身"`)
* Priority: `none`=0, `low`=1, `medium`=3, `high`=5
* Date format: ISO 8601 with timezone, e.g. `2026-03-01T09:00:00+0800`
  * Flexible timezone input: `+08:00`, `+8:00`, `+8` are all auto-normalized to `+0800`
* **Smart timezone**: If `--timezone` is omitted, it is auto-inferred from date offsets (e.g. `+0800` → `Asia/Taipei`)
* Reminder format: `TRIGGER:-PT30M` (30min before), `TRIGGER:-PT1H` (1hr), `TRIGGER:-P1D` (1 day)
* All output is JSON

**API details**: See [api-reference.md](references/api-reference.md) for endpoint reference and task field definitions.
