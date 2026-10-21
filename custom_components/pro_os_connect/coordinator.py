"""Data update coordinator for the Pro OS Connect integration."""

import asyncio
from collections.abc import Callable
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pro_os_connect import ProOSConnect, ProOSConnectError
from pro_os_connect.common import TelemetryFields

from .const import COMMAND_SETTLE_TIME, DOMAIN, LOGGER, SCAN_INTERVAL

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
            # Refresh once all commands of a service call have settled
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=COMMAND_SETTLE_TIME, immediate=False
            ),
        )
        self.client = client
        # The client shares a single socket, so calls must not overlap
        self._lock = asyncio.Lock()

    async def async_execute[*Ts, T](self, func: Callable[[*Ts], T], *args: *Ts) -> T:
        """Run a blocking client call."""
        async with self._lock:
            return await self.hass.async_add_executor_job(func, *args)

    async def async_send_command[*Ts](
        self, func: Callable[[*Ts], object], *args: *Ts
    ) -> None:
        """Send a command to the device and refresh the telemetry."""
        try:
            await self.async_execute(func, *args)
        except ProOSConnectError as err:
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
        except ProOSConnectError as err:
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
