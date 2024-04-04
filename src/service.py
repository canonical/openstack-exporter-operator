"""Utility module to help manage the snap service with guarding functions."""

import os
from logging import getLogger
from typing import Any, Optional

from charms.operator_libs_linux.v2 import snap

logger = getLogger(__name__)


class SnapService:
    """A class representing the snap service(s)."""

    def __init__(self, client: snap.Snap) -> None:
        """Initialize the class."""
        self.snap_client = client

    def is_active(self) -> bool:
        """Return True if all snap service(s) is / are active."""
        return all(service.get("active", False) for service in self.snap_client.services.values())

    def restart_and_enable(self) -> None:
        """Restart and enable the snap service.

        Ensure:
        - service is running
        - service is enabled
        - service is restarted if already running to apply updated config
        """
        # This is safe to always run,
        # because restarting when service is disabled has no effect,
        # and restarting when enabled but stopped has the same effect as start.
        self.snap_client.restart()
        # This is idempotent, so ok to always run to ensure it's started and enabled
        self.snap_client.start(enable=True)

    def stop(self) -> None:
        """Stop and disable the snap service."""
        self.snap_client.stop(disable=True)

    def configure(self, snap_config: dict[str, Any]) -> None:
        """Configure the snap service."""
        # Bail out or it will crash on self.snap_client.set() method
        if not snap_config:
            logger.warning("empty snap config: %s, skipping...", snap_config)
            return

        self.snap_client.set(snap_config, typed=True)


def snap_install(resource: str) -> SnapService:
    """Install or refresh the snap, and return the snap service.

    Raises an exception on error.
    """
    try:
        logger.debug("installing snap.")
        logger.debug("fetching from resource.")
        snap_client = snap.install_local(resource, dangerous=True)
    except snap.SnapError as e:
        logger.error("failed to install snap: %s", str(e))
        raise e  # need to crash on_install event if it's not okay
    else:
        logger.info("installed %s snap.", snap_client.name)
        workaround_bug_268()
        return SnapService(snap_client)


def get_installed_snap_service(snap_name: str) -> Optional[SnapService]:
    """Return the snap service of the snap if it's installed."""
    try:
        snap_client = snap.SnapCache()[snap_name]
    except snap.SnapNotFoundError as e:
        logger.warning("unable to get snap client: %s", str(e))
        return None

    if not snap_client.present:
        logger.warning("snap %s not installed", snap_name)
        return None

    return SnapService(snap_client)


def workaround_bug_268() -> None:
    """Workaround for a bug that blocks some nova metrics.

    https://github.com/openstack-exporter/openstack-exporter/issues/268
    """
    logger.info("Adding service override to workaround bug 268")
    dir = "/etc/systemd/system/snap.golang-openstack-exporter.service.service.d"
    os.makedirs(dir, exist_ok=True)
    with open(f"{dir}/bug_268.conf", "w") as f:
        f.write("[Service]\nEnvironment=OS_COMPUTE_API_VERSION=2.87\n")
