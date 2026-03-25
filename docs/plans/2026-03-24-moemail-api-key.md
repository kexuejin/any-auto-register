# MoeMail API Key Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add optional MoeMail API Key mode that bypasses registration when `moemail_api_key` is configured.

**Architecture:** Thread `moemail_api_key` through config/UI into `MoeMailMailbox`. If key exists, call `/api/config` and `/api/emails/generate` with `X-API-Key`; otherwise keep the existing register + Turnstile flow.

**Tech Stack:** Python (FastAPI), React (Vite), existing mailbox abstraction.

---

### Task 1: Expose `moemail_api_key` in config + UI

**Files:**
- Modify: `api/config.py`
- Modify: `frontend/src/lib/mailProviders.ts`
- Modify: `frontend/src/pages/Register.tsx`

**Step 1: Write the failing test**

Skip — no unit test harness for frontend/config wiring.

**Step 2: Run test to verify it fails**

Skip.

**Step 3: Write minimal implementation**

- Add `moemail_api_key` to `CONFIG_KEYS`.
- Add MoeMail field in `MAIL_PROVIDER_FIELDS` as secret input.
- Add `moemail_api_key` to Register form defaults and submitted `extra`.

**Step 4: Run test to verify it passes**

Run: `pytest -q`  
Expected: PASS (no backend regressions).

**Step 5: Commit**

```bash
git add api/config.py frontend/src/lib/mailProviders.ts frontend/src/pages/Register.tsx
git commit -m "feat: add moemail api key config"
```

---

### Task 2: Add MoeMail API Key mailbox flow

**Files:**
- Modify: `core/base_mailbox.py`

**Step 1: Write the failing test**

Skip — no MoeMail test harness available.

**Step 2: Run test to verify it fails**

Skip.

**Step 3: Write minimal implementation**

- Pass `moemail_api_key` from `create_mailbox()` to `MoeMailMailbox`.
- In `MoeMailMailbox`:
  - Accept `api_key` and store it.
  - If `api_key` present, use `X-API-Key` headers for:
    - `GET /api/config` (domain list)
    - `POST /api/emails/generate`
    - `GET /api/emails/{emailId}` and message fetch
  - Keep current register/Turnstile flow for non-key mode.
  - Improve response parsing to tolerate `emailDomains` as list or comma string, and message lists in different keys.
  - Raise explicit errors when API key mode returns non-2xx or missing `email/id`.

**Step 4: Run test to verify it passes**

Run: `pytest -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add core/base_mailbox.py
git commit -m "feat: support moemail api key mode"
```

---

### Task 3: Final verification

**Files:**
- None

**Step 1: Run full test suite**

Run: `pytest -q`  
Expected: PASS (6 passed, 1 skipped).

**Step 2: Commit**

Skip — no code changes.
