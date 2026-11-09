"""Constants for the Pro OS Connect integration."""

import logging

DOMAIN = "pro_os_connect"
LOGGER = logging.getLogger(__package__)

CONF_MAX_SETPOINT = "max_setpoint"
CONF_MIN_SETPOINT = "min_setpoint"

CONF_SCAN_INTERVAL_IDLE = "scan_interval_idle"
CONF_SCAN_INTERVAL_RUNNING = "scan_interval_running"

# Polling intervals in seconds
DEFAULT_SCAN_INTERVAL_IDLE = 10
DEFAULT_SCAN_INTERVAL_RUNNING = 5

# Time the device needs to apply a command before its telemetry reflects it
COMMAND_SETTLE_TIME = 0.1

# The fume extractor setpoint (flow rate in m³/h) is always a multiple of this
SETPOINT_STEP = 10

ZEROCONF_HOSTNAME_PREFIX = "bofa_"
