# TickTick API Reference

## Contents

* V1 Open API endpoints (Task, Project)
* V1 Task field definitions
* V2 Internal API endpoints (Auth, Sync, Batch, Completed)
* V2 Sync response structure
* Environment variables

## V1 — Open API

Base URL: `https://api.ticktick.com/open/v1`
Auth: `Authorization: Bearer <TICKTICK_ACCESS_TOKEN>`

### Task Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/project/{pid}/task/{tid}` | Get task |
| POST | `/task` | Create task |
| POST | `/task/{tid}` | Update task |
| POST | `/project/{pid}/task/{tid}/complete` | Complete task |
| DELETE | `/project/{pid}/task/{tid}` | Delete task |

### Project Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/project` | List projects |
| GET | `/project/{pid}` | Get project |
| GET | `/project/{pid}/data` | Get project + tasks + columns |
| POST | `/project` | Create project |
| POST | `/project/{pid}` | Update project |
| DELETE | `/project/{pid}` | Delete project |

### Task Fields

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

***

## V2 — Internal API

Base URL: `https://api.ticktick.com/api/v2`
Auth: `Cookie: t=<session_token>` + browser fingerprint headers

### Auth Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/user/signon?wc=true&remember=true` | Login (returns token) |
| GET | `/user/preferences/settings?includeWeb=true` | User settings |
| GET | `/user/profile` | User profile |

### Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/batch/check/0` | Full sync (all tasks/projects/tags) |
| POST | `/batch/task` | Batch task operations |
| POST | `/batch/tag` | Batch tag operations |
| GET | `/project/all/completed?limit=N` | All completed tasks |
| GET | `/project/{pid}/completed?limit=N` | Project completed tasks |

### Sync Response Structure

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

***

## Environment Variables

Injected via `doppler run -p ticktick -c dev`:

| Variable | Purpose | Required For |
|----------|---------|-------------|
| `TICKTICK_ACCESS_TOKEN` | V1 OAuth Bearer token | V1 operations |
| `TICKTICK_USERNAME` | TickTick email | V2 operations |
| `TICKTICK_PASSWORD` | TickTick password | V2 operations |
