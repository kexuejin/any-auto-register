import sys
import types

fake_http_client_module = types.ModuleType("platforms.chatgpt.http_client")
fake_http_client_module.OpenAIHTTPClient = object
fake_http_client_module.HTTPClientError = Exception
sys.modules.setdefault("platforms.chatgpt.http_client", fake_http_client_module)

from platforms.chatgpt.register import _should_resend_otp


def test_resend_schedule():
    assert _should_resend_otp(elapsed=15, last_resend=0, resend_count=0)
    assert not _should_resend_otp(elapsed=10, last_resend=0, resend_count=0)
