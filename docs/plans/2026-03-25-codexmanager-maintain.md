# CodexManager Maintenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a CodexManager background maintainer that periodically removes banned accounts (remote + local) and auto-fills ChatGPT accounts when available count falls below a configured threshold.

**Architecture:** Introduce a `CodexManagerMaintainer` thread started in `main.py` lifespan. It uses a small RPC helper to call `account/list` and `account/delete`, parses configurable filters, and triggers the existing registration workflow with `auto_upload_target=codexmanager` when needed. Configuration is stored in `ConfigStore` and edited via the Settings UI.

**Tech Stack:** FastAPI, SQLModel, curl_cffi, React (Vite), Python threading

---

### Task 1: Add Config Keys For Maintenance

**Files:**
- Modify: `api/config.py`
- Modify: `tests/test_config_keys.py`

**Step 1: Write the failing test**

```python
def test_config_keys_include_expected_keys():
    for key in (
        "codexmanager_maintain_enabled",
        "codexmanager_maintain_interval_secs",
        "codexmanager_min_available",
        "codexmanager_fill_count",
        "codexmanager_banned_filter",
        "codexmanager_available_filter",
    ):
        assert key in CONFIG_KEYS
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_keys.py::test_config_keys_include_expected_keys -v`
Expected: FAIL with missing key in CONFIG_KEYS

**Step 3: Write minimal implementation**

Add the new keys to `CONFIG_KEYS` in `api/config.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_keys.py::test_config_keys_include_expected_keys -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/config.py tests/test_config_keys.py
git commit -m "feat: add codexmanager maintenance config keys"
```

---

### Task 2: Add CodexManager RPC Helper (list/delete)

**Files:**
- Create: `platforms/chatgpt/codexmanager_rpc.py`
- Create: `tests/test_codexmanager_rpc.py`

**Step 1: Write the failing tests**

```python
import json


def test_codexmanager_list_accounts_uses_filter(monkeypatch):
    import platforms.chatgpt.codexmanager_rpc as mod

    seen = {}

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None, impersonate=None):
        seen["url"] = url
        seen["body"] = json
        class Resp:
            status_code = 200
            def json(self):
                return {"result": {"items": [{"id": "1"}]}}
        return Resp()

    monkeypatch.setattr(mod.cffi_requests, "post", fake_post)
    items = mod.list_accounts("active", rpc_url="http://x", rpc_token="t")

    assert seen["body"]["method"] == "account/list"
    assert seen["body"]["params"]["filter"] == "active"
    assert items == [{"id": "1"}]


def test_codexmanager_delete_account_ok(monkeypatch):
    import platforms.chatgpt.codexmanager_rpc as mod

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None, impersonate=None):
        class Resp:
            status_code = 200
            def json(self):
                return {"result": {"ok": True}}
        return Resp()

    monkeypatch.setattr(mod.cffi_requests, "post", fake_post)
    ok = mod.delete_account("acc_1", rpc_url="http://x", rpc_token="t")
    assert ok is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_codexmanager_rpc.py -v`
Expected: FAIL (module or function not found)

**Step 3: Write minimal implementation**

Create `platforms/chatgpt/codexmanager_rpc.py` with:
- URL/token resolution reused from `platforms/chatgpt/codexmanager_upload.py`
- `rpc_call(method, params, ...)`
- `list_accounts(filter, ...)` returning items list
- `delete_account(account_id, ...)` returning ok boolean

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_codexmanager_rpc.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add platforms/chatgpt/codexmanager_rpc.py tests/test_codexmanager_rpc.py
git commit -m "feat: add codexmanager rpc helper"
```

---

### Task 3: Implement CodexManagerMaintainer Core Logic

**Files:**
- Create: `core/codexmanager_maintainer.py`
- Create: `tests/test_codexmanager_maintainer.py`

**Step 1: Write the failing tests**

```python

def test_maintainer_deletes_banned_and_local(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()

    calls = {"deleted": [], "local": []}

    def fake_list(filter_value=None):
        if filter_value == "banned":
            return [
                {"id": "a1", "email": "ban1@example.com"},
                {"id": "a2", "label": "ban2@example.com"},
            ]
        return []

    def fake_delete(account_id):
        calls["deleted"].append(account_id)
        return True

    def fake_local_delete(email):
        calls["local"].append(email)
        return True

    monkeypatch.setattr(maint, "_list_accounts", fake_list)
    monkeypatch.setattr(maint, "_delete_account", fake_delete)
    monkeypatch.setattr(maint, "_delete_local_account", fake_local_delete)
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": True,
        "interval_secs": 7200,
        "min_available": 50,
        "fill_count": 0,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    report = maint.run_once()
    assert calls["deleted"] == ["a1", "a2"]
    assert calls["local"] == ["ban1@example.com", "ban2@example.com"]
    assert report["deleted"] == 2


def test_maintainer_triggers_fill(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()
    calls = {"fill": []}

    monkeypatch.setattr(maint, "_list_accounts", lambda filter_value=None: [{"id": "x"}] if filter_value == "active" else [])
    monkeypatch.setattr(maint, "_delete_account", lambda account_id: True)
    monkeypatch.setattr(maint, "_delete_local_account", lambda email: True)
    monkeypatch.setattr(maint, "_start_register_task", lambda count: calls["fill"].append(count))
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": True,
        "interval_secs": 7200,
        "min_available": 5,
        "fill_count": 0,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    report = maint.run_once()
    assert report["available"] == 1
    assert calls["fill"] == [4]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_codexmanager_maintainer.py -v`
Expected: FAIL (module or methods not found)

**Step 3: Write minimal implementation**

Create `core/codexmanager_maintainer.py`:
- `CodexManagerMaintainer.start()` / `stop()` with background thread
- `run_once()` that:
  - reads config
  - calls `_list_accounts(banned_filter)` and deletes remote + local
  - counts available by union of `available_filters`
  - triggers `_start_register_task(need)` if below threshold
- `_read_config()` uses `config_store` with defaults and parsing
- `_start_register_task()` uses `api.tasks.RegisterTaskRequest` + `_run_register` (or a helper) with `auto_upload_target="codexmanager"`
- `_delete_local_account()` uses SQLModel Session to delete matching `platform="chatgpt"` by email

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_codexmanager_maintainer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/codexmanager_maintainer.py tests/test_codexmanager_maintainer.py
git commit -m "feat: add codexmanager maintainer core"
```

---

### Task 4: Wire Maintainer Into App Lifecycle

**Files:**
- Modify: `main.py`
- Modify: `tests/test_codexmanager_maintainer.py`

**Step 1: Write the failing test**

```python
def test_maintainer_start_stop(monkeypatch):
    import main

    calls = {"start": 0, "stop": 0}

    class FakeMaintainer:
        def start(self):
            calls["start"] += 1
        def stop(self):
            calls["stop"] += 1

    monkeypatch.setattr(main, "codexmanager_maintainer", FakeMaintainer())
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_codexmanager_maintainer.py::test_maintainer_start_stop -v`
Expected: FAIL (attribute not found)

**Step 3: Write minimal implementation**

- Instantiate a global `codexmanager_maintainer` in `main.py`.
- In `lifespan`, call `.start()` at startup and `.stop()` at shutdown.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_codexmanager_maintainer.py::test_maintainer_start_stop -v`
Expected: PASS

**Step 5: Commit**

```bash
git add main.py tests/test_codexmanager_maintainer.py
git commit -m "feat: start codexmanager maintainer on startup"
```

---

### Task 5: Update Settings UI (CodexManager Card)

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

**Step 1: Add UI fields**

Add fields under ChatGPT → CodexManager section:
- `codexmanager_maintain_enabled`
- `codexmanager_maintain_interval_secs`
- `codexmanager_min_available`
- `codexmanager_fill_count`
- `codexmanager_banned_filter`
- `codexmanager_available_filter`

**Step 2: Manual check**

Run: `cd frontend && npm run build`
Expected: Build succeeds and `static/` updated.

**Step 3: Commit**

```bash
git add frontend/src/pages/Settings.tsx static
# if static updated in this repo
git commit -m "feat: add codexmanager maintenance settings"
```

---

### Task 6: Full Test Pass

**Step 1: Run full test suite**

Run: `pytest`
Expected: PASS

**Step 2: Commit (if any remaining changes)**

```bash
git add -A
git commit -m "test: verify codexmanager maintenance"
```
