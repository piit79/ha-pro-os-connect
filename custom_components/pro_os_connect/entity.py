"""Base entity for the Pro OS Connect integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ProOSConnectDataUpdateCoordinator


class ProOSConnectEntity(CoordinatorEntity[ProOSConnectDataUpdateCoordinator]):
    """Defines a Pro OS Connect entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ProOSConnectDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize the Pro OS Connect entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry.unique_id
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer="Donaldson BOFA",
            model="Pro OS Connect",
            name=entry.title,
            serial_number=entry.unique_id,
        )
