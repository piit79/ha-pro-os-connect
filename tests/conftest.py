"""Fixtures for the Pro OS Connect integration tests."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from pro_os_connect.common import TelemetryFields
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_json_object_fixture,
)
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.pro_os_connect.const import CONF_MAX_SETPOINT, DOMAIN

HOST = "10.10.103.35"
SERIAL_NUMBER = "2511000618"
MAX_SETPOINT = 370


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the custom integration in all tests."""


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return the snapshot fixture with the Home Assistant extension."""
    # Whether syrupy's or Home Assistant's plugin fixture wins depends on plugin load order
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"Pro OS Connect {SERIAL_NUMBER}",
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_MAX_SETPOINT: MAX_SETPOINT},
        unique_id=SERIAL_NUMBER,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("custom_components.pro_os_connect.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def telemetry_overrides() -> dict[str, int | float]:
    """Return telemetry fields to override in the fixture data."""
    return {}


@pytest.fixture
def mock_pro_os_connect(
    telemetry_overrides: dict[str, int | float],
) -> Generator[MagicMock]:
    """Return a mocked Pro OS Connect client."""
    with (
        patch(
            "custom_components.pro_os_connect.ProOSConnect", autospec=True
        ) as client_mock,
        patch(
            "custom_components.pro_os_connect.config_flow.ProOSConnect",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.get_protocol_version.return_value = 1
        client.get_serial_number.return_value = SERIAL_NUMBER
        client.get_telemetry.return_value = TelemetryFields(
            **(load_json_object_fixture("telemetry.json") | telemetry_overrides)
        )

        def _set_setpoint(setpoint: int) -> bool:
            # The device clamps the setpoint to its maximum
            client.get_telemetry.return_value = replace(
                client.get_telemetry.return_value,
                setpoint=min(setpoint, MAX_SETPOINT),
            )
            return True

        client.set_setpoint.side_effect = _set_setpoint
        client.pump_start.return_value = True
        client.pump_stop.return_value = True
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.FAN, Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pro_os_connect: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Pro OS Connect integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.pro_os_connect.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
