# IMAP Subdomain Support Design

**Date:** 2026-03-24  
**Status:** Approved

## Context
Domain IMAP catch-all currently generates `local@domain_catchall_domain`. We need to support:
- Manual subdomains (user enters `sub.example.com` directly).
- Optional auto-random subdomain (letters-only), length 2–4 with default 2.

## Goals
- Add opt-in dynamic subdomain generation for IMAP catch-all emails.
- Preserve existing behavior when the feature is off.
- Expose controls in Settings and Register UI.

## Non-Goals
- Domain format validation or normalization.
- Changes to IMAP login or message parsing.
- Adding automated tests where no test harness exists.

## Selected Approach
**Option 1 (toggle + length)**
- Add config keys:
  - `domain_imap_use_dynamic_subdomain` (bool)
  - `domain_imap_subdomain_length` (number; 2–4, default 2)
- When enabled, generate `letters-only` subdomain and prepend to `domain_catchall_domain`.
- When disabled, use `domain_catchall_domain` as-is (manual subdomain allowed).

## Architecture
Subdomain generation happens inside `DomainImapMailbox.get_email()`. This centralizes the behavior in a single place used by all registration flows. UI and config only feed parameters; IMAP receiving remains unchanged.

## Components
- **Backend config**: `api/config.py` allowlist includes new keys.
- **Mailbox**: `core/base_mailbox.py` `DomainImapMailbox.get_email()` adds subdomain generation.
- **Frontend**: `frontend/src/lib/mailProviders.ts` adds fields; `Register` and `Settings` display them automatically.

## Data Flow
1. User selects `Domain IMAP` and enters `domain_catchall_domain`.
2. If dynamic subdomain is enabled:
   - Generate `subdomain` with `[a-z]`, length N (2–4, default 2).
   - `effective_domain = f"{subdomain}.{domain_catchall_domain}"`
3. Else:
   - `effective_domain = domain_catchall_domain` (unchanged).
4. Email becomes `local@effective_domain` and is used for IMAP filtering as before.

## Error Handling
- If `domain_catchall_domain` is empty, raise existing error.
- If length invalid or missing, fall back to 2.
- No extra domain validation (keeps backward compatibility).

## Backward Compatibility
- Default behavior unchanged unless dynamic subdomain is explicitly enabled.
- Manual subdomain input remains supported.

## Testing
- Manual verification:
  - Enable dynamic subdomain and confirm generated domain format.
  - Disable and ensure domain remains unchanged.
  - Try a manual subdomain and confirm `rand.sub.example.com` when enabled.
