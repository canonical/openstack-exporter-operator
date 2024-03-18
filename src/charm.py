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
from typing import Any, Optional

import ops
from config import RESOURCE_NAME, SNAP_NAME, SNAP_SERVICE_NAME, SnapConfig
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    ModelError,
)
from pydantic import ValidationError
from service import SnapService

logger = logging.getLogger(__name__)


class OpenstackExporterOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: tuple[Any]) -> None:
        """Initialize the charm."""
        super().__init__(*args)
        self.snap_service = SnapService(
            SNAP_NAME,
            SNAP_SERVICE_NAME,
        )

        self.framework.observe(self.on.remove, self._on_remove)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

    def get_resource(self) -> Optional[str]:
        """Return the path-to-resource or None if the resource is empty.

        Fetch the charm's resource and check if the resource is an empty file
        or not. If it's empty, return None. Otherwise, return the path to the
        resource.

        Returns
        -------
            snap_path (str or None)

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

    def configure(self, _: ops.HookEvent) -> None:
        """Configure the charm."""
        resource = self.get_resource()
        channel = self.model.config["snap-channel"]
        if not resource and self.snap_service.get_snap_channel() != channel:
            self.snap_service.install(channel, resource=resource)

        snap_config = self.get_validated_snap_config()
        if not snap_config:
            logger.error("invalid charm config, check `juju debug-log`")
            return
        self.snap_service.configure(snap_config)

        # TODO: properly start and stop the service depends on the relations to
        # keystone and grafana-agent.
        self.snap_service.start()

    def get_validated_snap_config(self) -> Optional[dict[str, Any]]:
        """Get validated snap config from charm config, or None if it's not valid."""
        try:
            snap_config = SnapConfig.from_charm_config(self.model.config)
        except ValidationError:
            return None
        return snap_config.dict(by_alias=True)

    def _on_remove(self, _: ops.RemoveEvent) -> None:
        """Handle remove charm event."""
        self.snap_service.remove()

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install charm event."""
        resource = self.get_resource()
        channel = self.model.config["snap-channel"]
        self.snap_service.install(channel, resource=resource)

    def _on_upgrade(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade charm event."""
        resource = self.get_resource()
        channel = self.model.config["snap-channel"]
        self.snap_service.install(channel, resource=resource)

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changed event."""
        self.configure(event)

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect unit status event (called after every event)."""
        if not self.get_validated_snap_config():
            event.add_status(BlockedStatus("invalid charm config, please check `juju debug-log`"))

        if self.snap_service.check_installed() and not self.snap_service.check_active():
            event.add_status(
                BlockedStatus("snap service is not running, please check snap service")
            )

        event.add_status(ActiveStatus())


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpenstackExporterOperatorCharm)
