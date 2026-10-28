"""Config-Flow für health_checker (eine Instanz: die Health-Checker-App)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_STALE_TIMEOUT, DEFAULT_STALE_TIMEOUT, DOMAIN, UNIQUE_ID

USER_SCHEMA = vol.Schema(
    {
        # Minuten ohne Report, nach denen die Status-Entity "offline" wird
        vol.Required(CONF_STALE_TIMEOUT, default=DEFAULT_STALE_TIMEOUT): int,
    }
)


class HealthCheckerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Bittet um die Stale-Zeit für die Status-Entity."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(UNIQUE_ID)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="HealthChecker", data=user_input)
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)
