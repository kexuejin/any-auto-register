# Accounts Modal Portal + Pagination Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Accounts page modals to always center in the viewport and add pagination (default 50/page) for large account lists.

**Architecture:** Render all Accounts modals through a React Portal to `document.body` so `position: fixed` overlays are not affected by scroll containers/transforms. Add `page/pageSize` state and include them in `/api/accounts` queries; render a simple pagination control at the bottom of the table.

**Tech Stack:** React + TypeScript (Vite), Tailwind CSS utilities, existing UI components (`Button`, `Badge`, `Card`).

---

### Task 1: Portalize Remaining Accounts Modals

**Files:**
- Modify: `frontend/src/pages/Accounts.tsx`

**Step 1: Wrap `DetailModal` in `Portal`**

Expected change:
- `DetailModal` returns:
  - `<Portal><div className="dialog-backdrop">...</div></Portal>`

**Step 2: Wrap `ImportModal` in `Portal`**

Expected change:
- `ImportModal` returns:
  - `<Portal><div className="dialog-backdrop">...</div></Portal>`

**Step 3: Confirm there are no other `.dialog-backdrop` instances without `Portal`**

Run:
- `rg -n "dialog-backdrop" frontend/src/pages/Accounts.tsx`

Expected:
- All modal backdrops are descendants of `<Portal>`.

---

### Task 2: Add Pagination State + API Params

**Files:**
- Modify: `frontend/src/pages/Accounts.tsx`

**Step 1: Add state**
- Add:
  - `const [page, setPage] = useState(1)`
  - `const [pageSize, setPageSize] = useState(50)`

**Step 2: Reset `page` when filters change**
- On changes to `tab`, `filterStatus`, `debouncedSearch`:
  - `setPage(1)`

**Step 3: Update `load()` to request `page` and `page_size`**
- Request:
  - `/accounts?platform=${tab}&page=${page}&page_size=${pageSize}&...`

**Step 4: Make data-loading effect depend on `page` and `pageSize`**
- Ensure list updates when switching pages.

---

### Task 3: Add Pagination UI

**Files:**
- Modify: `frontend/src/pages/Accounts.tsx`

**Step 1: Compute pagination summary**
- `const totalPages = Math.max(1, Math.ceil(total / pageSize))`
- `const canPrev = page > 1`
- `const canNext = page < totalPages`

**Step 2: Render controls under the table**
- Buttons:
  - `上一页` (disabled if `!canPrev`)
  - `下一页` (disabled if `!canNext`)
- Info:
  - `第 {page} / {totalPages} 页`
  - `共 {total} 条`
- Page size select:
  - `20 / 50 / 100` (changing resets to page 1)

**Step 3: Keep selection semantics “current page only”**
- No cross-page selection persistence beyond currently visible ids.

---

### Task 4: Verify Locally

**Files:**
- None (verification only)

**Step 1: Frontend build**

Run:
- `cd frontend && npm run build`

Expected:
- Build succeeds.

**Step 2: Manual UI smoke checks**
- Open Accounts page with long list.
- Scroll deep, open:
  - 自动注册 / 手动新增 / 详情 / 导入 / 操作结果 / 任务日志
- Expected:
  - All modals center in viewport regardless of scroll position.
- Use pagination:
  - Page changes update list, and the controls enable/disable correctly.

