#!/usr/bin/env python3
#
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""OpenStack Exporter Operator.

This charm provides charmed-openstack-exporter snap as part of the Charmed
OpenStack deployment.
"""

import logging
import os
from typing import Any

import ops
import yaml
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    WaitingStatus,
)

from service import (
    SNAP_NAME,
    SnapResource,
    get_installed_snap_service,
    snap_install_or_refresh,
)

logger = logging.getLogger(__name__)

RESOURCE_NAME = "openstack-exporter"
# Snap config options global constants
# This is to match between openstack-exporter and the entry in clouds.yaml
CLOUD_NAME = "openstack"
# store the clouds.yaml where it's easily accessible by the openstack-exporter snap
# This is the SNAP_COMMON directory for the exporter snap, which is accessible,
# unversioned, and retained across updates of the snap.
OS_CLIENT_CONFIG = f"/var/snap/{SNAP_NAME}/common/clouds.yaml"


class OpenstackExporterOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: tuple[Any]) -> None:
        """Initialize the charm."""
        super().__init__(*args)

        self._grafana_agent = COSAgentProvider(
            self,
            metrics_endpoints=[
                {"path": "/metrics", "port": self.config["port"]},
            ],
        )

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade)
        self.framework.observe(self.on.config_changed, self._configure)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)
        self.framework.observe(self.on.credentials_relation_changed, self._configure)
        self.framework.observe(self.on.credentials_relation_broken, self._configure)
        self.framework.observe(self.on.cos_agent_relation_changed, self._configure)
        self.framework.observe(self.on.cos_agent_relation_broken, self._configure)

    def _is_keystone_data_ready(self, data: dict[str, str]) -> bool:
        """Check if all the data is available from keystone.

        Data is validated as unit relation data from the keystone-admin interface.
        """
        return all(
            data.get(x)
            for x in [
                "service_protocol",
                "service_hostname",
                "service_port",
                "service_username",
                "service_password",
                "service_project_name",
                "service_project_domain_name",
                "service_user_domain_name",
                "service_region",
            ]
        )

    def _write_cloud_config(self, data: dict[str, str]) -> None:
        """Build a standard clouds.yaml given the keystone credentials data.

        This is used by the exporter to connect to the openstack cloud,
        including credentials, keystone endpoint, ca certificate, region.

        Only api version 3 is supported,
        since v2 was removed a long time ago (Queens release)
        https://docs.openstack.org/keystone/latest/contributor/http-api.html
        """
        auth_url = "{protocol}://{hostname}:{port}/v3".format(
            protocol=data["service_protocol"],
            hostname=data["service_hostname"],
            port=data["service_port"],
        )
        contents = {
            "clouds": {
                CLOUD_NAME: {
                    "region_name": data["service_region"],
                    "identity_api_version": "3",
                    "identity_interface": "internal",
                    "auth": {
                        "username": data["service_username"],
                        "password": data["service_password"],
                        "project_name": data["service_project_name"],
                        "project_domain_name": data["service_project_domain_name"],
                        "user_domain_name": data["service_user_domain_name"],
                        "auth_url": auth_url,
                    },
                    "verify": data["service_protocol"] == "https",
                    "cacert": self.config["ssl_ca"],
                }
            }
        }

        os.makedirs(os.path.dirname(OS_CLIENT_CONFIG), exist_ok=True)
        with open(OS_CLIENT_CONFIG, "w") as f:
            yaml.dump(contents, f)

    def _get_keystone_data(self) -> dict[str, str]:
        """Get keystone data if ready, otherwise empty dict."""
        # The double loop is because credentials are in the unit data,
        # and not all units are guaranteed to have this data.
        # So we pick the first one that has the data we need.
        for rel in self.model.relations.get("credentials", []):
            for unit in rel.units:
                data = rel.data[unit]
                if self._is_keystone_data_ready(data):
                    return data
        return {}

    def install(self) -> None:
        """Install the necessary resources for the charm."""
        try:
            resource = SnapResource(RESOURCE_NAME, self.model)
            snap_install_or_refresh(resource, self.model.config["snap_channel"])
        except Exception as e:
            logging.error("Failed to install/refresh openstack-exporter snap: %s", e)
            self.model.unit.status = BlockedStatus(
                "Failed to install/refresh openstack-exporter snap"
            )

    def _configure(self, _: ops.HookEvent) -> None:
        """Configure the charm.

        An idempotent method called as the result of several config or relation changed hooks.
        It will install the exporter if not already installed or refresh the channel if the it was
        changed.
        """
        self.install()

        snap_service = get_installed_snap_service(SNAP_NAME)

        # if cos is not related then we should block and not run anything
        if not self.model.relations.get("cos-agent"):
            snap_service.stop()
            return

        snap_service.configure(
            {
                "cloud": CLOUD_NAME,
                "os-client-config": str(OS_CLIENT_CONFIG),
                "web": {"listen-address": f":{self.model.config['port']}"},
                "cache": self.model.config["cache"],
                "cache-ttl": self.model.config["cache_ttl"],
            }
        )

        data = self._get_keystone_data()
        if not data:
            logger.info("Keystone credentials are not available, stopping services.")
            snap_service.stop()
            return

        logger.info("Keystone credentials are available, starting services.")
        self._write_cloud_config(data)
        snap_service.restart_and_enable()

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle install charm event."""
        self.install()

    def _on_upgrade(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle upgrade charm event."""
        self.install()

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent) -> None:
        """Handle collect unit status event (called after every event)."""
        if not self.model.relations.get("credentials"):
            event.add_status(BlockedStatus("Keystone is not related"))
            return

        if not self._get_keystone_data():
            event.add_status(WaitingStatus("Waiting for credentials from keystone"))
            return

        if not self.model.relations.get("cos-agent"):
            event.add_status(BlockedStatus("Grafana Agent is not related"))
            return

        resource = SnapResource(RESOURCE_NAME, self.model)
        if resource and resource.snap_name != SNAP_NAME:
            event.add_status(BlockedStatus(f"snap resource {resource.snap_name} is not valid."))
            return

        snap_service = get_installed_snap_service(SNAP_NAME)
        if not snap_service.present:
            event.add_status(
                BlockedStatus("snap service is not installed, please check snap service")
            )
            return
        if not snap_service.is_active():
            event.add_status(
                BlockedStatus("snap service is not running, please check snap service")
            )
            return

        event.add_status(ActiveStatus())


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpenstackExporterOperatorCharm)
