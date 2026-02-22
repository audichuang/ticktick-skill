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
ticktick_cli.py tasks [--project PID] [--status pending|completed]
ticktick_cli.py task-get <project_id> <task_id>
ticktick_cli.py task-create --project <pid> --title "Title" \
  [--content "Notes"] [--priority none|low|medium|high] \
  [--due "2026-03-01T09:00:00+0800"] [--start "..."] [--all-day] \
  [--timezone "Asia/Taipei"] [--kind TEXT|NOTE|CHECKLIST] \
  [--reminder "TRIGGER:-PT30M"] [--repeat "RRULE:FREQ=DAILY"] \
  [--subtask "Sub 1" --subtask "Sub 2"]
ticktick_cli.py task-update <task_id> --project <pid> [--title "..."] [--priority high]
ticktick_cli.py task-complete <project_id> <task_id>
ticktick_cli.py task-delete <project_id> <task_id>
```

### Search, Tags & History (V2)

```bash
ticktick_cli.py search "keyword"                                  # Search by title/content
ticktick_cli.py completed [--project PID] [--limit 50]            # Completed tasks
ticktick_cli.py tags                                              # List tags
ticktick_cli.py tag-create --name "Important" [--color "#FF0000"]
ticktick_cli.py sync [--full]                                     # Full sync (debug)
```

## Key Parameters

* `--project` is **required** for task-create and task-update
* Priority: `none`=0, `low`=1, `medium`=3, `high`=5
* Date format: ISO 8601 with timezone, e.g. `2026-03-01T09:00:00+0800`
* All output is JSON

**API details**: See [api-reference.md](references/api-reference.md) for V1/V2 endpoint reference and task field definitions.
