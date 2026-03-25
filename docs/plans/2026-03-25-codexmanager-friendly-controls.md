# CodexManager Friendly Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace CodexManager text inputs with friendly controls (toggle, number inputs, grouped sections, advanced collapse) in Settings.

**Architecture:** Keep Settings as the single source of form state and `/api/config` persistence; extend Field rendering to support new control types and add an advanced collapsible block for CodexManager settings.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind CSS.

---

### Task 1: Add Minimal Frontend Test Harness

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/pages/__tests__/settings-harness.test.tsx`

**Step 1: Write a failing test (no test runner yet)**

```tsx
// frontend/src/pages/__tests__/settings-harness.test.tsx
import { describe, it, expect } from 'vitest'

describe('settings test harness', () => {
  it('runs vitest', () => {
    expect(1 + 1).toBe(2)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL (vitest not found / missing dependencies)

**Step 3: Add minimal test setup**

```json
// frontend/package.json (devDependencies + scripts)
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run"
},
"devDependencies": {
  "vitest": "^3.2.4",
  "@testing-library/react": "^16.3.0",
  "@testing-library/jest-dom": "^6.6.3",
  "jsdom": "^26.0.0",
  ...
}
```

```ts
// frontend/vite.config.ts (add test config)
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

```ts
// frontend/src/test/setup.ts
import '@testing-library/jest-dom/vitest'
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm install && npm run test`
Expected: PASS (1 test)

**Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/test/setup.ts frontend/src/pages/__tests__/settings-harness.test.tsx
git commit -m "test: add vitest harness for settings"
```

---

### Task 2: Write Tests for New Field Types + Advanced Collapse

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/pages/__tests__/settings-codexmanager.test.tsx`

**Step 1: Write failing tests**

```tsx
// frontend/src/pages/__tests__/settings-codexmanager.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Settings from '../Settings'

vi.mock('@/lib/utils', async (orig) => {
  const mod = await orig()
  return { ...mod, apiFetch: vi.fn(async () => ({})) }
})

describe('CodexManager settings controls', () => {
  it('renders a toggle for auto-fill switch', async () => {
    render(<Settings />)
    expect(await screen.findByText('自动补号开关')).toBeInTheDocument()
    const toggle = screen.getByRole('switch', { name: '自动补号开关' })
    expect(toggle).toHaveAttribute('aria-checked')
  })

  it('hides advanced settings by default and shows after expand', async () => {
    render(<Settings />)
    const advancedButton = await screen.findByRole('button', { name: '高级设置' })
    expect(screen.queryByText('封禁过滤值')).toBeNull()
    fireEvent.click(advancedButton)
    expect(await screen.findByText('封禁过滤值')).toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL (toggle/collapse not implemented)

**Step 3: Implement minimal code to pass**

- Export/structure `Field` so it can render a `role="switch"` toggle when `type: 'toggle'`.
- Add advanced collapse UI in CodexManager section.
- Ensure the toggle is labelled with `aria-label` matching “自动补号开关”.

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/pages/__tests__/settings-codexmanager.test.tsx
git commit -m "test: cover CodexManager toggle and advanced collapse"
```

---

### Task 3: Implement Friendly Controls + Advanced Grouping

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

**Step 1: Write failing test for number fields**

```tsx
// add to settings-codexmanager.test.tsx
it('renders number inputs for interval and thresholds', async () => {
  render(<Settings />)
  const interval = await screen.findByLabelText('补号检查间隔(秒)')
  expect(interval).toHaveAttribute('type', 'number')
  const minAvailable = await screen.findByLabelText('最低可用账号数')
  expect(minAvailable).toHaveAttribute('type', 'number')
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL (inputs are not type=number)

**Step 3: Implement minimal code to pass**

- Add per-field metadata (`type`, `min`, `step`, `help`).
- Render numeric inputs when `type: 'number'`.
- Add `help` text under the input.
- Group CodexManager items into basic + advanced collapse per design.

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/pages/__tests__/settings-codexmanager.test.tsx
git commit -m "feat: friendly CodexManager controls with advanced section"
```

---

### Task 4: Build Frontend + Update Static Assets

**Files:**
- Modify: `static/index.html`
- Modify: `static/assets/*`

**Step 1: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds and updates `static/`

**Step 2: Smoke check**

Run: `python3 - <<'PY'
import re
print('codexmanager_maintain_enabled' in open('static/assets/' + [f for f in __import__('os').listdir('static/assets') if f.endswith('.js')][0]).read())
PY`
Expected: `True`

**Step 3: Commit**

```bash
git add -f static
# keep existing staged files
git commit -m "build: update static assets for CodexManager controls"
```

---

### Task 5: Manual Verification

**Steps**
1. Open `http://127.0.0.1:8000/settings`.
2. Verify CodexManager shows toggle + numeric inputs.
3. Advanced settings collapsed by default; expand shows filter fields.
4. Save config and confirm values persist after reload.

**Commit (optional)**
No code changes expected.
