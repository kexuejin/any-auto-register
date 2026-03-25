
def test_maintainer_deletes_banned_and_local(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()

    calls = {"deleted": [], "local": []}

    def fake_list(filter_value=None):
        if filter_value == "banned":
            return [
                {"id": "a1", "email": "ban1@example.com", "status": "banned"},
                {"id": "a2", "label": "ban2@example.com", "status": "disabled"},
            ]
        return []

    def fake_delete(account_id):
        calls["deleted"].append(account_id)
        return True

    def fake_local_delete(email):
        calls["local"].append(email)
        return True

    monkeypatch.setattr(maint, "_list_accounts", fake_list)
    monkeypatch.setattr(maint, "_delete_account", fake_delete)
    monkeypatch.setattr(maint, "_delete_local_account", fake_local_delete)
    # Avoid touching DB-backed task system in this unit test; we only assert cleanup behavior.
    monkeypatch.setattr(maint, "_start_register_task", lambda count: None)
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": True,
        "interval_secs": 7200,
        "min_available": 50,
        "fill_count": 0,
        "cleanup_enabled": True,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    report = maint.run_once()
    assert calls["deleted"] == ["a1", "a2"]
    assert calls["local"] == ["ban1@example.com", "ban2@example.com"]
    assert report["deleted"] == 2


def test_maintainer_triggers_fill(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()
    calls = {"fill": []}

    monkeypatch.setattr(maint, "_list_accounts", lambda filter_value=None: [{"id": "x"}] if filter_value == "active" else [])
    monkeypatch.setattr(maint, "_delete_account", lambda account_id: True)
    monkeypatch.setattr(maint, "_delete_local_account", lambda email: True)
    monkeypatch.setattr(maint, "_start_register_task", lambda count: calls["fill"].append(count))
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": True,
        "interval_secs": 7200,
        "min_available": 5,
        "fill_count": 0,
        "cleanup_enabled": False,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    report = maint.run_once()
    assert report["available"] == 1
    assert calls["fill"] == [4]


def test_maintainer_run_once_force_ignores_enabled(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()
    calls = {"list": [], "fill": []}

    def fake_list(filter_value=None):
        calls["list"].append(filter_value)
        if filter_value == "active":
            return [{"id": "x1"}]
        return []

    monkeypatch.setattr(maint, "_list_accounts", fake_list)
    monkeypatch.setattr(maint, "_delete_account", lambda account_id: True)
    monkeypatch.setattr(maint, "_delete_local_account", lambda email: True)
    monkeypatch.setattr(maint, "_start_register_task", lambda count: calls["fill"].append(count))
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": False,  # disabled, but force should ignore
        "interval_secs": 7200,
        "min_available": 2,
        "fill_count": 0,
        "cleanup_enabled": False,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    report = maint.run_once(force=True)
    assert report.get("skipped") is None
    assert report["available"] == 1
    assert calls["fill"] == [1]  # min_available=2 => need 1


def test_maintainer_fill_only_skips_delete(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()
    calls = {"deleted": []}

    monkeypatch.setattr(maint, "_list_accounts", lambda filter_value=None: [{"id": "a1", "label": "x@example.com", "status": "banned"}])
    monkeypatch.setattr(maint, "_delete_account", lambda account_id: calls["deleted"].append(account_id) or True)
    monkeypatch.setattr(maint, "_delete_local_account", lambda email: True)
    monkeypatch.setattr(maint, "_read_config", lambda: {
        "enabled": True,
        "interval_secs": 7200,
        "min_available": 1,
        "fill_count": 0,
        "cleanup_enabled": False,
        "banned_filter": "banned",
        "available_filters": ["active"],
    })

    rep = maint.run_once()
    assert rep["cleanup"] is False
    assert calls["deleted"] == []


def test_maintainer_start_stop(monkeypatch):
    import anyio
    import main
    from core import registry as registry_mod
    from core import scheduler as scheduler_mod
    from services import solver_manager as solver_mod
    from services import task_runtime as task_runtime_mod

    calls = {"start": 0, "stop": 0}

    class FakeMaintainer:
        def start(self):
            calls["start"] += 1

        def stop(self):
            calls["stop"] += 1

    monkeypatch.setattr(main, "codexmanager_maintainer", FakeMaintainer())

    class FakeScheduler:
        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "load_all", lambda: None)
    monkeypatch.setattr(registry_mod, "list_platforms", lambda: [])
    monkeypatch.setattr(scheduler_mod, "scheduler", FakeScheduler())
    monkeypatch.setattr(task_runtime_mod.task_runtime, "start", lambda: None)
    monkeypatch.setattr(task_runtime_mod.task_runtime, "stop", lambda: None)
    monkeypatch.setattr(solver_mod, "start_async", lambda: None)
    monkeypatch.setattr(solver_mod, "stop", lambda: None)

    async def _run():
        async with main.lifespan(main.app):
            pass

    anyio.run(_run)

    assert calls["start"] == 1
    assert calls["stop"] == 1


def test_maintainer_try_run_now_busy(monkeypatch):
    from core.codexmanager_maintainer import CodexManagerMaintainer

    maint = CodexManagerMaintainer()

    # Hold the lock to simulate an in-progress run
    maint._lock.acquire()
    try:
        ok, report, err = maint.try_run_now()
        assert ok is False
        assert report is None
        assert err == "busy"
    finally:
        maint._lock.release()
