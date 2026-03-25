from __future__ import annotations

from datetime import datetime, timezone
def _parse_datetime(value: str) -> datetime | None:
    """Parse common ISO-ish timestamps.

    We store timestamps in SQLite as datetimes, but some layers (task query DTOs)
    already serialize them to strings. Keep parsing tolerant so API endpoints
    don't crash when receiving string timestamps.
    """
    raw = (value or "").strip()
    if not raw:
        return None
    # Normalize "YYYY-MM-DD HH:MM:SS" -> ISO
    raw = raw.replace(" ", "T")
    # Normalize trailing Z -> offset
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def ensure_utc_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = _parse_datetime(value)
        value = parsed
        if value is None:
            return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def serialize_datetime(value: datetime | str | None) -> str | None:
    # If already serialized, keep it stable (avoid double-serialization bugs).
    if isinstance(value, str):
        return value
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")


def format_local_clock(value: datetime | str | None, fmt: str = "%H:%M:%S") -> str:
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        return ""
    return normalized.astimezone().strftime(fmt)
