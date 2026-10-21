"""Tests for the Pro OS Connect fan platform."""

from datetime import timedelta
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pro_os_connect import ProOSConnectTimeoutError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.pro_os_connect.const import COMMAND_SETTLE_TIME

ENTITY_ID = "fan.pro_os_connect_2511000618"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.FAN]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fan entity."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("telemetry_overrides", [{"is_running": 0}])
@pytest.mark.usefixtures("init_integration")
async def test_fan_off(hass: HomeAssistant) -> None:
    """Test the fan reports zero speed when the extractor is stopped."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(hass: HomeAssistant, mock_pro_os_connect: MagicMock) -> None:
    """Test turning on the fan without a speed keeps the setpoint."""
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_pro_os_connect.pump_start.assert_called_once()
    mock_pro_os_connect.set_setpoint.assert_not_called()


@pytest.mark.parametrize(
    ("service", "percentage", "setpoint"),
    [
        pytest.param(SERVICE_TURN_ON, 100, 370, id="turn_on_max"),
        pytest.param(SERVICE_TURN_ON, 1, 10, id="turn_on_min"),
        pytest.param(SERVICE_SET_PERCENTAGE, 50, 190, id="set_percentage_half"),
        pytest.param(SERVICE_SET_PERCENTAGE, 3, 20, id="set_percentage_round_up"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_speed(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    service: str,
    percentage: int,
    setpoint: int,
) -> None:
    """Test setting the fan speed sets the setpoint and starts the extractor."""
    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert mock_pro_os_connect.set_setpoint.mock_calls == [call(setpoint)]
    mock_pro_os_connect.pump_start.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_refresh_after_command(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the telemetry is refreshed once the commands have settled."""
    mock_pro_os_connect.get_telemetry.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 100},
        blocking=True,
    )

    # The device needs time to apply the commands before reporting them
    mock_pro_os_connect.get_telemetry.assert_not_called()

    freezer.tick(timedelta(seconds=COMMAND_SETTLE_TIME))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Setting the setpoint and starting the pump are refreshed together
    mock_pro_os_connect.get_telemetry.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PERCENTAGE] == 100


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(SERVICE_TURN_OFF, {}, id="turn_off"),
        pytest.param(SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 0}, id="percentage_0"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    service: str,
    data: dict[str, int],
) -> None:
    """Test turning off the fan stops the extractor."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )

    mock_pro_os_connect.pump_stop.assert_called_once()
    mock_pro_os_connect.set_setpoint.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_command_error(
    hass: HomeAssistant, mock_pro_os_connect: MagicMock
) -> None:
    """Test a failing command raises an error and closes the connection."""
    mock_pro_os_connect.pump_stop.side_effect = ProOSConnectTimeoutError("Timeout")

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the Pro OS Connect device: Timeout",
    ):
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    mock_pro_os_connect.disconnect.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_update_error(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the fan becomes unavailable when the telemetry cannot be read."""
    mock_pro_os_connect.get_telemetry.side_effect = OSError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    mock_pro_os_connect.disconnect.assert_called_once()
