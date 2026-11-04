"""Walmart México: precio, ofertas e historial de productos de walmart.com.mx."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .coordinator import WalmartConfigEntry, WalmartProductCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.IMAGE, Platform.SENSOR]

# Entidades que existieron en versiones anteriores y ya no se crean.
# 0.2.0: stock/disponibilidad (Walmart la calcula por la sucursal que deduce de la IP, no la elegida).
_REMOVED_KEYS = ("in_stock", "availability")


async def async_setup_entry(hass: HomeAssistant, entry: WalmartConfigEntry) -> bool:
    _remove_old_entities(hass, entry)
    coordinator = WalmartProductCoordinator(hass, entry)
    await coordinator.async_load_stored()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    # sin esperar: las consultas van de a una y no deben demorar el arranque de HA
    if coordinator.is_stale:
        entry.async_create_background_task(hass, coordinator.async_refresh(), coordinator.name)
    return True


def _remove_old_entities(hass: HomeAssistant, entry: WalmartConfigEntry) -> None:
    registry = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        if ent.unique_id.endswith(tuple(f"_{k}" for k in _REMOVED_KEYS)):
            registry.async_remove(ent.entity_id)


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
