"""Switch-Platform des PythonScriptServer-Devices (Sammel-Schalter).

Die Schalter-Entities entstehen dynamisch aus den Registrierungen der App
(Service `set_switches`, Full-List-Replacement): je `key` eine SwitchEntity,
alle unter dem PythonScriptServer-Gerät.

Semantik (Status-Mirror + Befehlskanal):
- Der Zustand spiegelt den von der App gemeldeten Ist-Zustand des Ziels
  (Service `set_switch_state` -> EVENT_SWITCH_STATE).
- Schaltet der User, aktualisiert die Entity optimistisch (async_turn_on/off)
  – das ist der Befehlskanal zur App; die App spiegelt danach den echten
  Zustand zurück (ggf. zurück auf den vorherigen, wenn der Befehl fehlschlug).
- Noch nicht lesbare Ziele (Registrierung mit "unknown") werden als
  "unknown" angezeigt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_SWITCH_STATE, EVENT_SWITCHES, UNIQUE_ID

DEVICE_INFO = DeviceInfo(
    identifiers={(DOMAIN, UNIQUE_ID)},
    name="PythonScriptServer",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Erzeugt die dynamische Schalter-Verwaltung für den Domain-Store."""
    store: dict[str, Any] = hass.data[DOMAIN]
    manager = PythonScriptServerSwitchManager(hass, async_add_entities, store)
    entry.async_on_unload(await manager.async_setup())


class PythonScriptServerSwitchManager:
    """Hält die Schalter-Entities zur Registrierungsliste synchron.

    Auf EVENT_SWITCHES (set_switches) werden neue Schalter ergänzt, entfernte
    gelöscht. Die Schalter selbst aktualisieren ihren Zustand über
    EVENT_SWITCH_STATE (set_switch_state).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        async_add_entities: AddEntitiesCallback,
        store: dict[str, Any],
    ) -> None:
        self._hass = hass
        self._async_add_entities = async_add_entities
        self._store = store
        self._entities: dict[str, PythonScriptServerSwitch] = {}

    async def async_setup(self) -> Callable[[], None]:
        """Abonniert die Registrierungs-Updates und erzeugt die Start-Entities."""
        unsub = self._hass.bus.async_listen(EVENT_SWITCHES, self._on_switches)
        await self._reconcile()
        return unsub

    async def _on_switches(self, _event: Event) -> None:
        await self._reconcile()

    async def _reconcile(self) -> None:
        registry = self._store["switches"]
        desired = set(registry)
        existing = set(self._entities)
        for key in desired - existing:
            entity = PythonScriptServerSwitch(self._store, key, registry[key])
            self._entities[key] = entity
            self._async_add_entities([entity])
        for key in existing - desired:
            entity = self._entities.pop(key)
            # Vollständig entfernen (inkl. Entity-Registry), damit ein aus
            # apps.yaml entfernter Schalter wirklich verschwindet.
            reg = er.async_get(self._hass)
            if reg.async_get(entity.entity_id):
                reg.async_remove(entity.entity_id)
            await entity.async_remove(force_remove=True)


class PythonScriptServerSwitch(SwitchEntity):
    """Ein Sammel-Schalter des PythonScriptServer-Devices.

    Status-Mirror + Befehlskanal: der Zustand spiegelt das gemeldete Ziel,
    ein User-Toggle ist der Befehl an die App.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, store: dict[str, Any], key: str, name: str) -> None:
        self._store = store
        self._key = key
        self._attr_unique_id = f"{UNIQUE_ID}_{key}"
        self._attr_device_info = DEVICE_INFO
        # Deterministische Entity-ID: switch.python_script_server_<key> – die App
        # referenziert genau diese ID für den Befehlskanal (listen_state).
        self.entity_id = f"switch.{UNIQUE_ID}_{key}"
        self._attr_name = name
        self._attr_is_on = None
        self._apply_state(store["switch_states"].get(key))

    async def async_added_to_hass(self) -> None:
        # Initialen Zustand (ggf. bereits registrierte Schalter) einspielen
        if self._apply_state(self._store["switch_states"].get(self._key)):
            self.async_write_ha_state()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_SWITCH_STATE, self._handle_report)
        )

    @callback
    def _handle_report(self, _event: Event) -> None:
        if self._apply_state(self._store["switch_states"].get(self._key)):
            self.async_write_ha_state()

    def _apply_state(self, state: str | None) -> bool:
        """Übernimmt den gemeldeten Zustand; True = geändert (schreiben)."""
        if state == STATE_ON:
            want: bool | None = True
        elif state == STATE_OFF:
            want = False
        else:
            want = None
        if want == self._attr_is_on:
            return False
        self._attr_is_on = want
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        # Optimistisch schalten: der Zustand ist der Befehl an die App; die App
        # spiegelt danach den echten Zustand zurück (set_switch_state).
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
