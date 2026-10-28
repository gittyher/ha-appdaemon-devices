"""HealthChecker – Device "HealthChecker" zur Überwachung der Shelly-Geräte.

Die Integration liest die Shelly-Geräte aus dem Device-/Entity-Registry
(Auto-Discovery) und stellt sie als Liste bereit (sensor.health_checker_devices,
Attribut `devices`). Eine App auf dem AppDaemon-Server (health_checker) pollt
die Erreichbarkeit (alle Entities eines Geräts "unavailable" = Gerät offline)
und meldet den Zustand je Gerät per Service `health_checker.set_state` zurück –
angezeigt im Status-Sensor (sensor.health_checker_status) mit Stale-Check
(ohne frischen Report "offline").
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import event as ha_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_STALE_TIMEOUT,
    DEFAULT_STALE_TIMEOUT,
    DEVICE_STATE_DOWN,
    DEVICE_STATE_OK,
    DOMAIN,
    EVENT_DEVICES,
    EVENT_REPORT,
    MANUFACTURER_FILTER,
    PLATFORMS,
    SERVICE_SET_STATE,
    STALE_CHECK_INTERVAL,
    VALID_STATES,
)
from .health_state import HealthState

# Registry-Update-Events (Geräte-/Entity-Registry) – Typen der Event-Payloads
RegistryEvent = Event[dr.EventDeviceRegistryUpdatedData] | Event[
    er.EventEntityRegistryUpdatedData
]


def _validate_timestamp(value: Any) -> str:
    """Validiert einen ISO-8601-Zeitstempel (z. B. vom AppDaemon-Server)."""
    if not isinstance(value, str):
        raise vol.Invalid("timestamp muss eine ISO-8601-String sein")
    try:
        datetime.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid(f"Ungültiger ISO-8601-Zeitstempel: {value!r}") from err
    return value


def _discover_shelly_devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Findet die Shelly-Geräte im Device-/Entity-Registry (Auto-Discovery).

    Ein Gerät zählt als Shelly, wenn sein Hersteller MANUFACTURER_FILTER
    enthält (case-insensitive). Liefert pro Gerät den Anzeigenamen und die
    zugehörigen aktiven Entities – die App prüft daraus die Erreichbarkeit.
    """
    dreg = dr.async_get(hass)
    ereg = er.async_get(hass)
    devices: list[dict[str, Any]] = []
    for device in dreg.devices.values():
        manufacturer = (device.manufacturer or "").lower()
        if MANUFACTURER_FILTER not in manufacturer:
            continue
        entity_ids = sorted(
            entry.entity_id
            for entry in ereg.entities.values()
            if entry.device_id == device.id and not entry.disabled_by
        )
        if not entity_ids:
            continue
        name = device.name_by_user or device.name or "Shelly-Gerät"
        devices.append({"name": name, "entities": entity_ids})
    devices.sort(key=lambda d: d["name"].lower())
    return devices


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Integration wird nur per Config-Entry eingerichtet (UI)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Registriert den set_state-Service, entdeckt Shelly-Geräte, Stale-Check."""
    state = HealthState(
        timedelta(minutes=entry.data.get(CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT))
    )
    store: dict[str, Any] = {
        "state": state,
        "devices": [],
        "devices_state": {},
        "down_since": {},
        "unsub_stale": None,
        "unsub_registry": [],
    }
    store["devices"] = _discover_shelly_devices(hass)
    hass.data[DOMAIN] = store

    async def _handle_set_state(call: ServiceCall) -> None:
        sent_at: datetime | None = None
        if (raw := call.data.get("timestamp")) is not None:
            # Vom Schema bereits validiert (ISO-8601)
            sent_at = datetime.fromisoformat(raw)
        if (overall := call.data.get("overall")) is not None:
            state.set(overall, sent_at)
        elif sent_at is not None:
            # Partial ohne overall: Zustand behalten, Stale-Zeit auffrischen
            state.touch(sent_at)
        if (devices := call.data.get("devices")) is not None:
            # Voll-Report der App: Geräte-Zustände komplett neu aufbauen,
            # damit nicht mehr gemeldete Geräte nicht hängen bleiben.
            devices_state: dict[str, str] = {}
            down_since: dict[str, str] = {}
            for device in devices:
                name = device["name"]
                device_state = device["state"]
                devices_state[name] = device_state
                if device_state == DEVICE_STATE_DOWN:
                    down_since[name] = device.get("since") or store["down_since"].get(
                        name
                    )
            store["devices_state"] = devices_state
            store["down_since"] = down_since
        hass.bus.async_fire(EVENT_REPORT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STATE,
        _handle_set_state,
        schema=vol.Schema(
            {
                vol.Optional("devices"): [
                    vol.Schema(
                        {
                            vol.Required("name"): cv.string,
                            vol.Required("state"): vol.In(
                                [DEVICE_STATE_OK, DEVICE_STATE_DOWN]
                            ),
                            vol.Optional("since"): _validate_timestamp,
                        }
                    )
                ],
                vol.Optional("overall"): vol.In(list(VALID_STATES)),
                vol.Optional("timestamp"): _validate_timestamp,
            }
        ),
    )

    # Auto-Discovery live halten: bei Änderungen am Device-/Entity-Registry
    # (neues Shelly-Gerät, Entity umgezogen) die Geräteliste neu berechnen.
    @callback
    def _handle_registry_update(_event: RegistryEvent) -> None:
        store["devices"] = _discover_shelly_devices(hass)
        hass.bus.async_fire(EVENT_DEVICES)

    store["unsub_registry"] = [
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _handle_registry_update
        ),
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, _handle_registry_update
        ),
    ]

    # Stale-Check: stellt die Status-Entity ohne frischen Report auf "offline" um
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
    """Entfernt Plattformen, Registry-Listener, Stale-Check und den Service."""
    store = hass.data.get(DOMAIN)
    if store:
        if store.get("unsub_stale"):
            store["unsub_stale"]()
        for unsub in store.get("unsub_registry", []):
            unsub()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
        hass.services.async_remove(DOMAIN, SERVICE_SET_STATE)
    return unloaded
