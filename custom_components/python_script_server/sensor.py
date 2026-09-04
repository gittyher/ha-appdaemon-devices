"""Sensor 'Zustand' – einzige Entity des Devices "PythonScriptServer".

Der Wert kommt per Push vom PythonScriptServer (AppDaemon)
(Service set_health); das Entity-Polling ist deaktiviert.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_REPORT, UNIQUE_ID
from .health_state import STATE_OFFLINE, HealthState


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Erzeugt die Health-Entity."""
    async_add_entities([PythonScriptServerHealthSensor(hass.data[DOMAIN]["state"])])


class PythonScriptServerHealthSensor(SensorEntity):
    """PythonScriptServer-Prozess-Status: ok | error | offline (kein frischer Report)."""

    _attr_has_entity_name = True
    _attr_translation_key = "health"
    _attr_unique_id = f"{UNIQUE_ID}_health"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-pulse"
    _attr_should_poll = False

    def __init__(self, state: HealthState) -> None:
        self._state_store = state
        self._attr_native_value = STATE_OFFLINE
        self._attr_extra_state_attributes = {
            "last_report": None,
            "last_report_sent": None,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, UNIQUE_ID)},
            name="PythonScriptServer",
        )

    async def async_added_to_hass(self) -> None:
        # Initialen Zustand (ggf. bereits empfangene Reports) einspielen
        self._handle_report(None)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_REPORT, self._handle_report)
        )

    @callback
    def _handle_report(self, _event: Event | None) -> None:
        self._attr_native_value = self._state_store.current()
        report = self._state_store.last_report
        sent_at = self._state_store.last_report_sent_at
        self._attr_extra_state_attributes = {
            # Empfangszeit auf HA (UTC) – Basis der Stale-Erkennung,
            # ISO-String für Templates/Automations
            "last_report": report.isoformat() if report else None,
            # Sendezeit des Reporters (AppDaemon-Server, UTC)
            "last_report_sent": sent_at.isoformat() if sent_at else None,
        }
        self.async_write_ha_state()
