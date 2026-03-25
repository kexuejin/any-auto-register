def test_codexmanager_list_accounts_uses_filter(monkeypatch):
    import platforms.chatgpt.codexmanager_rpc as mod

    seen = {}

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None, impersonate=None):
        seen["url"] = url
        seen["body"] = json
        class Resp:
            status_code = 200
            def json(self):
                return {"result": {"items": [{"id": "1"}]}}
        return Resp()

    monkeypatch.setattr(mod.cffi_requests, "post", fake_post)
    items = mod.list_accounts("active", rpc_url="http://x", rpc_token="t")

    assert seen["body"]["method"] == "account/list"
    assert seen["body"]["params"]["filter"] == "active"
    assert items == [{"id": "1"}]


def test_codexmanager_delete_account_ok(monkeypatch):
    import platforms.chatgpt.codexmanager_rpc as mod

    def fake_post(url, headers=None, json=None, proxies=None, timeout=None, impersonate=None):
        class Resp:
            status_code = 200
            def json(self):
                return {"result": {"ok": True}}
        return Resp()

    monkeypatch.setattr(mod.cffi_requests, "post", fake_post)
    ok = mod.delete_account("acc_1", rpc_url="http://x", rpc_token="t")
    assert ok is True
