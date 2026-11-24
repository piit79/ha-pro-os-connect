"""Config flow for the Pro OS Connect integration."""

import time
from typing import Any, override

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pro_os_connect import ProOSConnect, ProOSConnectError
import probatio

from .const import (
    COMMAND_SETTLE_TIME,
    CONF_EXCLUSIVE_ACCESS,
    CONF_MAX_SETPOINT,
    CONF_MIN_SETPOINT,
    CONF_SCAN_INTERVAL_IDLE,
    CONF_SCAN_INTERVAL_RUNNING,
    DEFAULT_EXCLUSIVE_ACCESS,
    DEFAULT_SCAN_INTERVAL_IDLE,
    DEFAULT_SCAN_INTERVAL_RUNNING,
    DOMAIN,
    LOGGER,
    ZEROCONF_HOSTNAME_PREFIX,
)

# The device clamps a too low or too high setpoint to its minimum or maximum
MIN_SETPOINT_PROBE = 1
MAX_SETPOINT_PROBE = 2**31 - 1

SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=1,
        max=300,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement=UnitOfTime.SECONDS,
    )
)


class InvalidResponse(Exception):
    """Raised when the device returns an unexpected response."""


def _get_device_info(host: str) -> tuple[str, bool]:
    """Return the serial number and running state of the device."""
    client = ProOSConnect(host, keep_connection=False)
    with client.hold_connection():
        client.get_protocol_version()
        serial_number = client.get_serial_number()
        telemetry = client.get_telemetry()
    if not serial_number:
        raise InvalidResponse
    return serial_number, telemetry.is_running


def _probe_setpoint(client: ProOSConnect, setpoint: int) -> int:
    """Set a setpoint and return the one the device applied."""
    client.set_setpoint(setpoint, read_back=False)
    time.sleep(COMMAND_SETTLE_TIME)
    return client.get_telemetry().setpoint


def _detect_setpoint_range(host: str) -> tuple[int, int]:
    """Detect the minimum and maximum setpoint, restoring the current one."""
    client = ProOSConnect(host, keep_connection=False)
    original_setpoint = client.get_telemetry().setpoint
    try:
        min_setpoint = _probe_setpoint(client, MIN_SETPOINT_PROBE)
        max_setpoint = _probe_setpoint(client, MAX_SETPOINT_PROBE)
    finally:
        client.set_setpoint(original_setpoint, read_back=False)
    if not 0 < min_setpoint <= max_setpoint:
        raise InvalidResponse
    return min_setpoint, max_setpoint


class ProOSConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pro OS Connect."""

    VERSION = 1
    MINOR_VERSION = 2

    _host: str
    _serial_number: str
    _exclusive_access: bool

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> ProOSConnectOptionsFlow:
        """Return the options flow."""
        return ProOSConnectOptionsFlow()

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
                self._exclusive_access = user_input[CONF_EXCLUSIVE_ACCESS]
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
                    probatio.Required(
                        CONF_EXCLUSIVE_ACCESS,
                        default=user_input.get(
                            CONF_EXCLUSIVE_ACCESS, DEFAULT_EXCLUSIVE_ACCESS
                        ),
                    ): BooleanSelector(),
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
                self._exclusive_access = user_input[CONF_EXCLUSIVE_ACCESS]
                if is_running:
                    return await self.async_step_confirm_running()
                return await self._async_create_entry()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_EXCLUSIVE_ACCESS,
                        default=user_input.get(
                            CONF_EXCLUSIVE_ACCESS, DEFAULT_EXCLUSIVE_ACCESS
                        ),
                    ): BooleanSelector(),
                }
            ),
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
        """Detect the setpoint range and create the config entry."""
        try:
            min_setpoint, max_setpoint = await self.hass.async_add_executor_job(
                _detect_setpoint_range, self._host
            )
        except ProOSConnectError, InvalidResponse:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=f"Pro OS Connect {self._serial_number}",
            data={
                CONF_HOST: self._host,
                CONF_MIN_SETPOINT: min_setpoint,
                CONF_MAX_SETPOINT: max_setpoint,
            },
            options={CONF_EXCLUSIVE_ACCESS: self._exclusive_access},
        )


class ProOSConnectOptionsFlow(OptionsFlowWithReload):
    """Handle the options of a Pro OS Connect config entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling intervals and connection mode."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL_IDLE: int(user_input[CONF_SCAN_INTERVAL_IDLE]),
                    CONF_SCAN_INTERVAL_RUNNING: int(
                        user_input[CONF_SCAN_INTERVAL_RUNNING]
                    ),
                    CONF_EXCLUSIVE_ACCESS: user_input[CONF_EXCLUSIVE_ACCESS],
                }
            )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_SCAN_INTERVAL_IDLE,
                        default=options.get(
                            CONF_SCAN_INTERVAL_IDLE, DEFAULT_SCAN_INTERVAL_IDLE
                        ),
                    ): SCAN_INTERVAL_SELECTOR,
                    probatio.Required(
                        CONF_SCAN_INTERVAL_RUNNING,
                        default=options.get(
                            CONF_SCAN_INTERVAL_RUNNING, DEFAULT_SCAN_INTERVAL_RUNNING
                        ),
                    ): SCAN_INTERVAL_SELECTOR,
                    probatio.Required(
                        CONF_EXCLUSIVE_ACCESS,
                        default=options.get(
                            CONF_EXCLUSIVE_ACCESS, DEFAULT_EXCLUSIVE_ACCESS
                        ),
                    ): BooleanSelector(),
                }
            ),
        )
