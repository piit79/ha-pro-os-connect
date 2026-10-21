"""Constants for the Pro OS Connect integration."""

from datetime import timedelta
import logging

from pro_os_connect import ProOSConnectError, ProOSConnectRequestError

DOMAIN = "pro_os_connect"
LOGGER = logging.getLogger(__package__)

CONF_MAX_SETPOINT = "max_setpoint"

SCAN_INTERVAL = timedelta(seconds=10)

# The fume extractor setpoint (flow rate in m³/h) is always a multiple of this
SETPOINT_STEP = 10

ZEROCONF_HOSTNAME_PREFIX = "bofa_"

# The library doesn't wrap socket errors raised on an already open connection
PRO_OS_CONNECT_ERRORS = (ProOSConnectError, ProOSConnectRequestError, OSError)
