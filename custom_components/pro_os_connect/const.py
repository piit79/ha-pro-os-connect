"""Constants for the Pro OS Connect integration."""

from datetime import timedelta
import logging

DOMAIN = "pro_os_connect"
LOGGER = logging.getLogger(__package__)

CONF_MAX_SETPOINT = "max_setpoint"

SCAN_INTERVAL = timedelta(seconds=10)

# Time the device needs to apply a command before its telemetry reflects it
COMMAND_SETTLE_TIME = 0.1

# The fume extractor setpoint (flow rate in m³/h) is always a multiple of this
SETPOINT_STEP = 10

ZEROCONF_HOSTNAME_PREFIX = "bofa_"
