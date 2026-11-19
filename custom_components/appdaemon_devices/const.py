"""Konstanten für die appdaemon_devices-Integration."""

from homeassistant.const import Platform

DOMAIN = "appdaemon_devices"
NAME = "AppDaemon Devices"
UNIQUE_ID = "appdaemon_devices"

PLATFORMS = [Platform.SWITCH]

SERVICE_SET_SWITCHES = "set_switches"
SERVICE_SET_STATE = "set_switch_state"
EVENT_SWITCHES = f"{DOMAIN}_switches"
EVENT_REPORT = f"{DOMAIN}_report"

# Von der App gemeldete Schalter-Zustände: Registrierung (set_switches) darf
# auch "unknown" sein (Ziel beim Start noch nicht lesbar); Updates
# (set_switch_state) nur "on"/"off" (Status-Mirror).
STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"
VALID_REGISTRATION_STATES = (STATE_ON, STATE_OFF, STATE_UNKNOWN)
VALID_UPDATE_STATES = (STATE_ON, STATE_OFF)
