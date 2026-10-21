"""Sensor platform for the Pro OS Connect integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfRatio, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow
from pro_os_connect.common import TelemetryFields

from .coordinator import ProOSConnectConfigEntry, ProOSConnectDataUpdateCoordinator
from .entity import ProOSConnectEntity

PARALLEL_UPDATES = 0

# Avoid state changes caused by jitter in the computed boot time
UPTIME_DEVIATION = timedelta(seconds=5)


@dataclass(frozen=True, kw_only=True)
class ProOSConnectSensorEntityDescription(SensorEntityDescription):
    """Describes a Pro OS Connect sensor entity."""

    value_fn: Callable[[TelemetryFields], float | int]


SENSORS: tuple[ProOSConnectSensorEntityDescription, ...] = (
    ProOSConnectSensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.flow_rate if data.is_running else 0,
    ),
    ProOSConnectSensorEntityDescription(
        key="compensated_combined_blockage",
        translation_key="combined_blockage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.compensated_combined_blockage,
    ),
    ProOSConnectSensorEntityDescription(
        key="compensated_pre_blockage",
        translation_key="pre_blockage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.compensated_pre_blockage,
    ),
    ProOSConnectSensorEntityDescription(
        key="pump_level",
        translation_key="pump_level",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pump_level,
    ),
    ProOSConnectSensorEntityDescription(
        key="real_combined_blockage",
        translation_key="real_combined_blockage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.real_combined_blockage,
    ),
    ProOSConnectSensorEntityDescription(
        key="real_pre_blockage",
        translation_key="real_pre_blockage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.real_pre_blockage,
    ),
    ProOSConnectSensorEntityDescription(
        key="real_inlet_blockage",
        translation_key="real_inlet_blockage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.real_inlet_blockage,
    ),
    ProOSConnectSensorEntityDescription(
        key="alarms",
        translation_key="alarms",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alarms,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProOSConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pro OS Connect sensors based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(
                ProOSConnectSensorEntity(coordinator, description)
                for description in SENSORS
            ),
            ProOSConnectUptimeSensorEntity(coordinator),
        ]
    )


class ProOSConnectSensorEntity(ProOSConnectEntity, SensorEntity):
    """Defines a Pro OS Connect sensor."""

    entity_description: ProOSConnectSensorEntityDescription

    def __init__(
        self,
        coordinator: ProOSConnectDataUpdateCoordinator,
        description: ProOSConnectSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | int:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class ProOSConnectUptimeSensorEntity(ProOSConnectEntity, SensorEntity):
    """Defines a Pro OS Connect sensor reporting the device boot time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "uptime"
    _boot_time: datetime | None = None

    def __init__(self, coordinator: ProOSConnectDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "uptime")

    @property
    @override
    def native_value(self) -> datetime:
        """Return the boot time of the device."""
        # The telemetry timestamp is the uptime in hundredths of a second
        boot_time = utcnow() - timedelta(seconds=self.coordinator.data.timestamp / 100)
        if (
            self._boot_time is None
            or abs(boot_time - self._boot_time) > UPTIME_DEVIATION
        ):
            self._boot_time = boot_time
        return self._boot_time
