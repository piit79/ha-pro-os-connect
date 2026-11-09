"""Fan platform for the Pro OS Connect integration."""

import math
from typing import Any, override

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import CONF_MAX_SETPOINT, CONF_MIN_SETPOINT, SETPOINT_STEP
from .coordinator import ProOSConnectConfigEntry, ProOSConnectDataUpdateCoordinator
from .entity import ProOSConnectEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProOSConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pro OS Connect fan based on a config entry."""
    async_add_entities([ProOSConnectFanEntity(entry.runtime_data)])


class ProOSConnectFanEntity(ProOSConnectEntity, FanEntity):
    """Defines the Pro OS Connect fume extractor fan."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: ProOSConnectDataUpdateCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, "fan")
        self._min_setpoint = coordinator.config_entry.data[CONF_MIN_SETPOINT]
        self._max_setpoint = coordinator.config_entry.data[CONF_MAX_SETPOINT]
        # Speed 1 is the minimum setpoint, each further speed adds a setpoint step
        self._speed_range = (
            1,
            math.ceil((self._max_setpoint - self._min_setpoint) / SETPOINT_STEP) + 1,
        )
        self._attr_speed_count = int_states_in_range(self._speed_range)

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the extractor is running."""
        return bool(self.coordinator.data.is_running)

    @property
    @override
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        data = self.coordinator.data
        if not data.is_running:
            return 0
        return ranged_value_to_percentage(
            self._speed_range, (data.setpoint - self._min_setpoint) / SETPOINT_STEP + 1
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Start the extractor, optionally at the given speed."""
        if percentage == 0:
            await self._async_stop_at_min_setpoint()
            return
        client = self.coordinator.client
        if percentage is not None:
            speed = math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
            setpoint = min(
                self._min_setpoint + (speed - 1) * SETPOINT_STEP, self._max_setpoint
            )
            await self.coordinator.async_send_command(client.set_setpoint, setpoint)
        await self.coordinator.async_send_command(client.pump_start)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the extractor."""
        await self.coordinator.async_send_command(self.coordinator.client.pump_stop)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the extractor."""
        await self.async_turn_on(percentage)

    async def _async_stop_at_min_setpoint(self) -> None:
        """Set the minimum setpoint and stop the extractor."""
        client = self.coordinator.client
        await self.coordinator.async_send_command(
            client.set_setpoint, self._min_setpoint
        )
        await self.coordinator.async_send_command(client.pump_stop)
