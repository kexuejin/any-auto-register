---
title: Mail Provider UI Conditional Fields
date: 2026-03-24
status: approved
---

# Overview
Unify mail provider configuration rendering in the frontend by introducing a shared provider schema and only displaying the configuration fields required by the currently selected provider. Apply this to both the Register page and the Settings page.

# Goals
- Add `chuleicn` and `domain_imap` providers to the UI.
- Show only the selected provider’s fields (no mixed/always-visible sections).
- Keep payloads backward-compatible by still submitting all `extra` keys.
- Eliminate duplicated provider field definitions between Register and Settings.

# Non-Goals
- Backend changes or validation rules.
- Changing how providers are executed or stored.
- Refactoring unrelated settings UI.

# Approach (Shared Schema)
Create a shared module (e.g., `frontend/src/lib/mailProviders.ts`) that exports:
- `MAIL_PROVIDER_OPTIONS` for select controls.
- `MAIL_PROVIDER_META` for section titles/descriptions.
- `MAIL_PROVIDER_FIELDS` for per-provider field definitions.

Both `Register.tsx` and `Settings.tsx` will render provider-specific fields by reading from this schema.

# UI/UX Behavior
## Register
- Mail provider select uses `MAIL_PROVIDER_OPTIONS`.
- Only the chosen provider’s fields are rendered.
- `extra` includes all provider keys to keep server compatibility.

## Settings
- Mail provider select uses `MAIL_PROVIDER_OPTIONS`.
- “邮箱服务” tab shows the default provider selector plus **only** the selected provider’s config section.
- Field component supports type/option metadata for provider-specific inputs (e.g., `domain_imap_use_tls`).

# Provider Field Definitions
Include existing providers plus new ones:
- `chuleicn`: `chuleicn_api_url`, `chuleicn_password`, `chuleicn_domain`.
- `domain_imap`: `domain_imap_host`, `domain_imap_port`, `domain_imap_user`, `domain_imap_pass`, `domain_imap_use_tls`, `domain_imap_proxy`, `domain_catchall_domain`.

# Data Flow
- Register form state includes all provider keys.
- Register submit sends `extra` with all provider keys.
- Settings loads `/config`, renders only the selected provider’s fields, and saves via `/config`.

# Error Handling & Validation
- Keep existing behavior (no extra validation in UI).
- Use placeholders and defaults where appropriate (e.g., IMAP port 993, TLS default true).

# Testing
- Manual UI check: switch providers in Register/Settings; confirm only relevant fields show.
- Ensure `chuleicn` / `domain_imap` options appear in both pages.
