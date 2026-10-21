"""Tests for the Pro OS Connect config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, call

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pro_os_connect import (
    ProOSConnectConnectError,
    ProOSConnectResponseError,
    ProOSConnectTimeoutError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pro_os_connect.const import CONF_MAX_SETPOINT, DOMAIN

from .conftest import HOST, MAX_SETPOINT, SERIAL_NUMBER

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MAX_SETPOINT_PROBE = 2**31 - 1

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    port=2345,
    hostname=f"bofa_{SERIAL_NUMBER}.local.",
    name=f"bofa_{SERIAL_NUMBER}._iq2._tcp.local.",
    properties={},
    type="_iq2._tcp.local.",
)


@pytest.mark.parametrize("telemetry_overrides", [{"is_running": 0}])
async def test_user_flow(hass: HomeAssistant, mock_pro_os_connect: MagicMock) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Pro OS Connect {SERIAL_NUMBER}"
    assert result["data"] == {CONF_HOST: HOST, CONF_MAX_SETPOINT: MAX_SETPOINT}
    assert result["result"].unique_id == SERIAL_NUMBER
    # The original setpoint is restored after probing the maximum
    assert mock_pro_os_connect.set_setpoint.mock_calls == [
        call(MAX_SETPOINT_PROBE),
        call(200),
    ]


async def test_user_flow_running(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test the user flow asks for confirmation when the extractor is running."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_running"
    mock_pro_os_connect.set_setpoint.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_MAX_SETPOINT: MAX_SETPOINT}
    assert result["result"].unique_id == SERIAL_NUMBER
    assert mock_pro_os_connect.set_setpoint.mock_calls == [
        call(MAX_SETPOINT_PROBE),
        call(200),
    ]


@pytest.mark.parametrize(
    ("method", "side_effect", "return_value", "error"),
    [
        pytest.param(
            "get_protocol_version",
            ProOSConnectConnectError,
            None,
            "cannot_connect",
            id="connect_error",
        ),
        pytest.param(
            "get_protocol_version",
            ProOSConnectTimeoutError,
            None,
            "cannot_connect",
            id="timeout_error",
        ),
        pytest.param(
            "get_serial_number",
            ProOSConnectResponseError,
            None,
            "cannot_connect",
            id="response_error",
        ),
        pytest.param(
            "get_protocol_version", None, None, "cannot_connect", id="no_protocol"
        ),
        pytest.param("get_serial_number", None, "", "cannot_connect", id="no_serial"),
        pytest.param("get_telemetry", None, None, "cannot_connect", id="no_telemetry"),
        pytest.param("get_protocol_version", Exception, None, "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    method: str,
    side_effect: type[Exception] | None,
    return_value: str | None,
    error: str,
) -> None:
    """Test the user flow handles errors and can recover."""
    mock_method = getattr(mock_pro_os_connect, method)
    original_return_value = mock_method.return_value
    mock_method.side_effect = side_effect
    mock_method.return_value = return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    # The connection is closed even if a request failed
    mock_pro_os_connect.disconnect.assert_called_once()

    mock_method.side_effect = None
    mock_method.return_value = original_return_value
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_running"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(ProOSConnectTimeoutError, "cannot_connect", id="timeout_error"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_detect_max_setpoint_error(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the flow aborts and restores the setpoint if probing fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )
    mock_pro_os_connect.get_telemetry.side_effect = [
        mock_pro_os_connect.get_telemetry.return_value,
        side_effect,
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert mock_pro_os_connect.set_setpoint.mock_calls == [
        call(MAX_SETPOINT_PROBE),
        call(200),
    ]


async def test_detect_max_setpoint_no_telemetry(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test the flow aborts without changing the setpoint if telemetry is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )
    mock_pro_os_connect.get_telemetry.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_pro_os_connect.set_setpoint.assert_not_called()


@pytest.mark.parametrize("telemetry_overrides", [{"setpoint": 0}])
async def test_detect_max_setpoint_invalid(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test the flow aborts if the device reports an invalid maximum setpoint."""
    mock_pro_os_connect.set_setpoint.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: HOST}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_pro_os_connect")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the user flow aborts and updates the host for a known device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "bofa.local"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "bofa.local"


@pytest.mark.parametrize("telemetry_overrides", [{"is_running": 0}])
async def test_zeroconf_flow(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test the zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "serial_number": SERIAL_NUMBER,
        "host": HOST,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Pro OS Connect {SERIAL_NUMBER}"
    assert result["data"] == {CONF_HOST: HOST, CONF_MAX_SETPOINT: MAX_SETPOINT}
    assert result["result"].unique_id == SERIAL_NUMBER


async def test_zeroconf_flow_running(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test the zeroconf flow asks for confirmation when the extractor is running."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_running"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_MAX_SETPOINT: MAX_SETPOINT}
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(ProOSConnectConnectError, "cannot_connect", id="connect_error"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test the zeroconf confirm step handles errors and can recover."""
    mock_pro_os_connect.get_protocol_version.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_DISCOVERY
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": error}

    mock_pro_os_connect.get_protocol_version.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_running"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_NUMBER


@pytest.mark.usefixtures("mock_pro_os_connect")
async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf discovery updates the host of a known device."""
    mock_config_entry.add_to_hass(hass)
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address("10.10.103.36"),
        ip_addresses=[ip_address("10.10.103.36")],
        port=2345,
        hostname=f"bofa_{SERIAL_NUMBER}.local.",
        name=f"bofa_{SERIAL_NUMBER}._iq2._tcp.local.",
        properties={},
        type="_iq2._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "10.10.103.36"


async def test_zeroconf_flow_not_pro_os_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts for an unexpected hostname."""
    discovery = ZeroconfServiceInfo(
        ip_address=ip_address(HOST),
        ip_addresses=[ip_address(HOST)],
        port=2345,
        hostname="other-device.local.",
        name="other-device._iq2._tcp.local.",
        properties={},
        type="_iq2._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_pro_os_connect_device"
