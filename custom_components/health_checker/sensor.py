"""Sensoren des Devices "HealthChecker": 'Devices' (Auto-Discovery der
Shelly-Geräte) und 'Status' (Erreichbarkeit der Geräte aus den Reports
der App).

Die Devices-Liste kommt aus dem Device-/Entity-Registry (Auto-Discovery,
ha-seitig); der Status kommt per Push von der HealthChecker-App
(Service set_state); das Entity-Polling ist deaktiviert.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_STATE_DOWN, DOMAIN, EVENT_DEVICES, EVENT_REPORT, UNIQUE_ID
from .health_state import STATE_OFFLINE

DEVICE_INFO = DeviceInfo(
    identifiers={(DOMAIN, UNIQUE_ID)},
    name="HealthChecker",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Erzeugt die Devices- und die Status-Entity."""
    store: dict[str, Any] = hass.data[DOMAIN]
    async_add_entities(
        [
            HealthCheckerDevicesSensor(store),
            HealthCheckerStatusSensor(store),
        ]
    )


class HealthCheckerDevicesSensor(SensorEntity):
    """Gefundene Shelly-Geräte (Auto-Discovery): Zustand = Anzahl, Attribut
    `devices` = [{name, entities}] – die Schnittstelle für die App."""

    _attr_has_entity_name = True
    _attr_translation_key = "devices"
    _attr_unique_id = f"{UNIQUE_ID}_devices"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:server-network"
    _attr_should_poll = False

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {"devices": []}
        self._attr_device_info = DEVICE_INFO

    async def async_added_to_hass(self) -> None:
        # Initialen Stand (ggf. bereits entdeckte Geräte) einspielen
        self._handle_update(None)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_DEVICES, self._handle_update)
        )

    @callback
    def _handle_update(self, _event: Event | None) -> None:
        devices = self._store.get("devices", [])
        self._attr_native_value = len(devices)
        self._attr_extra_state_attributes = {"devices": devices}
        self.async_write_ha_state()


class HealthCheckerStatusSensor(SensorEntity):
    """Erreichbarkeit der Shelly-Geräte: Zustand = ok | error | offline
    (kein frischer Report); Attribute je Gerät.

    Die Werte kommen per Service set_state von der App (AppDaemon-Server):
    `devices_state` (name -> ok/down), `down_since` (name -> ISO-Beginn des
    Ausfalls). `down_devices` wird hier berechnet.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_unique_id = f"{UNIQUE_ID}_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-pulse"
    _attr_should_poll = False

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._attr_native_value = STATE_OFFLINE
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_device_info = DEVICE_INFO

    async def async_added_to_hass(self) -> None:
        # Initialen Zustand (ggf. bereits empfangene Reports) einspielen
        self._handle_report(None)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_REPORT, self._handle_report)
        )

    @callback
    def _handle_report(self, _event: Event | None) -> None:
        state = self._store["state"]
        self._attr_native_value = state.current()
        devices_state: dict[str, str] = self._store.get("devices_state", {})
        down_since: dict[str, str] = self._store.get("down_since", {})
        report = state.last_report
        sent_at = state.last_report_sent_at
        self._attr_extra_state_attributes = {
            "total_devices": len(devices_state),
            "down_devices": sorted(
                name for name, st in devices_state.items() if st == DEVICE_STATE_DOWN
            ),
            "devices": dict(sorted(devices_state.items())),
            "down_since": {
                name: since
                for name, since in down_since.items()
                if devices_state.get(name) == DEVICE_STATE_DOWN
            },
            # Empfangszeit auf HA (UTC) – Basis der Stale-Erkennung
            "last_report": report.isoformat() if report else None,
            # Sendezeit des Reporters (AppDaemon-Server, UTC)
            "last_report_sent": sent_at.isoformat() if sent_at else None,
        }
        self.async_write_ha_state()
