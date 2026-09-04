"""Zentraler Gesundheitsstatus (ohne HA-Abhängigkeit, damit unit-testbar)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

STATE_OK = "ok"
STATE_ERROR = "error"
STATE_OFFLINE = "offline"


class HealthState:
    """Hält den letzten Report + Zeitstempel; alt = offline.

    `last_report`  = Empfangszeit auf HA (Basis der Stale-Erkennung,
                      HA-Uhr – bleibt Clock-Skew-immun).
    `last_report_sent_at` = Sendezeit des Reporters (z. B. AppDaemon-
                      Server, eigene Uhr) – nur zur Anzeige/Diagnose.
    """

    def __init__(self, stale_timeout: timedelta) -> None:
        self._stale_timeout = stale_timeout
        self._last_state = STATE_OFFLINE
        self._last_report: datetime | None = None
        self._last_report_sent_at: datetime | None = None

    @property
    def last_report(self) -> datetime | None:
        """Zeitpunkt des letzten Reports (UTC) oder None."""
        return self._last_report

    @property
    def last_report_sent_at(self) -> datetime | None:
        """Vom Reporter gemeldeter Sendezeitpunkt (UTC) oder None."""
        return self._last_report_sent_at

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def set(self, state: str, sent_at: datetime | None = None) -> None:
        self._last_state = state
        self._last_report = self._now()
        self._last_report_sent_at = sent_at

    def current(self) -> str:
        if self._last_report is None:
            return STATE_OFFLINE
        if (self._now() - self._last_report) > self._stale_timeout:
            return STATE_OFFLINE
        return self._last_state
