"""Configuración desde la UI: se pega el ID o el link del producto."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .api import ProductNotFound, WalmartBlocked, WalmartClient, WalmartError, parse_product_id
from .const import (
    CONF_PRODUCT_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

CONF_PRODUCT = "product"


class WalmartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Agregar un producto."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            product_id = parse_product_id(user_input[CONF_PRODUCT])
            if product_id is None:
                errors[CONF_PRODUCT] = "invalid_product"
            else:
                await self.async_set_unique_id(product_id)
                self._abort_if_unique_id_configured()
                client = WalmartClient(async_get_clientsession(self.hass))
                try:
                    product = await client.async_get_product(product_id)
                except ProductNotFound:
                    errors[CONF_PRODUCT] = "not_found"
                except WalmartBlocked:
                    errors["base"] = "blocked"
                except WalmartError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=product.name,
                        data={CONF_PRODUCT_ID: product.product_id},
                        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PRODUCT): TextSelector()}),
            errors=errors,
            description_placeholders={"example": "https://www.walmart.com.mx/ip/…/00800440001437"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return WalmartOptionsFlow()


class WalmartOptionsFlow(OptionsFlow):
    """Cada cuánto se consulta el producto."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})

        actual = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=actual): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=5,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
