"""Foto del producto."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WalmartConfigEntry, WalmartProductCoordinator
from .entity import WalmartEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WalmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WalmartImage(hass, entry.runtime_data)])


class WalmartImage(WalmartEntity, ImageEntity):
    def __init__(self, hass: HomeAssistant, coordinator: WalmartProductCoordinator) -> None:
        WalmartEntity.__init__(self, coordinator, "photo")
        ImageEntity.__init__(self, hass)
        self._attr_image_url = coordinator.data.image_url
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        url = self.coordinator.data.image_url
        if url and url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
