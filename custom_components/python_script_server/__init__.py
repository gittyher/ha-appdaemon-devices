"""PythonScriptServer – Device "PythonScriptServer" mit Health-, Skript-
Versions-, App-Übersichts- und Sammel-Schalter-Entities.

Die Entities werden von einem Script auf dem AppDaemon-Server
(PythonScriptServer) per Service gesetzt:
- python_script_server.set_health: Health (mit Stale-Check, ohne frischen
  Report "offline") und die zentrale Skript-Version des Reporters.
- python_script_server.set_apps: die installierten und laufenden Apps
  (Listen), angezeigt im Apps-Sensor.
- python_script_server.set_switches / set_switch_state: Sammel-Schalter
  (Feature-Toggles aus apps.yaml, Status-Mirror) als Switch-Entities unter
  demselben Gerät.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import event as ha_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_STALE_TIMEOUT,
    DEFAULT_STALE_TIMEOUT,
    DOMAIN,
    EVENT_REPORT,
    EVENT_SWITCH_STATE,
    EVENT_SWITCHES,
    PLATFORMS,
    SERVICE_SET_APPS,
    SERVICE_SET_HEALTH,
    SERVICE_SET_SWITCH_STATE,
    SERVICE_SET_SWITCHES,
    STALE_CHECK_INTERVAL,
    VALID_REGISTRATION_STATES,
    VALID_STATES,
    VALID_UPDATE_STATES,
)
from .health_state import HealthState

_LOGGER = logging.getLogger(__name__)


def _validate_timestamp(value: Any) -> str:
    """Validiert einen ISO-8601-Zeitstempel (z. B. vom AppDaemon-Server)."""
    if not isinstance(value, str):
        raise vol.Invalid("timestamp muss eine ISO-8601-String sein")
    try:
        datetime.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid(f"Ungültiger ISO-8601-Zeitstempel: {value!r}") from err
    return value


def _validate_switch_key(value: Any) -> str:
    """Validiert den Schalter-Key (wird als Entity-ID-Suffix verwendet)."""
    key = cv.string(value)
    if not key or not all(c.isalnum() or c == "_" for c in key):
        raise vol.Invalid(
            "key muss aus [a-z0-9_]+ bestehen (nur Buchstaben, Ziffern, Unterstrich)"
        )
    return key


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Integration wird nur per Config-Entry eingerichtet (UI)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Registriert den set_health-Service und den Stale-Check."""
    state = HealthState(
        timedelta(minutes=entry.data.get(CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT))
    )
    # "version" = zentrale Skript-Version des Reporters (AppDaemon-Server);
    # wird mit jedem Report aktualisiert und in der Text-Entity angezeigt.
    # "installed_apps"/"running_apps" = App-Übersicht aus set_apps.
    store: dict[str, Any] = {
        "state": state,
        "version": None,
        "installed_apps": None,
        "running_apps": None,
        "switches": {},  # key -> Anzeigename
        "switch_states": {},  # key -> "on"|"off"|"unknown"
    }
    hass.data[DOMAIN] = store

    async def _handle_set_health(call: ServiceCall) -> None:
        sent_at: datetime | None = None
        if (raw := call.data.get("timestamp")) is not None:
            # Vom Schema bereits validiert (ISO-8601)
            sent_at = datetime.fromisoformat(raw)
        if (version := call.data.get("version")) is not None:
            store["version"] = version
        state.set(call.data["state"], sent_at)
        hass.bus.async_fire(EVENT_REPORT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEALTH,
        _handle_set_health,
        schema=vol.Schema(
            {
                vol.Required("state"): vol.In(list(VALID_STATES)),
                vol.Optional("timestamp"): _validate_timestamp,
                vol.Optional("version"): cv.string,
            }
        ),
    )

    async def _handle_set_apps(call: ServiceCall) -> None:
        # Partial-Update: nur mitgegebene Felder überschreiben, damit ein
        # Report ohne Felder den zuletzt gemeldeten Stand nicht löscht.
        if (apps := call.data.get("installed_apps")) is not None:
            store["installed_apps"] = apps
        if (apps := call.data.get("running_apps")) is not None:
            store["running_apps"] = apps
        hass.bus.async_fire(EVENT_REPORT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_APPS,
        _handle_set_apps,
        schema=vol.Schema(
            {
                vol.Optional("installed_apps"): [cv.string],
                vol.Optional("running_apps"): [cv.string],
            }
        ),
    )

    async def _handle_set_switches(call: ServiceCall) -> None:
        # Full-List-Replacement: die Liste ist die Source of Truth. Nicht mehr
        # gemeldete Schalter werden aus dem Store entfernt (die Switch-Platform
        # räumt die Entities auf); neue/geänderte werden übernommen.
        new_registry: dict[str, str] = {}
        new_states: dict[str, str] = {}
        for sw in call.data["switches"]:
            new_registry[sw["key"]] = sw["name"]
            new_states[sw["key"]] = sw["state"]
        store["switches"] = new_registry
        store["switch_states"] = new_states
        hass.bus.async_fire(EVENT_SWITCHES)
        hass.bus.async_fire(EVENT_SWITCH_STATE)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCHES,
        _handle_set_switches,
        schema=vol.Schema(
            {
                vol.Required("switches"): [
                    vol.Schema(
                        {
                            vol.Required("key"): _validate_switch_key,
                            vol.Required("name"): cv.string,
                            vol.Required("state"): vol.In(VALID_REGISTRATION_STATES),
                        }
                    )
                ]
            }
        ),
    )

    async def _handle_set_switch_state(call: ServiceCall) -> None:
        key = call.data["key"]
        if key not in store["switches"]:
            _LOGGER.warning(
                "set_switch_state für unbekannten Schalter %r ignoriert", key
            )
            return
        store["switch_states"][key] = call.data["state"]
        hass.bus.async_fire(EVENT_SWITCH_STATE)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCH_STATE,
        _handle_set_switch_state,
        schema=vol.Schema(
            {
                vol.Required("key"): _validate_switch_key,
                vol.Required("state"): vol.In(VALID_UPDATE_STATES),
            }
        ),
    )

    # Stale-Check: stellt die Entity ohne frischen Report auf "offline" um
    last_published: str | None = None

    # HA ruft die Action mit Local-Time auf; für die Terminierung
    # (point_in_time erwartet UTC) immer fresh UTC-Now verwenden
    async def _check_stale(now: datetime) -> None:
        nonlocal last_published
        current = state.current()
        if current != last_published:
            last_published = current
            hass.bus.async_fire(EVENT_REPORT)
        store["unsub_stale"] = ha_event.async_track_point_in_time(
            hass,
            _check_stale,
            dt_util.utcnow() + timedelta(seconds=STALE_CHECK_INTERVAL),
        )

    store["unsub_stale"] = ha_event.async_track_point_in_time(
        hass, _check_stale, dt_util.utcnow() + timedelta(seconds=STALE_CHECK_INTERVAL)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt Plattformen, Stale-Check und den Service."""
    store = hass.data.get(DOMAIN)
    if store and store.get("unsub_stale"):
        store["unsub_stale"]()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
        hass.services.async_remove(DOMAIN, SERVICE_SET_HEALTH)
        hass.services.async_remove(DOMAIN, SERVICE_SET_APPS)
        hass.services.async_remove(DOMAIN, SERVICE_SET_SWITCHES)
        hass.services.async_remove(DOMAIN, SERVICE_SET_SWITCH_STATE)
    return unloaded
