#!/usr/bin/env python3
#
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""OpenStack Exporter Operator.

This charm provide golang-openstack-exporter snap as part of the Charmed
OpenStack deployment.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import ops
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    ModelError,
)
from service import get_installed_snap_service, snap_install

logger = logging.getLogger(__name__)

# Miscellaneous constants
USER_HOME = Path().home()

# charm global constants
RESOURCE_NAME = "openstack-exporter"

# snap global constants
SNAP_NAME = "golang-openstack-exporter"
SNAP_SERVICE_NAME = "service"


# Snap config options global constants
CLOUD_NAME = "openstack"
OS_CLIENT_CONFIG = USER_HOME / "clouds.yaml"


class OpenstackExporterOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: tuple[Any]) -> None:
        """Initialize the charm."""
        super().__init__(*args)

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

    def get_resource(self) -> Optional[str]:
        """Return the path-to-resource or None if the resource is empty.

        Fetch the charm's resource and check if the resource is an empty file
        or not. If it's empty, return None. Otherwise, return the path to the
        resource.
        """
        try:
            snap_path = self.model.resources.fetch(RESOURCE_NAME).absolute()
        except ModelError:
            logger.warning("cannot fetch charm resource")
            return None

        if not os.path.getsize(snap_path) > 0:
            logger.warning("resource is an empty file")
            return None

        return snap_path

    def install(self) -> None:
        """Install or upgrade charm."""
        resource = self.get_resource()
        if not resource:
            raise ValueError("resource is invalid or not found.")
        snap_install(resource, SNAP_SERVICE_NAME)

    def configure(self, event: ops.HookEvent) -> None:
        """Configure the charm."""
        snap_service = get_installed_snap_service(SNAP_NAME, SNAP_SERVICE_NAME)

        if not snap_service:
            logger.warning("snap is not installed, defer configuring the charm.")
            event.defer()
            return

        snap_config = self.get_validated_snap_config()
        if not snap_config:
            logger.error("invalid charm config, check `juju debug-log`")
            return
        snap_service.configure(snap_config)

        # TODO: properly start and stop the service depends on the relations to
        # keystone and grafana-agent.
        snap_service.start()

    def get_validated_snap_config(self) -> dict[str, Any]:
        """Get validated snap config from charm config, or empty dict if it's not valid."""
        log_level = self.model.config["log-level"].lower()
        web_listen_address = f":{self.model.config['port']}"
        log_level_choices = {"debug", "info", "warn", "error"}
        if log_level not in log_level_choices:
            logger.error("invalid config `log-level`, must be in {log_level_choices}")
            return {}
        return {
            "cloud": CLOUD_NAME,
            "log": {"level": log_level},
            "web": {"listen-address": web_listen_address},
            "os-client-config": str(OS_CLIENT_CONFIG),
        }

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install charm event."""
        self.install()

    def _on_upgrade(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade charm event."""
        self.install()

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changed event."""
        self.configure(event)

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect unit status event (called after every event)."""
        snap_service = get_installed_snap_service(SNAP_NAME, SNAP_SERVICE_NAME)

        if not snap_service:
            event.add_status(BlockedStatus("snap service is installed, please check snap service"))
        elif not snap_service.is_active():
            event.add_status(
                BlockedStatus("snap service is not running, please check snap service")
            )

        if not self.get_validated_snap_config():
            event.add_status(BlockedStatus("invalid charm config, please check `juju debug-log`"))

        event.add_status(ActiveStatus())


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpenstackExporterOperatorCharm)
