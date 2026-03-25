from application import tasks


def test_pick_auto_upload_target_priority(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: False, raising=False)
    cfg = {
        "cpa_api_url": "x",
        "team_manager_url": "y",
        "team_manager_key": "k",
        "codexmanager_rpc_url": "z",
    }
    assert tasks._pick_auto_upload_target("", cfg) == "cpa"
    cfg = {"team_manager_url": "y", "team_manager_key": "k", "codexmanager_rpc_url": "z"}
    assert tasks._pick_auto_upload_target("", cfg) == "team_manager"
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: True, raising=False)
    cfg = {"codexmanager_rpc_url": "z"}
    assert tasks._pick_auto_upload_target("", cfg) == "codexmanager"


def test_pick_auto_upload_target_respects_explicit():
    cfg = {"cpa_api_url": "x"}
    assert tasks._pick_auto_upload_target("none", cfg) == "none"
    assert tasks._pick_auto_upload_target("team_manager", cfg) == "team_manager"


def test_pick_auto_upload_target_whitespace_falls_back():
    cfg = {"cpa_api_url": "x"}
    assert tasks._pick_auto_upload_target("   ", cfg) == "cpa"


def test_pick_auto_upload_target_defaults_to_none(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: False, raising=False)
    cfg = {}
    assert tasks._pick_auto_upload_target("", cfg) == "none"


def test_pick_auto_upload_target_requires_team_manager_key(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: False, raising=False)
    cfg = {"team_manager_url": "x"}
    assert tasks._pick_auto_upload_target("", cfg) == "none"
    cfg = {"team_manager_url": "x", "team_manager_key": "k"}
    assert tasks._pick_auto_upload_target("", cfg) == "team_manager"


def test_pick_auto_upload_target_allows_codexmanager_without_url(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: True, raising=False)
    cfg = {}
    assert tasks._pick_auto_upload_target("", cfg) == "codexmanager"


def test_pick_auto_upload_target_requires_codexmanager_token(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: False, raising=False)
    cfg = {}
    assert tasks._pick_auto_upload_target("", cfg) == "none"


def test_pick_auto_upload_target_codexmanager_url_without_token_is_none(monkeypatch):
    monkeypatch.setattr(tasks, "_has_codexmanager_token", lambda: False, raising=False)
    cfg = {"codexmanager_rpc_url": "x"}
    assert tasks._pick_auto_upload_target("", cfg) == "none"
