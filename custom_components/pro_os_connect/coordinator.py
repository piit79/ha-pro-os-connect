"""Data update coordinator for the Pro OS Connect integration."""

import asyncio
from collections.abc import Callable
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pro_os_connect import ProOSConnect
from pro_os_connect.common import TelemetryFields

from .const import DOMAIN, LOGGER, PRO_OS_CONNECT_ERRORS, SCAN_INTERVAL

type ProOSConnectConfigEntry = ConfigEntry[ProOSConnectDataUpdateCoordinator]


class ProOSConnectDataUpdateCoordinator(DataUpdateCoordinator[TelemetryFields]):
    """Class to manage fetching Pro OS Connect telemetry."""

    config_entry: ProOSConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ProOSConnectConfigEntry,
        client: ProOSConnect,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Pro OS Connect {entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # The client shares a single socket, so calls must not overlap
        self._lock = asyncio.Lock()

    async def async_execute[*Ts, T](self, func: Callable[[*Ts], T], *args: *Ts) -> T:
        """Run a blocking client call, reconnecting on the next call after an error."""
        async with self._lock:
            try:
                return await self.hass.async_add_executor_job(func, *args)
            except PRO_OS_CONNECT_ERRORS:
                self.client.disconnect()
                raise

    async def async_send_command[*Ts](
        self, func: Callable[[*Ts], object], *args: *Ts
    ) -> None:
        """Send a command to the device and refresh the telemetry."""
        try:
            await self.async_execute(func, *args)
        except PRO_OS_CONNECT_ERRORS as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()

    @override
    async def _async_update_data(self) -> TelemetryFields:
        """Fetch telemetry from the device."""
        try:
            telemetry = await self.async_execute(self.client.get_telemetry)
        except PRO_OS_CONNECT_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        if telemetry is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            )
        return telemetry
