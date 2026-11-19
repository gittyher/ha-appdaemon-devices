"""AppDaemonDevices – Sammel-Gerät für lose Schalter und Informationen.

Ein einzelnes HA-Device ("AppDaemon Geräte"), das als Platzhalter für
Steuerungen und Daten aus diesem Projekt dient, die keinem eigenen Gerät
zuzuordnen sind. Die AppDaemon-App (apps/appdaemon_devices/generic_devices.py)
meldet die Schalter aus apps.yaml per Service `set_switches` (Full-List-
Replacement inkl. Zustand); die Switch-Platform erzeugt daraus Switch-Entities
(Status-Mirror des Ziels). Schaltet der User, ist das der Befehlskanal zur App;
programmatische Updates der App kommen über `set_switch_state`.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    EVENT_REPORT,
    EVENT_SWITCHES,
    PLATFORMS,
    SERVICE_SET_STATE,
    SERVICE_SET_SWITCHES,
    VALID_REGISTRATION_STATES,
    VALID_UPDATE_STATES,
)

_LOGGER = logging.getLogger(__name__)


def _validate_key(value: Any) -> str:
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
    """Registriert die Schalter-Services; die Switch-Platform legt die Entities an."""
    store: dict[str, Any] = {
        "switches": {},  # key -> Anzeigename
        "states": {},  # key -> "on"|"off"|"unknown"
    }
    hass.data[DOMAIN] = store

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
        store["states"] = new_states
        hass.bus.async_fire(EVENT_SWITCHES)
        hass.bus.async_fire(EVENT_REPORT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SWITCHES,
        _handle_set_switches,
        schema=vol.Schema(
            {
                vol.Required("switches"): [
                    vol.Schema(
                        {
                            vol.Required("key"): _validate_key,
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
        store["states"][key] = call.data["state"]
        hass.bus.async_fire(EVENT_REPORT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_STATE,
        _handle_set_switch_state,
        schema=vol.Schema(
            {
                vol.Required("key"): _validate_key,
                vol.Required("state"): vol.In(VALID_UPDATE_STATES),
            }
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entfernt die Plattform und die Services."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.pop(DOMAIN, None)
        hass.services.async_remove(DOMAIN, SERVICE_SET_SWITCHES)
        hass.services.async_remove(DOMAIN, SERVICE_SET_STATE)
    return unloaded
