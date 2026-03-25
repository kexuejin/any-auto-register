from platforms.chatgpt.codexmanager_upload import (
    build_import_payload,
    resolve_rpc_urls,
)


class Dummy:
    def __init__(self, email, token=None, extra=None):
        self.email = email
        self.token = token or ""
        self.extra = extra or {}


def test_build_import_payload_requires_access_token():
    acc = Dummy("a@example.com", token="", extra={})
    assert build_import_payload(acc) is None


def test_build_import_payload_requires_all_tokens():
    acc = Dummy("a@example.com", token="tok", extra={"refresh_token": "", "id_token": ""})
    assert build_import_payload(acc) is None


def test_resolve_rpc_urls_prefers_primary_and_fallbacks():
    urls = resolve_rpc_urls("http://example.com/rpc")
    assert urls[0] == "http://example.com/rpc"
    assert "http://127.0.0.1:48760/rpc" in urls
    assert "http://localhost:48760/rpc" in urls
    assert "http://127.0.0.1:48761/api/rpc" in urls
    assert "http://localhost:48761/api/rpc" in urls


def test_resolve_rpc_urls_normalizes_scheme_less_primary():
    urls = resolve_rpc_urls("127.0.0.1:48760/rpc")
    assert urls[0] == "http://127.0.0.1:48760/rpc"


def test_upload_returns_error_when_access_token_missing():
    from platforms.chatgpt.codexmanager_upload import upload_to_codexmanager

    ok, msg = upload_to_codexmanager(
        Dummy("a@example.com", token="", extra={"refresh_token": "r", "id_token": "i"})
    )
    assert ok is False
    assert "access_token" in msg


def test_upload_returns_error_when_rpc_token_missing(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    monkeypatch.setattr(mod, "_resolve_rpc_token", lambda *_: "")

    def _fail_post(*_args, **_kwargs):
        raise AssertionError("request should not be sent without token")

    monkeypatch.setattr(mod.cffi_requests, "post", _fail_post)

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
    )
    assert ok is False
    assert "RPC Token" in msg


def test_upload_success_parses_result(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    class Resp:
        status_code = 200

        def json(self):
            return {"result": {"created": 1, "updated": 0, "failed": 0}}

    monkeypatch.setattr(mod.cffi_requests, "post", lambda *_a, **_k: Resp())

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is True
    assert "created=1" in msg


def test_upload_no_created_or_updated_is_failure(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    class Resp:
        status_code = 200

        def json(self):
            return {"result": {"created": 0, "updated": 0, "failed": 0}}

    monkeypatch.setattr(mod.cffi_requests, "post", lambda *_a, **_k: Resp())

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert "created=0" in msg


def test_upload_invalid_json_returns_error(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    class Resp:
        status_code = 200
        text = "not-json"

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(mod.cffi_requests, "post", lambda *_a, **_k: Resp())

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert "rpc_invalid_json" in msg


def test_upload_connection_refused_after_connection_refused_on_fallbacks(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    monkeypatch.setattr(
        mod,
        "resolve_rpc_urls",
        lambda _primary: ["http://127.0.0.1:48760/rpc", "http://localhost:48760/rpc"],
    )

    def _raise_conn(*_a, **_k):
        raise RuntimeError("failed to connect")

    monkeypatch.setattr(mod.cffi_requests, "post", _raise_conn)

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert msg == "rpc_connection_refused"


def test_upload_does_not_propagate_rpc_error_payload(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    class Resp:
        status_code = 200

        def json(self):
            return {"error": "raw backend error"}

    monkeypatch.setattr(mod.cffi_requests, "post", lambda *_a, **_k: Resp())

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert msg == "rpc_invalid_json"


def test_upload_http_status_maps_to_rpc_http_code(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    class Resp:
        status_code = 401

        def json(self):
            return {"message": "unauthorized"}

    monkeypatch.setattr(mod.cffi_requests, "post", lambda *_a, **_k: Resp())

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert msg == "rpc_http_401"


def test_upload_timeout_maps_to_rpc_timeout(monkeypatch):
    import platforms.chatgpt.codexmanager_upload as mod

    def _raise_timeout(*_a, **_k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(mod.cffi_requests, "post", _raise_timeout)

    ok, msg = mod.upload_to_codexmanager(
        Dummy("a@example.com", token="tok", extra={"refresh_token": "r", "id_token": "i"}),
        rpc_url="http://127.0.0.1:48760/rpc",
        rpc_token="token",
    )
    assert ok is False
    assert msg == "rpc_timeout"
