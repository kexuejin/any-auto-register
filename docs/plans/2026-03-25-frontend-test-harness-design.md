# Frontend Test Harness Design

## Goal
Add a minimal Vitest harness to the frontend so we can run React-focused tests in a jsdom environment, starting with a single sanity test.

## Context
The frontend is a Vite + React 19 app with Tailwind. There is no existing test runner or test config.

## Proposed Design
- Add a `test` script and required devDependencies in `frontend/package.json`.
- Extend `frontend/vite.config.ts` with a `test` block that sets `environment: 'jsdom'` and references a setup file.
- Add `frontend/src/test/setup.ts` to register `@testing-library/jest-dom` matchers for Vitest.
- Add a simple sanity test at `frontend/src/pages/__tests__/settings-harness.test.tsx` to confirm the runner works.

## Data Flow
`npm run test` -> `vitest run` -> loads Vite config -> sets jsdom + setup file -> executes test files.

## Testing
1. Run `cd frontend && npm run test` (expected to fail before dependencies are installed).
2. Run `cd frontend && npm install` then `npm run test` (expected to pass with 1 test).

## Risks and Mitigations
- Risk: dependency version conflicts. Mitigation: keep versions close to recommended, adjust only if necessary for Vite/React compatibility.
