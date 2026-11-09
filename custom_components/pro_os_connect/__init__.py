"""The Pro OS Connect integration."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from pro_os_connect import ProOSConnect

from .const import CONF_MIN_SETPOINT, LOGGER, SETPOINT_STEP
from .coordinator import ProOSConnectConfigEntry, ProOSConnectDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ProOSConnectConfigEntry
) -> bool:
    """Set up Pro OS Connect from a config entry."""
    client = ProOSConnect(entry.data[CONF_HOST])
    coordinator = ProOSConnectDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(client.disconnect)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ProOSConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: ProOSConnectConfigEntry
) -> bool:
    """Migrate an old config entry."""
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        # Entries created before the minimum was detected used the setpoint step as minimum
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_MIN_SETPOINT: SETPOINT_STEP},
            minor_version=2,
        )
        LOGGER.debug("Migrated config entry to version 1.2")

    return True
