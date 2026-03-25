# ChatGPT Menu CodexManager Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a ChatGPT account menu action that uploads to CodexManager using the same config/token resolution as the registration dropdown.

**Architecture:** Extend the ChatGPT platform action list with a new `upload_codexmanager` action and handle it in `execute_action` by calling the existing CodexManager uploader. The frontend already renders actions dynamically from the API, so no UI changes are required.

**Tech Stack:** FastAPI, Python, pytest.

---

### Task 1: Add failing tests for CodexManager action

**Files:**
- Create: `tests/test_chatgpt_actions.py`

**Step 1: Write the failing test**

```python
from platforms.chatgpt.plugin import ChatGPTPlatform
from core.base_platform import RegisterConfig, Account, AccountStatus


def test_chatgpt_actions_include_codexmanager():
    platform = ChatGPTPlatform(config=RegisterConfig())
    actions = platform.get_platform_actions()
    ids = [a["id"] for a in actions]
    assert "upload_codexmanager" in ids


def test_execute_action_upload_codexmanager(monkeypatch):
    platform = ChatGPTPlatform(config=RegisterConfig())

    called = {"ok": False}

    def _fake_upload(account):
        called["ok"] = True
        return True, "ok"

    import platforms.chatgpt.codexmanager_upload as mod
    monkeypatch.setattr(mod, "upload_to_codexmanager", _fake_upload)

    acc = Account(
        platform="chatgpt",
        email="a@example.com",
        password="x",
        token="tok",
        status=AccountStatus.REGISTERED,
        extra={},
    )

    result = platform.execute_action("upload_codexmanager", acc, {})
    assert called["ok"] is True
    assert result["ok"] is True
    assert result["data"] == "ok"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chatgpt_actions.py::test_chatgpt_actions_include_codexmanager -v`

Expected: FAIL with missing action id.

**Step 3: Commit**

```bash
git add tests/test_chatgpt_actions.py
git commit -m "test: add failing tests for codexmanager action"
```

---

### Task 2: Implement CodexManager action

**Files:**
- Modify: `platforms/chatgpt/plugin.py`
- Test: `tests/test_chatgpt_actions.py`

**Step 1: Write minimal implementation**

```python
# In get_platform_actions()
{
    "id": "upload_codexmanager",
    "label": "上传 CodexManager",
    "params": [],
},

# In execute_action()
elif action_id == "upload_codexmanager":
    from platforms.chatgpt.codexmanager_upload import upload_to_codexmanager
    ok, msg = upload_to_codexmanager(account)
    return {"ok": ok, "data": msg}
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_chatgpt_actions.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add platforms/chatgpt/plugin.py tests/test_chatgpt_actions.py
git commit -m "feat: add codexmanager upload action"
```

---

### Task 3: Full test run

**Files:**
- None

**Step 1: Run full tests**

Run: `PYTHONPATH=. pytest`

Expected: PASS (all tests)

**Step 2: Commit (if needed)**

```bash
# No code changes expected
```
