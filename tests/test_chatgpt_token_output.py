import sys
import types

fake_http_client_module = types.ModuleType("platforms.chatgpt.http_client")
fake_http_client_module.OpenAIHTTPClient = object
fake_http_client_module.HTTPClientError = Exception
sys.modules.setdefault("platforms.chatgpt.http_client", fake_http_client_module)

from platforms.chatgpt.register import RegistrationResult


def test_token_output_fields():
    result = RegistrationResult(
        success=True,
        email="a@b.com",
        type="codex",
        name="Alice",
        access_token="access_token_value",
        refresh_token="refresh_token_value",
        id_token="id_token_value",
        account_id="acct_1",
        workspace_id="ws_1",
        expires_at="2026-03-24T00:00:00Z",
        registered_at="2026-03-24T00:00:00Z",
        mode="register",
        team_upgrade={"attempted": False, "success": False},
        token_health={"checked": True},
    )
    data = result.to_dict()
    for field in (
        "email",
        "type",
        "name",
        "access_token",
        "refresh_token",
        "id_token",
        "account_id",
        "workspace_id",
        "expires_at",
        "registered_at",
        "mode",
        "team_upgrade",
        "token_health",
    ):
        assert field in data
