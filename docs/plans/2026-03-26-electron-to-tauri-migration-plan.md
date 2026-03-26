# Electron -> Tauri Migration Implementation Plan (Windows + macOS)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Electron shell with a Tauri shell to reduce installer size, while keeping the existing FastAPI-served UI (`http://127.0.0.1:8000`) and PyInstaller backend executable as a bundled sidecar.

**Architecture:** Tauri (Rust) owns the app lifecycle: spawn the backend sidecar, wait for a health check, then open a window pointing to the backend URL. The web UI remains unchanged and does not require Tauri IPC permissions.

**Tech Stack:** Tauri v2, Rust, system WebView (WKWebView/WebView2), PyInstaller backend executable, Windows NSIS installer.

---

## Constraints / Non-Goals

- No business logic changes in `frontend/` or the Python backend.
- Keep the UI delivery model: backend serves SPA + API on port `8000`.
- No macOS signing/notarization (internal usage).
- Windows should prefer minimal bundle size: do not embed WebView2 runtime (use download bootstrapper mode).

## Current State (Reference)

- Electron shell logic: `electron/main.js`
- Electron bundling: `electron/electron-builder.yml` + `extraResources: backend/**`
- Backend build: `electron/build-backend.sh` produces `electron/backend/backend` (~74MB).

## Decisions (Recommended Defaults)

- Tauri window loads `http://127.0.0.1:8000` (prefer IP over `localhost`).
- Backend port stays `8000` for parity (later improvement: dynamic port).
- Backend sidecar path is resolved via Tauri sidecar facilities, not hard-coded.
- macOS: build and ship two separate artifacts:
  - `aarch64-apple-darwin` (Apple Silicon)
  - `x86_64-apple-darwin` (Intel)

---

### Task 1: Create Tauri Shell Skeleton

**Files:**
- Create: `src-tauri/`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/tauri.conf.json` (or update if generated elsewhere)

**Step 1: Initialize Tauri project**

Run (one of the standard init flows):

```bash
# Option A (if tauri-cli is available)
cargo tauri init

# Option B (if using npm scaffolding)
# npm create tauri-app@latest
```

Expected: `src-tauri/` with a minimal app that can run.

**Step 2: Run dev build**

Run: `cargo tauri dev`

Expected: app window opens.

**Step 3: Commit**

```bash
git add src-tauri
git commit -m "chore(tauri): initialize shell project"
```

---

### Task 2: Define Sidecar Binary Layout (Tauri externalBin)

**Files:**
- Create: `src-tauri/binaries/` (directory)
- Modify: `src-tauri/tauri.conf.json`

**Step 1: Add externalBin configuration**

Set:
- `bundle.externalBin = ["binaries/backend"]`

Note: Tauri will look for `backend-$TARGET_TRIPLE[.exe]`.

**Step 2: Commit**

```bash
git add src-tauri/tauri.conf.json src-tauri/binaries
git commit -m "chore(tauri): configure backend sidecar externalBin"
```

---

### Task 3: Implement Backend Spawn + Health Check in Rust

**Files:**
- Modify: `src-tauri/src/main.rs`

**Step 1: Implement backend spawning**

Behavior parity with `electron/main.js`:
- In production (packaged), spawn backend sidecar.
- Set env:
  - `PORT=8000`
  - `AAR_DATA_DIR=<tauri app data dir>`
- Set `current_dir` to the directory containing the sidecar (or an equivalent stable location).
- Capture stdout/stderr for debugging.

**Step 2: Implement backend readiness wait**

Poll: `GET http://127.0.0.1:8000/api/platforms`
- Retry ~30 times with 1s delay.
- Resolve when status code < 500.
- On timeout: show a dialog and exit.

**Step 3: Implement shutdown cleanup**

- On app exit, kill backend child process if present.

**Step 4: Commit**

```bash
git add src-tauri/src/main.rs
git commit -m "feat(tauri): spawn backend sidecar and wait for readiness"
```

---

### Task 4: Point Window at Backend URL (No UI Changes)

**Files:**
- Modify: `src-tauri/src/main.rs`

**Step 1: Load URL**

Ensure the main window loads:
- `http://127.0.0.1:8000`

**Step 2: Validate no Tauri IPC needed**

Do not introduce `invoke` calls from the web UI (avoid remote capabilities complexity).

**Step 3: Commit**

```bash
git add src-tauri/src/main.rs
git commit -m "feat(tauri): load UI from local backend URL"
```

---

### Task 5: Add Backend Build Output Copying into `src-tauri/binaries/`

**Files:**
- Create: `scripts/build-backend-mac.sh`
- Create: `scripts/build-backend-win.ps1` (or `.bat`)
- (Optionally) Modify: `electron/build-backend.sh` to share logic

**Step 1: mac script**

- Build backend (PyInstaller) on mac.
- Determine triple: `rustc --print host-tuple` (fallback: parse `rustc -Vv`).
- Copy output to: `src-tauri/binaries/backend-$TRIPLE`

**Step 2: Windows script**

- Build backend on Windows (PyInstaller).
- Determine triple.
- Copy output to: `src-tauri/binaries/backend-$TRIPLE.exe`

**Step 3: Commit**

```bash
git add scripts
git commit -m "chore(build): copy pyinstaller backend into tauri sidecar binaries"
```

---

### Task 6: Windows Installer Settings (NSIS + WebView2 Download Bootstrapper)

**Files:**
- Modify: `src-tauri/tauri.conf.json`

**Step 1: Ensure NSIS target**

Configure Windows bundling to produce NSIS `-setup.exe` installer (as desired).

**Step 2: Ensure WebView2 install mode is minimal**

Set `bundle.windows.webviewInstallMode.type = "downloadBootstrapper"`.

**Step 3: Build on Windows**

Run:

```bash
# Ensure sidecar exists: src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe
cargo tauri build
```

Expected: NSIS installer produced.

**Step 4: Commit**

```bash
git add src-tauri/tauri.conf.json
git commit -m "chore(windows): nsis bundling and minimal webview2 install mode"
```

---

### Task 7: macOS Builds (Two Architectures)

**Files:**
- None (process + CI)

**Step 1: Build Apple Silicon artifact**

On Apple Silicon machine/runner:

```bash
./scripts/build-backend-mac.sh
cargo tauri build --target aarch64-apple-darwin
```

Expected: `.app` / `.dmg` for aarch64.

**Step 2: Build Intel artifact**

On Intel machine/runner:

```bash
./scripts/build-backend-mac.sh
cargo tauri build --target x86_64-apple-darwin
```

Expected: `.app` / `.dmg` for x86_64.

---

### Task 8: Add CI (Optional But Strongly Recommended)

**Files:**
- Create: `.github/workflows/build-tauri-mac-aarch64.yml`
- Create: `.github/workflows/build-tauri-mac-x86_64.yml`
- Create: `.github/workflows/build-tauri-win.yml`

**Step 1: mac aarch64 workflow**

- Checkout
- Setup Python + install deps
- Run `scripts/build-backend-mac.sh`
- Setup Rust toolchain + Tauri prerequisites
- Run `cargo tauri build --target aarch64-apple-darwin`
- Upload artifacts

**Step 2: mac x86_64 workflow**

Same as above with `--target x86_64-apple-darwin`.

**Step 3: Windows workflow**

- Checkout
- Setup Python + install deps
- Run Windows backend build script
- Setup Rust toolchain
- Run `cargo tauri build`
- Upload artifacts

**Step 4: Commit**

```bash
git add .github/workflows
git commit -m "ci: build tauri installers for windows and mac (two arch)"
```

---

## Verification Checklist (Manual)

- Startup:
  - App launches backend automatically.
  - UI opens at `http://127.0.0.1:8000`.
- Failure mode:
  - If backend binary is missing or port is occupied, app shows an error and exits.
- Shutdown:
  - Closing the app stops backend process (no orphan backend).
- Data:
  - `AAR_DATA_DIR` points to a stable per-user directory (not inside app resources).

## Size Accounting Checklist

- Compare Windows installer size:
  - Electron NSIS `.exe` vs Tauri NSIS `-setup.exe`.
- Confirm WebView2 runtime is not embedded (installer should be small; runtime installed on-demand).
- Recognize lower bound:
  - PyInstaller backend (~74MB) dominates; further reductions require backend packaging optimization.

