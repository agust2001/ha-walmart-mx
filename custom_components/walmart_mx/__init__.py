"""Walmart México: precio, ofertas e historial de productos de walmart.com.mx."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import WalmartConfigEntry, WalmartProductCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.IMAGE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WalmartConfigEntry) -> bool:
    coordinator = WalmartProductCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: WalmartConfigEntry) -> None:
    """Al cambiar las opciones (intervalo) se recarga la entrada."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WalmartConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: WalmartConfigEntry) -> None:
    """Al borrar el producto se borra también su historial guardado."""
    from homeassistant.helpers.storage import Store

    from .const import CONF_PRODUCT_ID, DOMAIN, STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.data[CONF_PRODUCT_ID]}").async_remove()
