"""Config-Flow für appdaemon_devices (eine Instanz: das Sammel-Gerät).

Keine Optionen – die Schalter/Informationen kommen komplett von der
AppDaemon-App (apps.yaml) per Service set_switches.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN, NAME, UNIQUE_ID


class AppdaemonDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Bittet um Bestätigung (leeres Formular, eine Instanz)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(UNIQUE_ID)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
