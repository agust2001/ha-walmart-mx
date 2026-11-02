"""Base común: cada producto es un dispositivo con varias entidades."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WalmartProductCoordinator


class WalmartEntity(CoordinatorEntity[WalmartProductCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: WalmartProductCoordinator, key: str) -> None:
        super().__init__(coordinator)
        data = coordinator.data
        self._attr_unique_id = f"{coordinator.product_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.product_id)},
            name=data.name,
            manufacturer=data.brand or "Walmart México",
            model=coordinator.product_id,
            configuration_url=data.url,
            entry_type=DeviceEntryType.SERVICE,
        )
