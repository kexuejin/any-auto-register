from platforms.chatgpt.plugin import ChatGPTPlatform
from core.base_platform import RegisterConfig, Account, AccountStatus


def test_chatgpt_actions_include_codexmanager():
    platform = ChatGPTPlatform(config=RegisterConfig())
    actions = platform.get_platform_actions()
    ids = [a["id"] for a in actions]
    assert "upload_codexmanager" in ids


def test_execute_action_upload_codexmanager(monkeypatch):
    platform = ChatGPTPlatform(config=RegisterConfig())

    called = {"ok": False}

    def _fake_upload(account):
        called["ok"] = True
        return True, "ok"

    import platforms.chatgpt.codexmanager_upload as mod
    monkeypatch.setattr(mod, "upload_to_codexmanager", _fake_upload)

    acc = Account(
        platform="chatgpt",
        email="a@example.com",
        password="x",
        token="tok",
        status=AccountStatus.REGISTERED,
        extra={},
    )

    result = platform.execute_action("upload_codexmanager", acc, {})
    assert called["ok"] is True
    assert result["ok"] is True
    assert result["data"] == "ok"
