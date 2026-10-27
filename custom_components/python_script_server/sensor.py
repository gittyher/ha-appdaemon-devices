"""Sensoren des Devices "PythonScriptServer": 'Zustand' (Health), 'Skript-
Version' (zentrale Version des auf dem Server laufenden Scripts) und 'Apps'
(App-Übersicht: installierte/laufende Apps).

Die Werte kommen per Push vom PythonScriptServer (AppDaemon)
(Service set_health bzw. set_apps); das Entity-Polling ist deaktiviert.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_REPORT, UNIQUE_ID
from .health_state import STATE_OFFLINE, HealthState

DEVICE_INFO = DeviceInfo(
    identifiers={(DOMAIN, UNIQUE_ID)},
    name="PythonScriptServer",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Erzeugt die Health-, die Skript-Versions- und die Apps-Entity."""
    store: dict[str, Any] = hass.data[DOMAIN]
    async_add_entities(
        [
            PythonScriptServerHealthSensor(store["state"]),
            PythonScriptServerVersionSensor(store),
            PythonScriptServerAppsSensor(store),
        ]
    )


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
        self._attr_device_info = DEVICE_INFO

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


class PythonScriptServerVersionSensor(SensorEntity):
    """Zentrale Skript-Version des auf dem AppDaemon-Server laufenden Scripts.

    Wird vom Script mit jedem Report gemeldet (Service-Feld `version`);
    bis zum ersten Report "unknown". Die Version wird beim Deploy automatisch
    aus der Commit-Distance abgeleitet (install/derive_version.sh).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "script_version"
    _attr_unique_id = f"{UNIQUE_ID}_script_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:tag-text"
    _attr_should_poll = False

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._attr_native_value = STATE_UNKNOWN
        self._attr_device_info = DEVICE_INFO

    async def async_added_to_hass(self) -> None:
        # Initialen Wert (ggf. bereits empfangene Version) einspielen
        self._handle_report(None)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_REPORT, self._handle_report)
        )

    @callback
    def _handle_report(self, _event: Event | None) -> None:
        version = self._store.get("version")
        self._attr_native_value = version if version is not None else STATE_UNKNOWN
        self.async_write_ha_state()


class PythonScriptServerAppsSensor(SensorEntity):
    """App-Übersicht: Zustand = Anzahl laufender Apps; Attribute = Listen.

    Die Werte kommen per Service set_apps vom Reporter (AppDaemon-Server):
    `installed_apps` = in apps.yaml registrierte Apps, `running_apps` =
    Apps mit aktiver initialize()-Instanz. `not_running_apps` wird hier
    berechnet (Differenz). Bis zum ersten set_apps-Report "unknown".
    """

    _attr_has_entity_name = True
    _attr_translation_key = "apps"
    _attr_unique_id = f"{UNIQUE_ID}_apps"
    _attr_icon = "mdi:apps"
    _attr_should_poll = False

    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store
        self._attr_native_value = STATE_UNKNOWN
        self._attr_extra_state_attributes = {
            "installed_apps": [],
            "running_apps": [],
            "not_running_apps": [],
        }
        self._attr_device_info = DEVICE_INFO

    async def async_added_to_hass(self) -> None:
        # Initialen Wert (ggf. bereits empfangene Reports) einspielen
        self._handle_report(None)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_REPORT, self._handle_report)
        )

    @callback
    def _handle_report(self, _event: Event | None) -> None:
        installed = self._store.get("installed_apps")
        running = self._store.get("running_apps")
        if installed is None or running is None:
            self._attr_native_value = STATE_UNKNOWN
            installed, running = [], []
        else:
            self._attr_native_value = len(running)
        self._attr_extra_state_attributes = {
            "installed_apps": sorted(installed),
            "running_apps": sorted(running),
            "not_running_apps": sorted(set(installed) - set(running)),
        }
        self.async_write_ha_state()
