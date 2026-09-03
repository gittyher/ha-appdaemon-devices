"""Konstanten für die python_script_server-Integration."""

from homeassistant.const import Platform

from .health_state import STATE_ERROR, STATE_OK

CONF_STALE_TIMEOUT = "stale_timeout"  # Minuten ohne Report -> "offline"

DOMAIN = "python_script_server"
NAME = "PythonScriptServer"
VERSION = "0.1.0"

UNIQUE_ID = "python_script_server"
DEFAULT_STALE_TIMEOUT = 5  # Minuten
STALE_CHECK_INTERVAL = 60  # Sekunden

SERVICE_SET_HEALTH = "set_health"
EVENT_REPORT = f"{DOMAIN}_report"
VALID_STATES = (STATE_OK, STATE_ERROR)

PLATFORMS = [Platform.SENSOR]
