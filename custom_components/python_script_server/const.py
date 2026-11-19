"""Konstanten für die python_script_server-Integration."""

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform

from .health_state import STATE_ERROR, STATE_OK

CONF_STALE_TIMEOUT = "stale_timeout"  # Minuten ohne Report -> "offline"

DOMAIN = "python_script_server"
NAME = "PythonScriptServer"

UNIQUE_ID = "python_script_server"
DEFAULT_STALE_TIMEOUT = 5  # Minuten
STALE_CHECK_INTERVAL = 60  # Sekunden

SERVICE_SET_HEALTH = "set_health"
SERVICE_SET_APPS = "set_apps"
EVENT_REPORT = f"{DOMAIN}_report"
VALID_STATES = (STATE_OK, STATE_ERROR)

# Sammel-Schalter (Feature-Toggles, von der App aus apps.yaml registriert):
# Registrierung (set_switches) darf auch "unknown" sein (Ziel beim Start noch
# nicht lesbar); Updates (set_switch_state) nur "on"/"off" (Status-Mirror).
SERVICE_SET_SWITCHES = "set_switches"
SERVICE_SET_SWITCH_STATE = "set_switch_state"
EVENT_SWITCHES = f"{DOMAIN}_switches"
EVENT_SWITCH_STATE = f"{DOMAIN}_switch_state"
VALID_REGISTRATION_STATES = (STATE_ON, STATE_OFF, STATE_UNKNOWN)
VALID_UPDATE_STATES = (STATE_ON, STATE_OFF)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]
