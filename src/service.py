"""Utility module to help manage the snap service with guarding functions."""

from logging import getLogger
from typing import Any, Optional

from charms.operator_libs_linux.v2 import snap

logger = getLogger(__name__)


class SnapService:
    """A class representing the a snap service (only support one service)."""

    def __init__(self, client: snap.Snap, snap_service: str) -> None:
        """Initialize the class."""
        self.snap_client = client
        self.snap_service = snap_service

    def is_active(self) -> bool:
        """Return True if the snap service is active."""
        return self.snap_client.services.get(self.snap_service, {}).get("active", False)

    def start(self) -> None:
        """Start and enable the snap service."""
        self.snap_client.start([self.snap_service], enable=True)

    def stop(self) -> None:
        """Stop and disable the snap service."""
        self.snap_client.stop([self.snap_service], disable=True)

    def configure(self, snap_config: dict[str, Any]) -> None:
        """Configure the snap service."""
        # Bail out or it will crash on self.snap_client.set() method
        if not snap_config:
            logger.warning("empty snap config: %s, skipping...", snap_config)
            return

        self.snap_client.set(snap_config, typed=True)


def snap_install(resource: str, snap_service: str) -> Optional[SnapService]:
    """Install or refresh the snap, and return the snap service."""
    try:
        logger.debug("installing snap.")
        logger.debug("fetching from resource.")
        snap_client = snap.install_local(resource, dangerous=True)
    except snap.SnapError as e:
        logger.error("failed to install snap: %s", str(e))
        raise e  # need to crash on_install event if it's not okay
    else:
        logger.info("installed %s snap.", snap_client.name)
        return SnapService(snap_client, snap_service)


def get_installed_snap_service(snap_name: str, snap_service: str) -> Optional[SnapService]:
    """Return the snap service of the snap if it's installed."""
    try:
        snap_client = snap.SnapCache()[snap_name]
    except snap.SnapNotFoundError as e:
        logger.warning("unable to get snap client: %s", str(e))
        return None

    if not snap_client.present:
        logger.warning("snap %s not installed", snap_name)
        return None

    return SnapService(snap_client, snap_service)
