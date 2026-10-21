"""Tests for the Pro OS Connect sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

UPTIME_ENTITY_ID = "sensor.pro_os_connect_2511000618_uptime"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.SENSOR]


@pytest.mark.freeze_time("2026-10-21 12:00:00+00:00")
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("telemetry_overrides", [{"is_running": 0}])
@pytest.mark.usefixtures("init_integration")
async def test_flow_rate_not_running(hass: HomeAssistant) -> None:
    """Test the flow rate is reported as zero when the extractor is stopped."""
    state = hass.states.get("sensor.pro_os_connect_2511000618_flow_rate")
    assert state
    assert state.state == "0"


@pytest.mark.freeze_time("2026-10-21 12:00:00+00:00")
@pytest.mark.usefixtures("init_integration")
async def test_uptime(
    hass: HomeAssistant,
    mock_pro_os_connect: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the boot time ignores jitter but follows a reboot."""
    state = hass.states.get(UPTIME_ENTITY_ID)
    assert state
    assert state.state == "2026-10-20T01:42:23+00:00"
    telemetry = mock_pro_os_connect.get_telemetry.return_value

    # The device clock lagging a couple of seconds behind does not change the state
    mock_pro_os_connect.get_telemetry.return_value = replace(
        telemetry, timestamp=telemetry.timestamp + 800
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(UPTIME_ENTITY_ID)
    assert state
    assert state.state == "2026-10-20T01:42:23+00:00"

    mock_pro_os_connect.get_telemetry.return_value = replace(telemetry, timestamp=500)
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(UPTIME_ENTITY_ID)
    assert state
    assert state.state == "2026-10-21T12:00:15+00:00"
