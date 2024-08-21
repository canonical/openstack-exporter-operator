"""Utility module to help manage the snap service with guarding functions."""

import os
from logging import getLogger
from typing import Any, Optional

from charms.operator_libs_linux.v2 import snap

logger = getLogger(__name__)

SNAP_NAME = "charmed-openstack-exporter"


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


def snap_install(resource: Optional[str], channel: str) -> SnapService:
    """Install the snap, and return the snap service.

    Before installing the snap, it will try to remove the upstream snap that could be installed on
    older versions of this charm.

    If the channel is changed, the snap.add method is able to identify and refresh the charm to the
    new channel.

    Raises an exception on error.
    """
    remove_upstream_snap()
    try:
        if resource:
            logger.debug("installing %s from resource.", SNAP_NAME)
            # installing from a resource if installed from snap store previously is not problematic
            snap_client = snap.install_local(resource, dangerous=True)
        else:
            # installing from snap store if previously installed from resource is problematic, so
            # it's necessary to remove it first
            remove_snap_as_resource()
            logger.debug("installing %s from snapcraft store", SNAP_NAME)
            snap_client = snap.add(SNAP_NAME, channel=channel)
    except snap.SnapError as e:
        logger.error("failed to install snap: %s", str(e))
        raise e
    else:
        logger.info("installed %s snap.", snap_client.name)
        workaround_bug_268()
        return SnapService(snap_client)


def remove_upstream_snap() -> None:
    """Remove the old snap from upstream to not conflict with the charmed-openstack-exporter.

    Raises an exception on error.
    """
    try:
        snap.remove(["golang-openstack-exporter"])
    except snap.SnapError as e:
        logger.error("failed to remove golang-openstack-exporter snap: %s", str(e))
        raise e


def remove_snap_as_resource() -> None:
    """Remove the snap as resource.

    If the snap as resource is not removed, it's not possible to install from the store and will
    fail. When the revision of a snap has "x" on it e.g. "x1" this means that the snap was
    installed by a local file. The way to return to the one from snapstore is by passing an empty
    file. In such scenario, the local installation will be removed to be able to install from the
    snapstore.
    """
    snap_cache = snap.SnapCache()
    o7k_exporter = snap_cache[SNAP_NAME]
    if o7k_exporter.present and "x" in o7k_exporter.revision:
        logger.info("removing local resource snap before installing from snapstore")
        try:
            print("Trying to remove")
            snap.remove(SNAP_NAME)
        except snap.SnapError as e:
            logger.error("failed to remove snap as a resource: %s", str(e))
            raise e


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
    dir = f"/etc/systemd/system/snap.{SNAP_NAME}.service.service.d"
    os.makedirs(dir, exist_ok=True)
    with open(f"{dir}/bug_268.conf", "w") as f:
        f.write("[Service]\nEnvironment=OS_COMPUTE_API_VERSION=2.87\n")
