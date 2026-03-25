# IMAP Subdomain Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add optional dynamic IMAP subdomain generation (letters-only, length 2–4 default 2) while preserving manual subdomain behavior.

**Architecture:** Extend Domain IMAP mailbox creation with a toggle + length config. When enabled, `get_email()` prepends a random subdomain to `domain_catchall_domain`. UI exposes the two new fields and API config allowlists them.

**Tech Stack:** Python (core mailboxes), FastAPI (config), React + TypeScript (frontend forms)

---

### Task 1: Allow new IMAP config keys

**Files:**
- Modify: `api/config.py`

**Step 1: Write the failing test**

Skip — no existing test harness for config allowlist.

**Step 2: Add new config keys**

Add:
- `domain_imap_use_dynamic_subdomain`
- `domain_imap_subdomain_length`

to `CONFIG_KEYS` in `api/config.py`.

**Step 3: Run test to verify it fails**

Skip — no test target.

**Step 4: Commit**

```bash
git add api/config.py
git commit -m "feat: allow IMAP subdomain config keys"
```

---

### Task 2: Implement dynamic subdomain generation

**Files:**
- Modify: `core/base_mailbox.py`

**Step 1: Write the failing test**

Skip — no IMAP unit test suite available.

**Step 2: Pass new options from factory**

In `create_mailbox()` when provider is `domain_imap`, pass:
- `use_dynamic_subdomain` from `extra["domain_imap_use_dynamic_subdomain"]`
- `subdomain_length` from `extra["domain_imap_subdomain_length"]`

Parse boolean consistently with existing `domain_imap_use_tls`.

**Step 3: Extend DomainImapMailbox init**

Add fields:
- `use_dynamic_subdomain: bool`
- `subdomain_length: int`

Store them on `self`.

**Step 4: Generate effective domain in get_email()**

Logic:
- Resolve base domain from `self.domain` or user’s email domain (existing behavior).
- If `use_dynamic_subdomain`:
  - Clamp length to 2–4, fallback to 2.
  - Generate `letters-only` subdomain.
  - `effective_domain = f"{sub}.{base_domain}"`
- Else use `base_domain` as-is.
- Generate local part as today and return `local@effective_domain`.

**Step 5: Run test to verify it passes**

Skip — no test target.

**Step 6: Commit**

```bash
git add core/base_mailbox.py
git commit -m "feat: add IMAP dynamic subdomain generation"
```

---

### Task 3: Expose fields in UI

**Files:**
- Modify: `frontend/src/lib/mailProviders.ts`
- Modify: `frontend/src/pages/Register.tsx`

**Step 1: Write the failing test**

Skip — no frontend test harness.

**Step 2: Add provider fields**

In `MAIL_PROVIDER_FIELDS.domain_imap`, add:
- `domain_imap_use_dynamic_subdomain` (select: true/false)
- `domain_imap_subdomain_length` (number; placeholder `2`)

**Step 3: Add Register defaults**

In `Register` form state, add:
- `domain_imap_use_dynamic_subdomain: 'false'`
- `domain_imap_subdomain_length: 2`

**Step 4: Run test to verify it passes**

Skip — no test target.

**Step 5: Commit**

```bash
git add frontend/src/lib/mailProviders.ts frontend/src/pages/Register.tsx
git commit -m "feat: expose IMAP subdomain fields in UI"
```
