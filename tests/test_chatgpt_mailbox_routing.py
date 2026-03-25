from dataclasses import dataclass
import types
import sys

from platforms.chatgpt.plugin import ChatGPTPlatform
from core.base_platform import RegisterConfig


class FakeMailbox:
    def get_email(self):
        return type("A", (), {"email": "x@y.com", "account_id": "id"})()

    def get_current_ids(self, *a, **k):
        return set()

    def wait_for_code(self, *a, **k):
        return "123456"


@dataclass
class FakeResult:
    success: bool = True
    email: str = "x@y.com"
    password: str = "Pass123456!"
    account_id: str = "acct-1"
    access_token: str = "atk"
    refresh_token: str = "rtk"
    id_token: str = "itk"
    session_token: str = ""
    workspace_id: str = "ws-1"
    error_message: str = ""


def test_chatgpt_uses_injected_mailbox(monkeypatch):
    import core.base_mailbox as mailbox_mod

    def _fail_tempmail(*args, **kwargs):
        raise AssertionError("should not use TempMailLolMailbox when injected mailbox exists")

    class FakeEngine:
        def __init__(self, email_service, proxy_url=None, callback_logger=None):
            self.email_service = email_service
            self.email = None
            self.password = None

        def run(self):
            return FakeResult(email=self.email or "x@y.com", password=self.password or "Pass123456!")

    fake_register_mod = types.SimpleNamespace(RegistrationEngine=FakeEngine)
    monkeypatch.setitem(sys.modules, "platforms.chatgpt.register", fake_register_mod)
    monkeypatch.setattr(mailbox_mod.TempMailLolMailbox, "__init__", _fail_tempmail)

    cfg = RegisterConfig(extra={"mail_provider": "chuleicn"})
    p = ChatGPTPlatform(config=cfg, mailbox=FakeMailbox())
    account = p.register(email="x@y.com", password="Pass123456!")
    assert account.email == "x@y.com"
