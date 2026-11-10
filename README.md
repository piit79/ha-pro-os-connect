# Pro OS Connect

Home Assistant custom integration for Donaldson BOFA fume extractors with a Pro OS Connect controller.

It polls the controller over the local network every 10 seconds, or every 5 seconds while the extractor is running (both [configurable](#configuration)), and provides:

- **Fan**: turn the extractor on and off, and set the flow rate in steps of 10 m³/h between the device's minimum and maximum setpoint. Setting the speed to 0 sets the minimum setpoint and stops the extractor.
- **Sensors**: flow rate, target flow rate, filter blockage levels, filter pressures (disabled by default), pump level, active alarms and uptime.

Devices are discovered automatically using zeroconf, or can be added manually by host name or IP address.

### Disclaimer

This integration was created using Claude Code.

## Installation

### HACS

1. In Home Assistant Marketplace or HACS (if you're on HA 2026.10 or older), open the menu in the top right corner and select **Custom repositories**.
2. Add `https://github.com/piit79/ha-pro-os-connect` with type **Integration**.
3. Search for **Pro OS Connect**, install it, and restart Home Assistant.

### Manual

Copy `custom_components/pro_os_connect` into the `custom_components` folder of your Home Assistant configuration directory and restart Home Assistant.

## Configuration

Go to **Settings** > **Devices & services** and add the **Pro OS Connect** integration, or confirm the discovered device.

During setup, the integration briefly sets the extractor to its lowest and then its highest setpoint to detect the minimum and maximum flow rate, then restores the original setpoint. If the extractor is running, you are asked to confirm this first.

To change the polling intervals after setup, select **Configure** on the integration entry. The intervals for an idle and a running extractor can be set separately, between 1 and 300 seconds.

## Requirements

Home Assistant 2026.10.0 or newer.

## Development

```shell
uv venv -p 3.14
uv pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
