---
name: ticktick
description: "Manages TickTick tasks and projects via CLI. Supports V1 Open API (tasks/projects CRUD, subtasks, reminders, repeat rules) and V2 internal API (search tasks, completed task history, tags CRUD, full sync). Use when the user asks to create, query, update, complete, or delete tasks; manage projects or tags; search for tasks; or view task completion history in TickTick."
---

# TickTick Skill

Manages TickTick tasks and projects. Combines V1 official API (stable CRUD) with V2 internal API (search, tags, completed history).

## Running Commands

All commands require Doppler for credential injection:

```bash
doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py <command>
```

**Workflow**: Always run `projects` first to get project IDs, then perform task operations.

## ⚠️ 建立任務的標準工作流程（必須遵守）

每次建立任務前，**必須**依序執行以下步驟：

1. **查看最近任務**：先用 `task-recent --project <PID>` 查看該專案最近 5 筆任務（可加 `--tag` 篩選類型）
2. **分析格式**：觀察 title 命名風格、content 結構、reminder 設定、priority、tags 等模式
3. **模仿格式**：新任務的 title / content / reminder / priority / tags 等欄位，必須與同類型既有任務保持一致的風格
4. **建立任務**：確認格式一致後，才執行 `task-create`（記得加上正確的 `--tag`）

**嚴禁**：未查看既有任務就直接建立任務、自行發明 title 格式或 content 結構。

**範例**：如果該專案的健身任務 title 都是「🏋️ 健身教練課」且帶 tag `健身`，新任務也必須用同樣格式和 tag。

## ⚠️ 完成任務時自動打卡（必須遵守）

完成以下 tag 的任務時，**必須同時打卡對應的習慣**：

| Task Tag | 對應 Habit | Habit ID | 目標 |
|----------|-----------|----------|------|
| `健身` | 🏋️ 健身 | `69a5a5414180e1beee860c71` | 4 次/週 |
| `funday` | 📚 英文課 | `69a5a543ba87b313f90deb78` | 5 堂/週 |
| `tutorabc` | 📚 英文課 | `69a5a543ba87b313f90deb78` | 5 堂/週 |

**流程**：`task-complete` → 檢查 tag → 自動 `habit-checkin --habit <對應ID>`

## Commands

### Projects (V1)

```bash
ticktick_cli.py projects                                          # List all
ticktick_cli.py project-get <project_id>                          # Get with tasks
ticktick_cli.py project-create --name "Work" [--color "#FF5733"] [--view kanban]
ticktick_cli.py project-update <project_id> [--name "..."] [--color "..."]
ticktick_cli.py project-delete <project_id>
```

### Tasks (V1)

```bash
ticktick_cli.py task-recent --project <pid> [--limit 5] [--tag TAG]   # ⚠️ 建立前先看格式
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

**Multi-line content**: Use `\n` in `--content` / `--desc` for line breaks. The CLI auto-converts literal `\n` to real newlines.

```bash
# Example: multi-line description
ticktick_cli.py task-create --project <pid> --title "Meeting" \
  --content "時間：2026/03/21 14:00-16:00\n地點：台北市中山區\n費用：NT$100"
```

### Search, Tags & History (V2)

```bash
ticktick_cli.py search "keyword"                                  # Search by title/content
ticktick_cli.py completed [--project PID] [--limit 50] [--tag TAG]  # Completed tasks (filterable)
ticktick_cli.py tags                                              # List tags
ticktick_cli.py tag-create --name "Important" [--color "#FF0000"]
ticktick_cli.py upload-attachment --project <pid> --task <tid> --file /path/to/file  # Upload attachment
ticktick_cli.py sync [--full]                                     # Full sync (debug)
```

### Habits（V2 習慣打卡）

```bash
ticktick_cli.py habits                                             # List habits
ticktick_cli.py habit-create --name "🏋️ 健身" --frequency 4 --period week
ticktick_cli.py habit-checkin --habit <id> [--date YYYYMMDD]       # Check in (default: today)
ticktick_cli.py habit-delete --habit <id>
```

**Tasks + Habits 搭配**：完成運動/上課 Task 後，同時用 `habit-checkin` 打卡追蹤週目標。

## Key Parameters

* `--project` is **required** for task-create and task-update
* `--tag` supports multiple values for create/update (`--tag "健身" --tag "重訓"`), single value for filter (`--tag "健身"`)
* Priority: `none`=0, `low`=1, `medium`=3, `high`=5
* Date format: ISO 8601 with timezone, e.g. `2026-03-01T09:00:00+0800`
  * Flexible timezone input: `+08:00`, `+8:00`, `+8` are all auto-normalized to `+0800`
* **Smart timezone**: If `--timezone` is omitted, it is auto-inferred from date offsets (e.g. `+0800` → `Asia/Taipei`)
* Reminder format: `TRIGGER:-PT30M` (30min before), `TRIGGER:-PT1H` (1hr), `TRIGGER:-P1D` (1 day)
* All output is JSON

**API details**: See [api-reference.md](references/api-reference.md) for V1/V2 endpoint reference and task field definitions.
