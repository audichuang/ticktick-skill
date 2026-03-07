# TickTick API Reference

## Contents

* API endpoints (Auth, Tasks, Projects, Tags, Habits, Sync)
* Task field definitions
* Environment variables

## Base

Base URL: `https://api.ticktick.com/api/v2`
Auth: `Cookie: t=<session_token>` + browser fingerprint headers

## Auth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/user/signon?wc=true&remember=true` | Login (returns token) |
| GET | `/user/preferences/settings?includeWeb=true` | User settings |
| GET | `/user/profile` | User profile |

## Task Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/batch/check/0` | Full sync (get all tasks) |
| POST | `/batch/task` | Batch task operations (add/update/delete) |
| POST | `/batch/taskComplete` | Complete tasks |
| GET | `/project/all/completed?limit=N` | All completed tasks |
| GET | `/project/{pid}/completed?limit=N` | Project completed tasks |

## Project Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/batch/check/0` | Full sync (get all projects) |
| POST | `/batch/projectProfile` | Batch project operations (add/update/delete) |

## Tag Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/batch/check/0` | Full sync (get all tags) |
| POST | `/batch/tag` | Batch tag operations (add/update/delete) |

## Habit Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/habits` | List all habits |
| POST | `/habits/batch` | Batch habit operations (add/update/delete) |
| POST | `/habitCheckins/batch` | Batch check-in operations |

## Attachment Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/attachment/upload/{pid}/{tid}/{aid}` | Upload attachment (multipart/form-data) |

## Task Fields

| Field | Type | Notes |
|-------|------|-------|
| title\* | string | Required |
| projectId\* | string | Required |
| content | string | Notes/description |
| desc | string | Checklist description |
| priority | int | 0=none, 1=low, 3=medium, 5=high |
| status | int | 0=active, 2=completed |
| dueDate | string | ISO 8601: `yyyy-MM-dd'T'HH:mm:ssZ` |
| startDate | string | Same format as dueDate |
| isAllDay | bool | All-day task |
| timeZone | string | e.g. `Asia/Taipei` |
| reminders | string\[] | e.g. `["TRIGGER:-PT30M"]` |
| repeatFlag | string | RRULE e.g. `RRULE:FREQ=DAILY` |
| items | object\[] | Subtasks: `[{title, status}]` |
| tags | string\[] | Tag labels |
| kind | string | TEXT / NOTE / CHECKLIST |

## Sync Response Structure

```json
{
  "inboxId": "inbox123...",
  "projectProfiles": [...],
  "projectGroups": [...],
  "tags": [...],
  "syncTaskBean": {
    "update": [...]
  }
}
```

## Environment Variables

Injected via `doppler run -p ticktick -c dev`:

| Variable | Purpose |
|----------|---------|
| `TICKTICK_USERNAME` | TickTick email |
| `TICKTICK_PASSWORD` | TickTick password |
