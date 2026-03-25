from __future__ import annotations

import json
import logging
import os

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

FALLBACK_URLS = [
    "http://127.0.0.1:48760/rpc",
    "http://localhost:48760/rpc",
    "http://127.0.0.1:48761/api/rpc",
    "http://localhost:48761/api/rpc",
]


def _get_config_value(key: str) -> str:
    try:
        from core.config_store import config_store

        return str(config_store.get(key, "") or "")
    except Exception:
        return ""


def _read_token_file(path: str) -> str:
    if not path:
        return ""
    try:
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return str(f.read() or "").strip()
    except Exception:
        return ""


def _resolve_rpc_token(explicit: str | None = None) -> str:
    if explicit:
        token = str(explicit or "").strip()
        if token:
            return token

    token = str(_get_config_value("codexmanager_rpc_token") or "").strip()
    if token:
        return token

    token = str(os.getenv("CODEXMANAGER_RPC_TOKEN", "") or "").strip()
    if token:
        return token

    token_file = str(_get_config_value("codexmanager_rpc_token_file") or "").strip()
    if token_file:
        token = _read_token_file(token_file)
        if token:
            return token

    token_file = str(os.getenv("CODEXMANAGER_RPC_TOKEN_FILE", "") or "").strip()
    if token_file:
        token = _read_token_file(token_file)
        if token:
            return token

    db_path = str(os.getenv("CODEXMANAGER_DB_PATH", "") or "").strip()
    if db_path:
        token = _read_token_file(
            os.path.join(os.path.dirname(db_path), "codexmanager.rpc-token")
        )
        if token:
            return token

    mac_defaults = [
        os.path.expanduser(
            "~/Library/Application Support/com.codexmanager.desktop/codexmanager.rpc-token"
        ),
        os.path.expanduser(
            "~/Library/Application Support/codexmanager/codexmanager.rpc-token"
        ),
    ]
    for path in mac_defaults:
        token = _read_token_file(path)
        if token:
            return token

    return ""


def _resolve_rpc_url(explicit: str | None = None) -> str:
    if explicit:
        value = str(explicit or "").strip()
        if value:
            return value

    value = str(_get_config_value("codexmanager_rpc_url") or "").strip()
    if value:
        return value

    value = str(os.getenv("CODEXMANAGER_RPC_URL", "") or "").strip()
    if value:
        return value

    return "http://127.0.0.1:48760/rpc"


def resolve_rpc_urls(primary: str) -> list[str]:
    normalized_primary = str(primary or "").strip()
    if normalized_primary and "://" not in normalized_primary:
        normalized_primary = f"http://{normalized_primary}"
    candidates = [normalized_primary] + FALLBACK_URLS
    urls = []
    seen = set()
    for url in candidates:
        normalized = str(url or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
    return urls


def build_import_payload(account) -> dict | None:
    access_token = (getattr(account, "token", "") or "").strip()
    extra = getattr(account, "extra", None) or {}
    refresh_token = (extra.get("refresh_token") or extra.get("refreshToken") or "").strip()
    id_token = (extra.get("id_token") or extra.get("idToken") or "").strip()
    if not access_token or not refresh_token or not id_token:
        return None
    email = getattr(account, "email", "")
    return {
        "email": email,
        "label": extra.get("label") or email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "workspace_id": (extra.get("workspace_id") or extra.get("workspaceId") or ""),
        "account_id": (extra.get("account_id") or extra.get("accountId") or ""),
    }


def _map_rpc_exception(exc: Exception) -> str:
    message = str(exc or "").lower()
    if isinstance(exc, TimeoutError) or "timed out" in message or "timeout" in message:
        return "rpc_timeout"
    if (
        "connection refused" in message
        or "refused" in message
        or "failed to connect" in message
    ):
        return "rpc_connection_refused"
    return "rpc_unreachable"


def upload_to_codexmanager(
    account,
    rpc_url: str | None = None,
    rpc_token: str | None = None,
) -> tuple[bool, str]:
    payload = build_import_payload(account)
    if not payload:
        return False, "账号缺少 access_token/refresh_token/id_token"

    primary_url = _resolve_rpc_url(rpc_url)
    rpc_urls = resolve_rpc_urls(primary_url)
    if not rpc_urls and primary_url != "http://127.0.0.1:48760/rpc":
        rpc_urls = resolve_rpc_urls("http://127.0.0.1:48760/rpc")
    if not rpc_urls:
        return False, "CodexManager RPC URL 未配置"

    token = _resolve_rpc_token(rpc_token)
    if not token:
        return False, "CodexManager RPC Token 未配置"
    headers = {"Content-Type": "application/json"}
    headers["X-CodexManager-Rpc-Token"] = token

    content = json.dumps([payload], ensure_ascii=False)
    body = {"id": 1, "method": "account/import", "params": {"content": content}}

    errors: list[str] = []
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
            errors.append(_map_rpc_exception(exc))
            logger.warning("[CodexManager] RPC request failed: %s", exc)
            continue

        if resp.status_code not in (200, 201):
            errors.append(f"rpc_http_{resp.status_code}")
            continue

        try:
            data = resp.json()
        except Exception:
            errors.append("rpc_invalid_json")
            continue

        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            errors.append("rpc_invalid_json")
            continue

        failed = int(result.get("failed", 0) or 0)
        created = int(result.get("created", 0) or 0)
        updated = int(result.get("updated", 0) or 0)
        ok = failed == 0 and (created + updated) > 0
        msg = f"created={created} updated={updated} failed={failed}"
        return ok, msg

    if not errors:
        return False, "rpc_unreachable"
    return False, errors[-1]
