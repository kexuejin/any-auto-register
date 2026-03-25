# Accounts List Created-At Desc Sort Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure `/api/accounts` returns accounts ordered by `created_at` descending so newest appear first.

**Architecture:** Update the accounts list query to include `order_by(AccountModel.created_at.desc())`. Add a unit test that seeds two accounts with distinct `created_at` values and asserts the returned order.

**Tech Stack:** FastAPI, SQLModel, pytest.

---

### Task 1: Add failing test for created_at descending order

**Files:**
- Create: `tests/test_accounts_ordering.py`

**Step 1: Write the failing test**

```python
from datetime import datetime, timezone, timedelta

from sqlmodel import SQLModel, Session, create_engine

from api.accounts import list_accounts
from core.db import AccountModel


def test_list_accounts_orders_by_created_at_desc():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    old_time = datetime.now(timezone.utc) - timedelta(days=1)
    new_time = datetime.now(timezone.utc)

    with Session(engine) as session:
        session.add(AccountModel(
            platform="chatgpt",
            email="old@example.com",
            password="x",
            created_at=old_time,
        ))
        session.add(AccountModel(
            platform="chatgpt",
            email="new@example.com",
            password="y",
            created_at=new_time,
        ))
        session.commit()

        result = list_accounts(session=session)
        items = result["items"]
        assert [items[0].email, items[1].email] == ["new@example.com", "old@example.com"]
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_accounts_ordering.py::test_list_accounts_orders_by_created_at_desc -v`

Expected: FAIL with order assertion (new not first).

**Step 3: Commit**

```bash
git add tests/test_accounts_ordering.py
git commit -m "test: add ordering test for accounts list"
```

---

### Task 2: Implement created_at desc ordering

**Files:**
- Modify: `api/accounts.py`
- Test: `tests/test_accounts_ordering.py`

**Step 1: Write minimal implementation**

```python
# in list_accounts(), after filters
q = q.order_by(AccountModel.created_at.desc())
```

**Step 2: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_accounts_ordering.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add api/accounts.py tests/test_accounts_ordering.py
git commit -m "feat: sort accounts by created_at desc"
```

---

### Task 3: Full test run

**Files:**
- None

**Step 1: Run full tests**

Run: `PYTHONPATH=. pytest`

Expected: PASS (all tests)

**Step 2: Commit (if needed)**

```bash
# No code changes expected
```
