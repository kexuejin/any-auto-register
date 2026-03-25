# CodexManager Run-Now Maintenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an “立即检查” button in Settings that triggers a one-off CodexManager full maintenance run (cleanup banned + count available + fill) even when the scheduled maintainer is disabled.

**Architecture:** Expose a small backend API endpoint that calls `CodexManagerMaintainer` with `force=True` and uses the existing non-blocking lock to return `busy` when a run is already in progress. Frontend calls the endpoint and displays toast feedback.

**Tech Stack:** FastAPI, Python threads, React + TypeScript (Vite), existing `apiFetch`.

---

### Task 1: Backend — Add Run-Now API (Busy + Forced)

**Files:**
- Modify: `core/codexmanager_maintainer.py`
- Create: `api/codexmanager.py`
- Modify: `main.py`
- Test: `tests/test_codexmanager_maintainer.py`

**Step 1: Write failing tests**

Add tests:
- When maintainer disabled in config, `run_once(force=True)` still runs list/delete/list flow and returns report.
- When lock is held, API returns `{ok:false,error:"busy"}`.

Example skeleton:

```python
def test_run_once_force_ignores_enabled(monkeypatch):
    # monkeypatch config_store.get_all to return maintain_enabled false
    # monkeypatch rpc.list_accounts/delete_account to deterministic fakes
    # assert report contains expected available/deleted/fill and no skipped
    ...
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest -q tests/test_codexmanager_maintainer.py`
Expected: FAIL (no force mode / no API)

**Step 3: Implement minimal backend changes**

1. In `core/codexmanager_maintainer.py`:
   - Change signature to `run_once(self, force: bool = False) -> dict`.
   - If `not force` and `enabled` is false, keep current behavior (skipped).
   - If `force` is true, ignore enabled check.
   - Add helper `try_run_now(self) -> tuple[bool, dict|None, str|None]` that does:
     - try acquire lock non-blocking
     - if fail: return (False, None, "busy")
     - else: run `run_once(force=True)` and release lock

2. Create `api/codexmanager.py` with router:

```python
from fastapi import APIRouter
from main import codexmanager_maintainer

router = APIRouter(prefix="/codexmanager", tags=["codexmanager"])

@router.post("/maintain/run")
def maintain_run_now():
    ok, report, err = codexmanager_maintainer.try_run_now()
    if not ok:
        return {"ok": False, "error": err or "failed"}
    if report.get("error"):
        return {"ok": False, "error": report.get("error")}
    return {"ok": True, "forced": True, "report": report}
```

3. In `main.py`: include router: `app.include_router(codexmanager_router, prefix="/api")`.

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest -q tests/test_codexmanager_maintainer.py`
Expected: PASS

**Step 5: Commit**

```bash
git add core/codexmanager_maintainer.py api/codexmanager.py main.py tests/test_codexmanager_maintainer.py
git commit -m "feat: add codexmanager run-now maintenance endpoint"
```

---

### Task 2: Frontend — Add “立即检查” Button + Toast

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Test: `frontend/src/pages/__tests__/settings-codexmanager.test.tsx`

**Step 1: Write failing test**

Extend existing test to assert the button exists in the CodexManager section:

```tsx
expect(await screen.findByRole('button', { name: '立即检查' })).toBeInTheDocument()
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL (button missing)

**Step 3: Implement minimal UI**

- Add local state in `Settings` for `maintainRunning` and toast.
- In CodexManager section header row, render a small button `立即检查`.
- On click: call `apiFetch('/codexmanager/maintain/run', { method: 'POST' })`.
- Handle responses:
  - ok: toast success with report numbers
  - error == busy: toast error “执行中/忙”
  - other: toast error

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/pages/__tests__/settings-codexmanager.test.tsx
git commit -m "feat: add CodexManager run-now button"
```

---

### Task 3: Build Static Assets

**Files:**
- Modify: `static/index.html`
- Modify: `static/assets/*`

**Step 1: Build**

Run: `cd frontend && npm run build`
Expected: PASS

**Step 2: Commit**

```bash
git add -f static
git commit -m "build: update static assets for run-now button"
```

---

### Task 4: Manual Verification

1. Restart backend.
2. Open `http://127.0.0.1:8000/settings` hard refresh.
3. In ChatGPT -> CodexManager, click `立即检查`.
4. Expect toast with counts or busy.
