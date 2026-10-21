# Pro OS Connect

Home Assistant custom integration for Donaldson BOFA fume extractors with a Pro OS Connect controller.

It polls the controller over the local network every 10 seconds and provides:

- **Fan**: turn the extractor on and off, and set the flow rate as a percentage of the device's maximum setpoint.
- **Sensors**: flow rate, filter blockage levels, pump level, active alarms and uptime.

Devices are discovered automatically using zeroconf, or can be added manually by host name or IP address.

## Installation

### HACS

1. In HACS, open the menu in the top right corner and select **Custom repositories**.
2. Add `https://github.com/piit79/ha-pro-os-connect` with type **Integration**.
3. Search for **Pro OS Connect**, install it, and restart Home Assistant.

### Manual

Copy `custom_components/pro_os_connect` into the `custom_components` folder of your Home Assistant configuration directory and restart Home Assistant.

## Configuration

Go to **Settings** > **Devices & services** and add the **Pro OS Connect** integration, or confirm the discovered device.

During setup, the integration briefly sets the extractor to its highest setpoint to detect the maximum flow rate, then restores the original setpoint. If the extractor is running, you are asked to confirm this first.

## Requirements

Home Assistant 2026.10.0 or newer.

## Development

```shell
uv venv -p 3.14
uv pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
