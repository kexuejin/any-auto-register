# MoeMail Turnstile Support Design

**Date:** 2026-03-24  
**Status:** Approved

## Context
MoeMail (sall.cc) now enforces Cloudflare Turnstile during registration. Current flow submits an empty `turnstileToken`, causing registration to fail and email generation to return empty/unauthorized.

## Goals
- Keep MoeMail as “zero-config” by automatically solving Turnstile when required.
- Reuse existing `captcha_solver / yescaptcha_key / solver_url` from registration tasks.
- Preserve backward compatibility if Turnstile is not required.

## Non-Goals
- Add a new standalone MoeMail configuration section.
- Change how other providers handle captchas.
- Add full automated tests (no harness exists for MoeMail).

## Selected Approach
- Fetch `https://sall.cc/zh-CN/login` and parse `sitekey` from HTML.
- Use existing captcha solver selection to produce a token:
  - `yescaptcha` → YesCaptcha
  - `local_solver` → Local Solver
  - `manual` → prompt
- Include `turnstileToken` in `/api/auth/register`.
- If `sitekey` is missing or solver fails, surface a clear error and stop registration.

## Architecture
Turnstile solving lives inside `MoeMailMailbox._register_and_login()`. The mailbox receives a `captcha_solver` and `extra` config from the platform task and uses existing `core.base_captcha` helpers.

## Components
- **core/base_mailbox.py**
  - Extend `MoeMailMailbox` to accept `captcha_solver` and `extra`.
  - Parse `sitekey` from login HTML.
  - Call `BaseCaptcha.solve_turnstile()` via the configured solver.
- **core/base_platform.py**
  - Reuse `_make_captcha()` to instantiate solver based on task config.
- **Factory wiring**
  - `create_mailbox()` passes `captcha_solver` and `extra` when provider is `moemail`.

## Data Flow
1. Task config selects captcha solver + credentials.
2. `create_mailbox()` builds MoeMail mailbox with solver config.
3. MoeMail registration fetches login page → parses sitekey.
4. Solver produces token → registration call includes `turnstileToken`.
5. Email generation proceeds normally.

## Error Handling
- If sitekey cannot be parsed: raise with “Turnstile sitekey not found”.
- If solver fails: raise with solver error.
- If Turnstile not required (sitekey absent and registration succeeds): allow flow to continue.

## Testing
- Manual verification:
  - Start solver and run MoeMail registration.
  - Confirm generated email is non-empty.
  - Disable solver and confirm error message is clear.
