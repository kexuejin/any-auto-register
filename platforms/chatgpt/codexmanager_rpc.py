from __future__ import annotations

import logging

from curl_cffi import requests as cffi_requests

from .codexmanager_upload import (
    _map_rpc_exception,
    _resolve_rpc_token,
    _resolve_rpc_url,
    resolve_rpc_urls,
)

logger = logging.getLogger(__name__)
_last_error = ""


def get_last_error() -> str:
    return _last_error


def _set_last_error(value: str) -> None:
    global _last_error
    _last_error = str(value or "")


def rpc_call(
    method: str,
    params: dict | None = None,
    rpc_url: str | None = None,
    rpc_token: str | None = None,
) -> dict | None:
    primary_url = _resolve_rpc_url(rpc_url)
    rpc_urls = resolve_rpc_urls(primary_url)
    if not rpc_urls:
        _set_last_error("rpc_url_missing")
        return None

    token = _resolve_rpc_token(rpc_token)
    if not token:
        _set_last_error("rpc_token_missing")
        return None

    headers = {
        "Content-Type": "application/json",
        "X-CodexManager-Rpc-Token": token,
    }
    body = {"id": 1, "method": method, "params": params or {}}

    for url in rpc_urls:
        try:
            resp = cffi_requests.post(
                url,
                headers=headers,
                json=body,
                proxies=None,
                timeout=30,
                impersonate="chrome110",
            )
        except Exception as exc:
            mapped = _map_rpc_exception(exc)
            _set_last_error(mapped or "rpc_unreachable")
            logger.warning("[CodexManager] RPC request failed: %s", exc)
            continue

        if resp.status_code not in (200, 201):
            _set_last_error(f"rpc_http_{resp.status_code}")
            continue

        try:
            data = resp.json()
        except Exception:
            _set_last_error("rpc_invalid_json")
            continue

        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            _set_last_error("")
            return result
        _set_last_error("rpc_invalid_json")
    return None


def list_accounts(
    filter: str | None = None,
    rpc_url: str | None = None,
    rpc_token: str | None = None,
) -> list[dict]:
    params = {}
    if filter:
        params["filter"] = filter
    result = rpc_call("account/list", params, rpc_url=rpc_url, rpc_token=rpc_token)
    items = result.get("items") if isinstance(result, dict) else None
    return list(items or [])


def delete_account(
    account_id: str,
    rpc_url: str | None = None,
    rpc_token: str | None = None,
) -> bool:
    params = {"accountId": account_id}
    result = rpc_call("account/delete", params, rpc_url=rpc_url, rpc_token=rpc_token)
    return bool(result.get("ok")) if isinstance(result, dict) else False
