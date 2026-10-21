"""Tests for the Pro OS Connect integration setup."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pro_os_connect import ProOSConnectTimeoutError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pro_os_connect: MagicMock,
) -> None:
    """Test loading and unloading the config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_pro_os_connect.disconnect.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        pytest.param(ProOSConnectTimeoutError, None, id="timeout_error"),
        pytest.param(None, None, id="no_telemetry"),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pro_os_connect: MagicMock,
    side_effect: type[Exception] | None,
    return_value: None,
) -> None:
    """Test the config entry is retried when the device cannot be reached."""
    mock_pro_os_connect.get_telemetry.side_effect = side_effect
    mock_pro_os_connect.get_telemetry.return_value = return_value
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
