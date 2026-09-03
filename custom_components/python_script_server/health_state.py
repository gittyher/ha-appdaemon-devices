"""Zentraler Gesundheitsstatus (ohne HA-Abhängigkeit, damit unit-testbar)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

STATE_OK = "ok"
STATE_ERROR = "error"
STATE_OFFLINE = "offline"


class HealthState:
    """Hält den letzten Report + Zeitstempel; alt = offline."""

    def __init__(self, stale_timeout: timedelta) -> None:
        self._stale_timeout = stale_timeout
        self._last_state = STATE_OFFLINE
        self._last_report: datetime | None = None

    @property
    def last_report(self) -> datetime | None:
        """Zeitpunkt des letzten Reports (UTC) oder None."""
        return self._last_report

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def set(self, state: str) -> None:
        self._last_state = state
        self._last_report = self._now()

    def current(self) -> str:
        if self._last_report is None:
            return STATE_OFFLINE
        if (self._now() - self._last_report) > self._stale_timeout:
            return STATE_OFFLINE
        return self._last_state
