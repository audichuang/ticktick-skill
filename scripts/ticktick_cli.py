#!/usr/bin/env python3
"""
ticktick_cli.py — TickTick CLI 入口

用法:
  doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py <command> [options]

範例:
  # 列出所有專案
  doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py projects

  # 建立任務（含提醒和重複）
  doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py task-create \
    --project <project_id> --title "每日站會" --priority high \
    --due "2026-03-01T09:00:00+0800" \
    --reminder "TRIGGER:-PT30M" \
    --repeat "RRULE:FREQ=DAILY;INTERVAL=1"

  # 搜尋任務（V2）
  doppler run -p ticktick -c dev -- python3 scripts/ticktick_cli.py search "站會"
"""

import argparse
import json
import sys
import os

# 確保可以 import 同目錄的 ticktick_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ticktick_api import (
    create_client_from_env,
    PRIORITY_MAP,
    PRIORITY_REVERSE,
    _json_output,
)


# =============================================================================
# 子命令實現
# =============================================================================

def cmd_projects(args):
    """列出所有專案"""
    client = create_client_from_env()
    projects = client.list_projects()
    _json_output(projects)


def cmd_project_get(args):
    """取得單一專案（含任務和欄位）"""
    client = create_client_from_env()
    data = client.get_project_data(args.project_id)
    _json_output(data)


def cmd_project_create(args):
    """建立專案"""
    client = create_client_from_env()
    kwargs = {"name": args.name}
    if args.color:
        kwargs["color"] = args.color
    if args.view:
        kwargs["viewMode"] = args.view
    if args.kind:
        kwargs["kind"] = args.kind
    result = client.create_project(**kwargs)
    _json_output(result)


def cmd_project_update(args):
    """更新專案"""
    client = create_client_from_env()
    kwargs = {}
    if args.name:
        kwargs["name"] = args.name
    if args.color:
        kwargs["color"] = args.color
    if not kwargs:
        print("錯誤: 至少需要指定一個要更新的欄位 (--name, --color)", file=sys.stderr)
        sys.exit(1)
    result = client.update_project(args.project_id, **kwargs)
    _json_output(result)


def cmd_project_delete(args):
    """刪除專案"""
    client = create_client_from_env()
    result = client.delete_project(args.project_id)
    _json_output({"success": True, "deleted": args.project_id})


def cmd_tasks(args):
    """列出任務"""
    client = create_client_from_env()
    tasks = client.list_tasks(project_id=args.project)
    # 可選的狀態過濾
    if args.status == "pending":
        tasks = [t for t in tasks if t.get("status", 0) == 0]
    elif args.status == "completed":
        tasks = [t for t in tasks if t.get("status", 0) == 2]
    _json_output(tasks)


def cmd_task_get(args):
    """取得單一任務"""
    client = create_client_from_env()
    task = client.get_task(args.project_id, args.task_id)
    _json_output(task)


def cmd_task_create(args):
    """建立任務"""
    client = create_client_from_env()
    kwargs = {
        "title": args.title,
        "projectId": args.project,
    }
    if args.content:
        kwargs["content"] = args.content.replace("\\n", "\n")
    if args.desc:
        kwargs["desc"] = args.desc.replace("\\n", "\n")
    if args.priority:
        kwargs["priority"] = PRIORITY_MAP.get(args.priority, 0)
    if args.due:
        kwargs["dueDate"] = args.due
    if args.start:
        kwargs["startDate"] = args.start
    if args.all_day:
        kwargs["isAllDay"] = True
    if args.timezone:
        kwargs["timeZone"] = args.timezone
    if args.kind:
        kwargs["kind"] = args.kind
    if args.reminder:
        kwargs["reminders"] = args.reminder  # 可多次指定
    if args.repeat:
        kwargs["repeatFlag"] = args.repeat
    if args.subtask:
        # 子任務格式: ["title1", "title2", ...]
        kwargs["items"] = [{"title": t, "status": 0} for t in args.subtask]

    result = client.create_task(**kwargs)
    _json_output(result)


def cmd_task_update(args):
    """更新任務"""
    client = create_client_from_env()
    kwargs = {
        "id": args.task_id,
        "projectId": args.project,
    }
    if args.title:
        kwargs["title"] = args.title
    if args.content:
        kwargs["content"] = args.content.replace("\\n", "\n")
    if args.priority:
        kwargs["priority"] = PRIORITY_MAP.get(args.priority, 0)
    if args.due:
        kwargs["dueDate"] = args.due
    if args.start:
        kwargs["startDate"] = args.start

    result = client.update_task(args.task_id, **kwargs)
    _json_output(result)


def cmd_task_complete(args):
    """完成任務"""
    client = create_client_from_env()
    result = client.complete_task(args.project_id, args.task_id)
    _json_output({"success": True, "completed": args.task_id})


def cmd_task_delete(args):
    """刪除任務"""
    client = create_client_from_env()
    result = client.delete_task(args.project_id, args.task_id)
    _json_output({"success": True, "deleted": args.task_id})


# ── V2 增強命令 ──────────────────────────────────────────────────────────

def cmd_search(args):
    """搜尋任務（V2）"""
    client = create_client_from_env()
    tasks = client.search_tasks(args.query)
    _json_output(tasks)


def cmd_completed(args):
    """已完成任務（V2）"""
    client = create_client_from_env()
    tasks = client.get_completed_tasks(
        project_id=args.project,
        limit=args.limit,
    )
    _json_output(tasks)


def cmd_tags(args):
    """列出所有標籤（V2）"""
    client = create_client_from_env()
    tags = client.list_tags()
    _json_output(tags)


def cmd_tag_create(args):
    """建立標籤（V2）"""
    client = create_client_from_env()
    result = client.create_tag(
        name=args.name,
        color=args.color,
        parent=args.parent,
    )
    _json_output(result)


def cmd_sync(args):
    """全量同步（V2，除錯用）"""
    client = create_client_from_env()
    data = client.sync()
    # 只輸出摘要，避免資料量過大
    summary = {
        "inboxId": data.get("inboxId"),
        "projects": len(data.get("projectProfiles", [])),
        "project_folders": len(data.get("projectGroups", [])),
        "tags": len(data.get("tags", [])),
        "tasks": len(data.get("syncTaskBean", {}).get("update", [])),
    }
    if args.full:
        _json_output(data)
    else:
        _json_output(summary)


# =============================================================================
# argparse 定義
# =============================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        prog="ticktick_cli",
        description="TickTick CLI — V1 + V2 雙層 API",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # ── Projects ─────────────────────────────────────────────────────────

    sub.add_parser("projects", help="列出所有專案")

    p = sub.add_parser("project-get", help="取得專案詳情（含任務）")
    p.add_argument("project_id", help="專案 ID")

    p = sub.add_parser("project-create", help="建立專案")
    p.add_argument("--name", required=True, help="專案名稱")
    p.add_argument("--color", help='顏色 hex，如 "#FF5733"')
    p.add_argument("--view", choices=["list", "kanban", "timeline"],
                   help="視圖模式")
    p.add_argument("--kind", choices=["TASK", "NOTE"], default="TASK",
                   help="專案類型")

    p = sub.add_parser("project-update", help="更新專案")
    p.add_argument("project_id", help="專案 ID")
    p.add_argument("--name", help="新名稱")
    p.add_argument("--color", help="新顏色")

    p = sub.add_parser("project-delete", help="刪除專案")
    p.add_argument("project_id", help="專案 ID")

    # ── Tasks ────────────────────────────────────────────────────────────

    p = sub.add_parser("tasks", help="列出任務")
    p.add_argument("--project", help="專案 ID（不指定則列出全部）")
    p.add_argument("--status", choices=["pending", "completed"],
                   help="過濾狀態")

    p = sub.add_parser("task-get", help="取得單一任務")
    p.add_argument("project_id", help="專案 ID")
    p.add_argument("task_id", help="任務 ID")

    p = sub.add_parser("task-create", help="建立任務")
    p.add_argument("--project", required=True, help="專案 ID")
    p.add_argument("--title", required=True, help="任務標題")
    p.add_argument("--content", help="任務內容/備註")
    p.add_argument("--desc", help="Checklist 描述")
    p.add_argument("--priority", choices=["none", "low", "medium", "high"],
                   help="優先級")
    p.add_argument("--due", help='到期日 "yyyy-MM-ddTHH:mm:ssZ"')
    p.add_argument("--start", help='開始日期 "yyyy-MM-ddTHH:mm:ssZ"')
    p.add_argument("--all-day", action="store_true", help="全天任務")
    p.add_argument("--timezone", help='時區，如 "Asia/Taipei"')
    p.add_argument("--kind", choices=["TEXT", "NOTE", "CHECKLIST"],
                   help="任務類型")
    p.add_argument("--reminder", action="append",
                   help='提醒規則，如 "TRIGGER:-PT30M"（可多次指定）')
    p.add_argument("--repeat", help='重複規則 RRULE，如 "RRULE:FREQ=DAILY"')
    p.add_argument("--subtask", action="append",
                   help="子任務標題（可多次指定）")

    p = sub.add_parser("task-update", help="更新任務")
    p.add_argument("task_id", help="任務 ID")
    p.add_argument("--project", required=True, help="專案 ID")
    p.add_argument("--title", help="新標題")
    p.add_argument("--content", help="新內容")
    p.add_argument("--priority", choices=["none", "low", "medium", "high"],
                   help="新優先級")
    p.add_argument("--due", help="新到期日")
    p.add_argument("--start", help="新開始日期")

    p = sub.add_parser("task-complete", help="完成任務")
    p.add_argument("project_id", help="專案 ID")
    p.add_argument("task_id", help="任務 ID")

    p = sub.add_parser("task-delete", help="刪除任務")
    p.add_argument("project_id", help="專案 ID")
    p.add_argument("task_id", help="任務 ID")

    # ── V2 增強命令 ──────────────────────────────────────────────────────

    p = sub.add_parser("search", help="搜尋任務（V2）")
    p.add_argument("query", help="搜尋關鍵字")

    p = sub.add_parser("completed", help="已完成任務（V2）")
    p.add_argument("--project", help="專案 ID（不指定則全部）")
    p.add_argument("--limit", type=int, default=50, help="筆數上限")

    sub.add_parser("tags", help="列出所有標籤（V2）")

    p = sub.add_parser("tag-create", help="建立標籤（V2）")
    p.add_argument("--name", required=True, help="標籤名稱")
    p.add_argument("--color", help='顏色 hex，如 "#57A8FF"')
    p.add_argument("--parent", help="父標籤名稱")

    p = sub.add_parser("sync", help="全量同步（V2，除錯用）")
    p.add_argument("--full", action="store_true",
                   help="輸出完整同步資料（預設只輸出摘要）")

    return parser


# =============================================================================
# 入口
# =============================================================================

COMMAND_MAP = {
    "projects": cmd_projects,
    "project-get": cmd_project_get,
    "project-create": cmd_project_create,
    "project-update": cmd_project_update,
    "project-delete": cmd_project_delete,
    "tasks": cmd_tasks,
    "task-get": cmd_task_get,
    "task-create": cmd_task_create,
    "task-update": cmd_task_update,
    "task-complete": cmd_task_complete,
    "task-delete": cmd_task_delete,
    "search": cmd_search,
    "completed": cmd_completed,
    "tags": cmd_tags,
    "tag-create": cmd_tag_create,
    "sync": cmd_sync,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handler = COMMAND_MAP.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
