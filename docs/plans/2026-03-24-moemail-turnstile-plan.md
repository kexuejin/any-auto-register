# MoeMail Turnstile Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically solve MoeMail Turnstile during registration using the task’s configured captcha solver so MoeMail remains zero-config.

**Architecture:** Extend `MoeMailMailbox` to fetch the login page, parse the Turnstile sitekey, solve via existing captcha providers, and submit the token on registration. Wire solver config through the mailbox factory from registration tasks.

**Tech Stack:** Python (core mailbox), requests, existing captcha providers (YesCaptcha / Local Solver / Manual)

---

### Task 1: Wire captcha configuration into MoeMail mailbox

**Files:**
- Modify: `core/base_mailbox.py`

**Step 1: Write the failing test**

Skip — no unit test harness for MoeMail.

**Step 2: Extend MoeMailMailbox init**

Add optional parameters:
- `captcha_solver: str`
- `extra: dict`

Store on `self` for later use.

**Step 3: Add Turnstile sitekey parsing**

Add a helper to fetch `https://sall.cc/zh-CN/login` (via session) and parse:
- Prefer `data-sitekey="..."` if present
- Fallback to regex `0x[a-zA-Z0-9]{15,}` from HTML

**Step 4: Solve Turnstile**

Implement a helper that instantiates a solver using:
- `yescaptcha` → `YesCaptcha(extra["yescaptcha_key"])`
- `local_solver` → `LocalSolverCaptcha(extra["solver_url"])`
- `manual` → `ManualCaptcha()`

Call `solve_turnstile(login_url, sitekey)` and return token.

**Step 5: Use token in registration**

In `_register_and_login()`:
- If sitekey found → must solve token; on failure raise clear error.
- If sitekey not found → proceed with empty token (compat).
- Submit `turnstileToken` in `/api/auth/register`.
- If response indicates Turnstile required and token empty → raise clear error.

**Step 6: Run test to verify it passes**

Skip — no test target.

**Step 7: Commit**

```bash
git add core/base_mailbox.py
git commit -m "feat: solve moemail turnstile during register"
```

---

### Task 2: Pass captcha solver config into mailbox factory

**Files:**
- Modify: `core/base_mailbox.py`
- Modify: `api/tasks.py`

**Step 1: Write the failing test**

Skip — no test harness.

**Step 2: Extend create_mailbox signature**

Add `captcha_solver: str | None = None` and pass to `MoeMailMailbox` along with `extra`.

**Step 3: Pass solver config from task**

In `api/tasks.py`, when calling `create_mailbox`, pass:
- `captcha_solver=req.captcha_solver`

**Step 4: Run test to verify it passes**

Skip — no test target.

**Step 5: Commit**

```bash
git add core/base_mailbox.py api/tasks.py
git commit -m "feat: pass captcha config to moemail mailbox"
```
