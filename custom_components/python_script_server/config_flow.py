"""Config-Flow für python_script_server (eine Instanz: der PythonScriptServer-Prozess)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT, DOMAIN, UNIQUE_ID

USER_SCHEMA = vol.Schema(
    {
        # Minuten ohne Report, nach denen die Health-Entity "offline" wird
        vol.Required(CONF_STALE_TIMEOUT, default=DEFAULT_STALE_TIMEOUT): int,
    }
)


class PythonScriptServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Bittet um die Stale-Zeit für die Health-Entity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(UNIQUE_ID)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="PythonScriptServer", data=user_input)
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)
