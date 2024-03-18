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
from functools import cached_property
from typing import Any, Optional

import ops
from config import RESOURCE_NAME, SNAP_NAME, SNAP_SERVICE_NAME
from pydantic import ValidationError
from service import SnapService

logger = logging.getLogger(__name__)


def serialize_status(status: ops.model.StatusBase) -> tuple[str, str]:
    """Serialize `model.StatusBase` for storage."""
    return status.name, status.message


def deserialize_status(serialized_status: tuple[str, str]) -> ops.model.StatusBase:
    """Deserialize a tuple of (name, message) to `ops.model.StatusBase`."""
    name, message = serialized_status
    return ops.model.StatusBase.from_name(name, message)


class OpenstackExporterOperatorCharm(ops.CharmBase):
    """Charm the service."""

    _stored = ops.framework.StoredState()

    def __init__(self, *args: tuple[Any]) -> None:
        """Initialize the charm."""
        super().__init__(*args)
        self.snap_service = SnapService(
            SNAP_NAME,
            SNAP_SERVICE_NAME,
        )

        self._stored.set_default(
            config={},
            status={
                "config": serialize_status(ops.model.ActiveStatus()),
            },
        )

        self.framework.observe(self.on.remove, self._on_remove)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

    @cached_property
    def resource(self) -> Optional[str]:
        """Return the path-to-resource or None if the resource is empty.

        Fetch the charm's resource and check if the resource is an empty file
        or not. If it's empty, return None. Otherwise, return the path to the
        resource.

        Note: the property is cached for each invocation of a hook.

        Returns
        -------
            snap_path (str or None)

        """
        try:
            snap_path = self.model.resources.fetch(RESOURCE_NAME).absolute()
            if not os.path.getsize(snap_path) > 0:
                return None
        except ops.model.ModelError:
            return None
        else:
            return snap_path

    def configure(self, _: ops.HookEvent) -> None:
        """Configure the charm."""
        changed_config = self.get_changed_config()
        if not self.resource and "snap-channel" in changed_config:
            self.snap_service.install(self.model.config["snap-channel"], self.resource)

        try:
            self._stored.status["config"] = serialize_status(
                ops.model.MaintenanceStatus("configuring charm")
            )
            self.snap_service.configure(self.model.config)
        except ValidationError as e:
            self._stored.status["config"] = serialize_status(
                ops.model.BlockedStatus("invalid charm config, check `juju debug-log`")
            )
            logger.error(e)
            return
        self._stored.status["config"] = serialize_status(ops.model.ActiveStatus())

        # TODO: properly start and stop the service depends on the relations to
        # keystone and grafana-agent.
        self.snap_service.start()

    def get_changed_config(self) -> dict[str, Any]:
        """Return a dictionary of changed config.

        Update the juju store about the "config" data, and returns the config
        options that were changed during the config changed event.

        Returns
        -------
            changed_config (dict): A dictionary of changed config.

        """
        changed_config = {}
        for k, v in self.model.config.items():
            if k not in self._stored.config or self._stored.config[k] != v:
                self._stored.config[k] = v
                changed_config[k] = v
        return changed_config

    def _on_remove(self, _: ops.RemoveEvent) -> None:
        """Handle remove charm event."""
        self.snap_service.uninstall(self.model.config.get("channel"), resource=self.resource)

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install charm event."""
        self.snap_service.install(self.model.config.get("channel"), resource=self.resource)

    def _on_upgrade(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade charm event."""
        self.snap_service.install(self.model.config.get("channel"), resource=self.resource)

    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        """Handle update status event."""
        if self.unit.status != ops.model.ActiveStatus():
            self.configure(event)

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        """Handle config changed event."""
        self.configure(event)

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect unit status event (called after every event)."""
        for status in self._stored.status.values():
            event.add_status(deserialize_status(status))

        if self.snap_service.installed and not self.snap_service.active:
            event.add_status(
                ops.model.BlockedStatus("snap service is not running, please check snap service")
            )


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpenstackExporterOperatorCharm)
