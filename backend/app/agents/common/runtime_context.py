"""Trusted context captured once for an agent workflow run."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def build_runtime_context() -> dict[str, str]:
    """Capture one trusted time reference for the entire workflow run."""

    timezone_name = settings.BUSINESS_TIMEZONE
    current_datetime = datetime.now(ZoneInfo(timezone_name))
    return {
        "current_datetime": current_datetime.isoformat(),
        "timezone": timezone_name,
    }
