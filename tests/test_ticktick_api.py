"""Behavioural regression tests for TickTickAPI.

These exercise the public methods (search_tasks, list_projects, ...) with the
network boundary (urllib.request.urlopen) mocked, so they run offline and pin
the bug fixes documented alongside them.
"""
import io
import json
import urllib.error
from datetime import datetime, timezone

import pytest

import ticktick_api
from ticktick_api import TickTickAPI


class _FakeHeaders:
    def get_all(self, key):
        return []


class _FakeResp:
    """Minimal stand-in for the urlopen context-manager response."""

    def __init__(self, body, headers=None):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = headers or _FakeHeaders()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _api_no_login():
    """Build a TickTickAPI instance without doing a real network login."""
    api = TickTickAPI.__new__(TickTickAPI)
    api.session_token = "session"
    api.csrf_token = None
    api.inbox_id = ""
    api._device_id = "65a0test"
    api._sync_cache = None
    api._sync_cache_time = 0
    api._username = "user@example.com"
    api._password = "pw"
    return api


# ── Cycle 1: search must tolerate null content/desc ──────────────────────
def test_search_ignores_tasks_with_null_content(monkeypatch):
    api = _api_no_login()
    monkeypatch.setattr(api, "sync", lambda *a, **k: {
        "syncTaskBean": {"update": [
            {"id": "1", "title": "groceries", "content": None, "desc": None},
        ]},
    })
    # The query lives nowhere; title doesn't match, content/desc are null.
    # Must return [] rather than crash on None.lower().
    assert api.search_tasks("needle", include_completed=False) == []


# ── Cycle 2: connection-level failures go through the error path ─────────
def test_network_error_goes_through_error_path(monkeypatch):
    api = _api_no_login()
    monkeypatch.setattr(ticktick_api, "_error_exit",
                        lambda msg: (_ for _ in ()).throw(RuntimeError(msg)))
    monkeypatch.setattr(ticktick_api.time, "sleep", lambda *_: None)  # skip retry backoff

    def boom(*a, **k):
        raise urllib.error.URLError("connection timed out")

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", boom)
    # A network/timeout failure must surface via the library's error path
    # (so the backend maps it to a clean 502), not leak as a raw URLError.
    with pytest.raises(RuntimeError) as ei:
        api.list_projects()  # → sync → _request → urlopen
    assert "逾時" in str(ei.value) or "連線" in str(ei.value)


# ── Cycle 3: every network call is bounded by a timeout ─────────────────
def test_login_is_bounded_by_a_timeout(monkeypatch):
    api = TickTickAPI.__new__(TickTickAPI)
    api._device_id = "65a0test"
    api.session_token = None
    api.csrf_token = None
    api.inbox_id = None
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp(json.dumps({"token": "tok", "inboxId": "ib"}))

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    api._login("user@example.com", "pw")
    assert api.session_token == "tok"
    # login must not be able to hang forever
    assert captured["timeout"] and captured["timeout"] > 0


# ── Cycle 4: an expired session re-logs-in and retries transparently ────
def test_expired_session_triggers_relogin_and_retry(monkeypatch):
    api = _api_no_login()
    api.session_token = "expired"
    calls = {"data": 0, "login": 0}

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/user/sign" in url:
            calls["login"] += 1
            return _FakeResp(json.dumps({"token": "fresh-token", "inboxId": "ib"}))
        calls["data"] += 1
        if calls["data"] == 1:
            raise urllib.error.HTTPError(
                url, 401, "Unauthorized", {}, io.BytesIO(b'{"errorId":"not_login"}'))
        return _FakeResp(json.dumps({"projectProfiles": [{"id": "p1"}]}))

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    # sync → _request gets 401 → should re-login once and retry, returning data.
    projects = api.list_projects()
    assert projects == [{"id": "p1"}]
    assert calls["login"] == 1
    assert api.session_token == "fresh-token"


# ── Cycle A: move tasks between projects (batch/taskProject) ────────────
def test_move_task_posts_to_taskProject(monkeypatch):
    api = _api_no_login()
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp("{}")

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    api.move_task("T1", "P_from", "P_to")
    assert captured["url"].endswith("/batch/taskProject")
    assert captured["body"] == [
        {"fromProjectId": "P_from", "taskId": "T1", "toProjectId": "P_to"}]


def test_move_all_moves_every_task_in_project(monkeypatch):
    api = _api_no_login()
    monkeypatch.setattr(api, "sync", lambda *a, **k: {"syncTaskBean": {"update": [
        {"id": "t1", "projectId": "P_from"}, {"id": "t2", "projectId": "P_from"}]}})
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp("{}")

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    api.move_all("P_from", "P_to")
    assert [m["taskId"] for m in captured["body"]] == ["t1", "t2"]
    assert all(m["fromProjectId"] == "P_from" and m["toProjectId"] == "P_to"
               for m in captured["body"])


# ── Cycle B: make a task a subtask of another (batch/taskParent) ────────
def test_make_subtask_posts_to_taskParent(monkeypatch):
    api = _api_no_login()
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp("{}")

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    api.make_subtask("CHILD", "PARENT", "P1")
    assert captured["url"].endswith("/batch/taskParent")
    assert captured["body"] == [
        {"parentId": "PARENT", "projectId": "P1", "taskId": "CHILD"}]


# ── Cycle C: transient 5xx / network errors are retried with backoff ────
def test_request_retries_on_5xx_then_succeeds(monkeypatch):
    api = _api_no_login()
    monkeypatch.setattr(ticktick_api.time, "sleep", lambda *_: None)  # no real delay
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b"busy"))
        return _FakeResp(json.dumps({"projectProfiles": [{"id": "p1"}]}))

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    assert api.list_projects() == [{"id": "p1"}]
    assert calls["n"] == 2  # one transient failure, then success


def test_request_does_not_retry_4xx(monkeypatch):
    api = _api_no_login()
    api._username = None  # disable relogin path so 401/4xx goes straight to error
    monkeypatch.setattr(ticktick_api, "_error_exit",
                        lambda msg: (_ for _ in ()).throw(RuntimeError(msg)))
    monkeypatch.setattr(ticktick_api.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {}, io.BytesIO(b"nope"))

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError):
        api.list_projects()
    assert calls["n"] == 1  # 4xx is not transient — no retry


# ── Cycle D: tag/habit colors are validated before hitting the network ──
def test_create_tag_rejects_invalid_hex_color(monkeypatch):
    api = _api_no_login()
    monkeypatch.setattr(ticktick_api, "_error_exit",
                        lambda msg: (_ for _ in ()).throw(RuntimeError(msg)))
    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network reached")))
    with pytest.raises(RuntimeError) as ei:
        api.create_tag("work", color="blue")
    assert "color" in str(ei.value).lower() or "顏色" in str(ei.value)


def test_create_tag_accepts_valid_hex_color(monkeypatch):
    api = _api_no_login()
    captured = {}

    def fake(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp("{}")

    monkeypatch.setattr(ticktick_api.urllib.request, "urlopen", fake)
    api.create_tag("work", color="#FF5733")
    assert captured["body"]["add"][0]["color"] == "#FF5733"


# ── Cycle E: datetime → TickTick date string (offset with NO colon) ─────
def test_to_ticktick_date_local_zone_offset_has_no_colon():
    dt = datetime(2026, 6, 20, 8, 30, 0)  # naive, interpreted in the given zone
    assert ticktick_api.to_ticktick_date(dt, "Asia/Taipei") == "2026-06-20T08:30:00+0800"


def test_to_ticktick_date_utc_default():
    dt = datetime(2026, 6, 20, 1, 56, 7, tzinfo=timezone.utc)
    assert ticktick_api.to_ticktick_date(dt) == "2026-06-20T01:56:07+0000"


def test_to_ticktick_date_converts_aware_dt_into_target_zone():
    dt = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)  # 00:00 UTC
    # → 08:00 in Taipei (+0800)
    assert ticktick_api.to_ticktick_date(dt, "Asia/Taipei") == "2026-06-20T08:00:00+0800"
