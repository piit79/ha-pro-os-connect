"""The Pro OS Connect integration."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from pro_os_connect import ProOSConnect

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
