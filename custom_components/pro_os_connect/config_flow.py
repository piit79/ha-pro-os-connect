"""Config flow for the Pro OS Connect integration."""

import time
from typing import Any, override

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pro_os_connect import ProOSConnect, ProOSConnectError
import probatio

from .const import (
    COMMAND_SETTLE_TIME,
    CONF_MAX_SETPOINT,
    DOMAIN,
    LOGGER,
    SETPOINT_STEP,
    ZEROCONF_HOSTNAME_PREFIX,
)

# The device clamps a too high setpoint to its maximum
MAX_SETPOINT_PROBE = 2**31 - 1


class InvalidResponse(Exception):
    """Raised when the device returns an unexpected response."""


def _get_device_info(host: str) -> tuple[str, bool]:
    """Return the serial number and running state of the device."""
    client = ProOSConnect(host)
    try:
        protocol_version = client.get_protocol_version()
        serial_number = client.get_serial_number()
        telemetry = client.get_telemetry()
    finally:
        client.disconnect()
    if protocol_version is None or not serial_number or telemetry is None:
        raise InvalidResponse
    return serial_number, bool(telemetry.is_running)


def _detect_max_setpoint(host: str) -> int:
    """Detect the maximum setpoint of the device, restoring the current one."""
    client = ProOSConnect(host)
    try:
        if (telemetry := client.get_telemetry()) is None:
            raise InvalidResponse
        client.set_setpoint(MAX_SETPOINT_PROBE)
        try:
            time.sleep(COMMAND_SETTLE_TIME)
            probed_telemetry = client.get_telemetry()
        finally:
            client.set_setpoint(telemetry.setpoint)
    finally:
        client.disconnect()
    if probed_telemetry is None or probed_telemetry.setpoint < SETPOINT_STEP:
        raise InvalidResponse
    return probed_telemetry.setpoint


class ProOSConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pro OS Connect."""

    VERSION = 1

    _host: str
    _serial_number: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                serial_number, is_running = await self.hass.async_add_executor_job(
                    _get_device_info, host
                )
            except ProOSConnectError, InvalidResponse:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial_number, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                self._host = host
                self._serial_number = serial_number
                if is_running:
                    return await self.async_step_confirm_running()
                return await self._async_create_entry()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST)
                    ): TextSelector(TextSelectorConfig(autocomplete="off")),
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of a Pro OS Connect device."""
        hostname = discovery_info.hostname.removesuffix(".local.")
        if not hostname.startswith(ZEROCONF_HOSTNAME_PREFIX):
            return self.async_abort(reason="not_pro_os_connect_device")

        # The device hostname contains its serial number
        serial_number = hostname.removeprefix(ZEROCONF_HOSTNAME_PREFIX)
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self._host = discovery_info.host
        self._serial_number = serial_number
        self.context["title_placeholders"] = {"serial_number": serial_number}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup of a discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _, is_running = await self.hass.async_add_executor_job(
                    _get_device_info, self._host
                )
            except ProOSConnectError, InvalidResponse:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if is_running:
                    return await self.async_step_confirm_running()
                return await self._async_create_entry()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "serial_number": self._serial_number,
                "host": self._host,
            },
            errors=errors,
        )

    async def async_step_confirm_running(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm changing the setpoint of a running extractor."""
        if user_input is not None:
            return await self._async_create_entry()
        return self.async_show_form(step_id="confirm_running")

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Detect the maximum setpoint and create the config entry."""
        try:
            max_setpoint = await self.hass.async_add_executor_job(
                _detect_max_setpoint, self._host
            )
        except ProOSConnectError, InvalidResponse:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=f"Pro OS Connect {self._serial_number}",
            data={CONF_HOST: self._host, CONF_MAX_SETPOINT: max_setpoint},
        )
