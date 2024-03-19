"""Setting for the charm."""
# Copyright 2024 Canonical Ltd.
#
# See LICENSE file for licensing details.

from pathlib import Path

# Miscellaneous constants
USER_HOME = str(Path().home())

# Snap global constants
RESOURCE_NAME = "openstack-exporter"
SNAP_NAME = "golang-openstack-exporter"
SNAP_SERVICE_NAME = "service"

# Snap config options global constants
WEB_TELEMETRY_PATH = "/metrics"
CLOUD_NAME = "openstack"
OS_CLIENT_CONFIG = Path(USER_HOME) / "clouds.yaml"
