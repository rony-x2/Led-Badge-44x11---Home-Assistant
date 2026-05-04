"""Config flow for the LED Badge integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN


class LedBadgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick an LSLED badge that is currently in Bluetooth transfer mode."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Auto-discovery: badge advertises itself, user just confirms."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered_info = discovery_info
        # Show a nicer name in the discovery card
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        info = self._discovered_info
        assert info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=info.name or info.address,
                data={CONF_ADDRESS: info.address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": info.name or info.address},
        )

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Manual flow with a dropdown of currently visible LSLED badges."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, address),
                data={CONF_ADDRESS: address},
            )

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current:
                continue
            if info.name and "LSLED" in info.name.upper():
                self._discovered[info.address] = (
                    f"{info.name} ({info.address})"
                )

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )
