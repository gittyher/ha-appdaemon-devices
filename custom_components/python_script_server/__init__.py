"""PythonScriptServer – Device "PythonScriptServer" mit einer Health-Entity.

Die Health-Entity wird von einem Script auf dem AppDaemon-Server
(PythonScriptServer) gesetzt (Service python_script_server.set_health).
Ohne Report innerhalb der Stale-Zeit wird sie auf "offline" umgestellt.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import event as ha_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_STALE_TIMEOUT,
    DEFAULT_STALE_TIMEOUT,
    DOMAIN,
    EVENT_REPORT,
    PLATFORMS,
    SERVICE_SET_HEALTH,
    STALE_CHECK_INTERVAL,
    VALID_STATES,
)
from .health_state import HealthState


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Integration wird nur per Config-Entry eingerichtet (UI)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Registriert den set_health-Service und den Stale-Check."""
    state = HealthState(
        timedelta(minutes=entry.data.get(CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT))
    )
    store: dict[str, Any] = {"state": state}
    hass.data[DOMAIN] = store

    async def _handle_set_health(call: ServiceCall) -> None:
        state.set(call.data["state"])
        hass.bus.async_fire(EVENT_REPORT)

    await hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEALTH,
        _handle_set_health,
        schema=vol.Schema({vol.Required("state"): vol.In(list(VALID_STATES))}),
    )

    # Stale-Check: stellt die Entity ohne frischen Report auf "offline" um
    last_published: str | None = None

    async def _check_stale() -> None:
        nonlocal last_published
        current = state.current()
        if current != last_published:
            last_published = current
            hass.bus.async_fire(EVENT_REPORT)
        store["unsub_stale"] = ha_event.async_track_point_in_time(
            hass,
            dt_util.utcnow() + timedelta(seconds=STALE_CHECK_INTERVAL),
            _check_stale,
        )

    store["unsub_stale"] = ha_event.async_track_point_in_time(
        hass, dt_util.utcnow() + timedelta(seconds=STALE_CHECK_INTERVAL), _check_stale
    )

    hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt Plattformen, Stale-Check und den Service."""
    store = hass.data.get(DOMAIN)
    if store and store.get("unsub_stale"):
        store["unsub_stale"]()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
        await hass.services.async_remove(DOMAIN, SERVICE_SET_HEALTH)
    return unloaded
