"""Konstanten für die health_checker-Integration."""

from homeassistant.const import Platform

from .health_state import STATE_ERROR, STATE_OK

CONF_STALE_TIMEOUT = "stale_timeout"  # Minuten ohne Report -> "offline"

DOMAIN = "health_checker"
NAME = "HealthChecker"

UNIQUE_ID = "health_checker"
DEFAULT_STALE_TIMEOUT = 5  # Minuten
STALE_CHECK_INTERVAL = 60  # Sekunden

SERVICE_SET_STATE = "set_state"
EVENT_REPORT = f"{DOMAIN}_report"
EVENT_DEVICES = f"{DOMAIN}_devices"

# Geräte-Erkennung im Device-Registry: nur Geräte dieses Herstellers
# (case-insensitive) werden als Shelly-Gerät übernommen.
MANUFACTURER_FILTER = "shelly"

# Per-Gerät-Zustände, die die App meldet (Service-Feld `state`)
DEVICE_STATE_OK = "ok"
DEVICE_STATE_DOWN = "down"

VALID_STATES = (STATE_OK, STATE_ERROR)

PLATFORMS = [Platform.SENSOR]
