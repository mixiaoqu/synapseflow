"""UTC time helpers for storage and API serialization."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize datetimes as ISO-8601 UTC strings with a trailing Z."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
