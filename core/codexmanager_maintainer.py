from __future__ import annotations

import logging
import threading
import time

from sqlmodel import Session, select

from core.config_store import config_store
from core.db import AccountModel, engine
from platforms.chatgpt import codexmanager_rpc


class CodexManagerMaintainer:
    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._logger = logging.getLogger(__name__)

    def start(self) -> None:
        if self._running and self._thread and self._thread.is_alive():
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            cfg = self._read_config()
            interval = int(cfg.get("interval_secs", 7200) or 7200)
            if cfg.get("enabled", True):
                if self._lock.acquire(blocking=False):
                    try:
                        self.run_once()
                    except Exception as exc:
                        self._logger.exception("CodexManager maintainer run failed: %s", exc)
                    finally:
                        self._lock.release()
            self._stop_event.wait(timeout=max(60, interval))

    def try_run_now(self) -> tuple[bool, dict | None, str | None]:
        """Manually trigger one full maintenance run.

        Uses the same non-blocking lock as the background loop.
        Returns (ok, report, err). If lock is held, err is 'busy'.
        """
        if not self._lock.acquire(blocking=False):
            return False, None, "busy"
        try:
            return True, self.run_once(force=True), None
        finally:
            self._lock.release()

    def run_once(self, force: bool = False) -> dict:
        cfg = self._read_config()
        # `deleted` counts CodexManager-side deletions (and corresponding local deletions when email matches).
        report = {"deleted": 0, "available": 0, "fill": 0, "cleanup": False}
        if (not force) and (not cfg.get("enabled", True)):
            report["skipped"] = True
            return report

        cleanup_enabled = bool(cfg.get("cleanup_enabled", False))
        report["cleanup"] = cleanup_enabled

        banned_filter = str(cfg.get("banned_filter") or "").strip()
        if cleanup_enabled and banned_filter:
            banned_items = self._list_accounts(banned_filter)
            err = self._get_last_error()
            if err:
                report["error"] = err
                return report
            skipped = 0
            for item in banned_items:
                # Safety: CodexManager's `account/list` filter behavior may vary by version.
                # We only delete when the returned item actually looks "banned/disabled".
                if not _is_banned_item(item):
                    skipped += 1
                    continue
                account_id = str(item.get("id") or "").strip()
                if not account_id:
                    continue
                if self._delete_account(account_id):
                    report["deleted"] += 1
                    email = str(item.get("email") or item.get("label") or "").strip()
                    if email:
                        self._delete_local_account(email)
                else:
                    err = self._get_last_error()
                    if err:
                        report["error"] = err
            if skipped:
                report["banned_skipped"] = int(skipped)

        available_filters = list(cfg.get("available_filters") or [])
        if not available_filters:
            available_filters = ["active"]
        ids: set[str] = set()
        for filter_value in available_filters:
            items = self._list_accounts(filter_value)
            err = self._get_last_error()
            if err:
                report["error"] = err
                return report
            for item in items:
                account_id = str(item.get("id") or "").strip()
                if account_id:
                    ids.add(account_id)
        available = len(ids)
        report["available"] = available

        min_available = int(cfg.get("min_available", 50) or 50)
        fill_count = int(cfg.get("fill_count", 0) or 0)
        if available < min_available:
            need = int(fill_count) if fill_count > 0 else (min_available - available)
            need = max(1, int(need))
            self._start_register_task(need)
            report["fill"] = need
        return report

    def _start_register_task(self, count: int) -> None:
        # Use the new task runtime (persistent task queue) rather than the legacy in-memory task runner.
        from application.task_commands import TaskCommandsService

        stored = config_store.get_all() or {}
        merged_extra = dict(stored)
        merged_extra["auto_upload_target"] = "codexmanager"

        executor_type = str(stored.get("default_executor") or "protocol")
        payload = {
            "platform": "chatgpt",
            "count": int(count),
            "concurrency": 1,
            "executor_type": executor_type,
            "captcha_solver": "auto",
            "extra": merged_extra,
        }
        TaskCommandsService().create_register_task(payload)

    def _list_accounts(self, filter_value: str | None) -> list[dict]:
        return codexmanager_rpc.list_accounts(filter_value)

    def _delete_account(self, account_id: str) -> bool:
        return codexmanager_rpc.delete_account(account_id)

    def _delete_local_account(self, email: str) -> bool:
        if not email:
            return False
        deleted = False
        with Session(engine) as session:
            accounts = session.exec(
                select(AccountModel).where(
                    AccountModel.platform == "chatgpt",
                    AccountModel.email == email,
                )
            ).all()
            for acc in accounts:
                session.delete(acc)
                deleted = True
            if deleted:
                session.commit()
        return deleted

    def _get_last_error(self) -> str:
        return str(codexmanager_rpc.get_last_error() or "")

    def _read_config(self) -> dict:
        cfg = config_store.get_all() or {}
        cleanup_raw = cfg.get("codexmanager_maintain_cleanup_enabled")
        # Backward compatible: previous versions used `codexmanager_maintain_fill_only`.
        # If the new key is unset but the old one exists, derive cleanup_enabled.
        if cleanup_raw is None or cleanup_raw == "":
            legacy_fill_only = cfg.get("codexmanager_maintain_fill_only")
            if legacy_fill_only is None or legacy_fill_only == "":
                cleanup_enabled = False
            else:
                cleanup_enabled = not _normalize_bool(legacy_fill_only, True)
        else:
            cleanup_enabled = _normalize_bool(cleanup_raw, False)
        return {
            "enabled": _normalize_bool(cfg.get("codexmanager_maintain_enabled"), True),
            "interval_secs": _normalize_int(cfg.get("codexmanager_maintain_interval_secs"), 7200, min_value=60),
            "min_available": _normalize_int(cfg.get("codexmanager_min_available"), 50, min_value=1),
            "fill_count": _normalize_int(cfg.get("codexmanager_fill_count"), 0, min_value=0),
            # Safety default: cleanup is OFF unless explicitly enabled.
            "cleanup_enabled": bool(cleanup_enabled),
            "banned_filter": str(cfg.get("codexmanager_banned_filter") or "banned").strip(),
            "available_filters": _split_filters(cfg.get("codexmanager_available_filter"), "active"),
        }


def _normalize_bool(value, default: bool) -> bool:
    if value is None or value == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _normalize_int(value, default: int, min_value: int | None = None) -> int:
    try:
        num = int(value)
    except Exception:
        num = int(default)
    if min_value is not None:
        num = max(min_value, num)
    return num


def _split_filters(value, default: str) -> list[str]:
    raw = str(value or default or "").strip()
    parts = [item.strip() for item in raw.replace(";", ",").split(",")]
    return [item for item in parts if item]


def _is_banned_item(item: dict) -> bool:
    """Best-effort classification for CodexManager `account/list` items.

    We purposefully bias to *not deleting* unless we see a strong signal that the
    account is banned/disabled/blocked. This prevents catastrophic deletions when
    upstream `filter` parameters are ignored or behave unexpectedly.
    """
    if not isinstance(item, dict):
        return False

    status = str(item.get("status") or "").strip().lower()
    reason = str(item.get("statusReason") or "").strip().lower()
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    tag_text = ",".join([str(t).strip().lower() for t in tags if t is not None])

    banned_statuses = {
        "banned",
        "disabled",
        "blocked",
        "suspended",
        "limited",
        "invalid",
    }
    if status in banned_statuses:
        return True

    # Some versions may still show status=active but include a reason/tag.
    keywords = ("ban", "banned", "blocked", "suspend", "disabled", "forbidden")
    if any(k in reason for k in keywords):
        return True
    if any(k in tag_text for k in keywords):
        return True

    return False
