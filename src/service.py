"""Utility module to help manage the snap service with guarding functions."""

import os
from logging import getLogger
from typing import Any, Optional

import yaml
from charms.operator_libs_linux.v2 import snap
from ops.model import Model, ModelError
from PySquashfsImage import SquashFsImage

logger = getLogger(__name__)

SNAP_NAME = "charmed-openstack-exporter"
# the upstream snap
UPSTREAM_SNAP = "golang-openstack-exporter"


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

    @property
    def present(self) -> bool:
        """Check if the snap client is present or not."""
        return self.snap_client.present


class SnapResource:
    """A class representing the snap resource."""

    def __init__(self, name: str, model: Model) -> None:
        """Initialize the class."""
        self.name = name
        self.model = model

    def __bool__(self) -> bool:
        """Boolean magic method for SnapResource.

        Returns True if it has a name, False otherwise.
        """
        return bool(self.snap_name)

    @property
    def path(self) -> Optional[str]:
        """Get the path of the resource.

        If cannot fetch the resource it returns None.
        """
        try:
            return self.model.resources.fetch(self.name).absolute()
        except ModelError:
            logger.debug("cannot fetch charm resource")
            return None

    @property
    def size(self) -> Optional[int]:
        """Get the snap size."""
        return os.path.getsize(self.path) if self.path else None

    @property
    def snap_name(self) -> Optional[str]:
        """Get the snap name from the resource passed.

        Raise exception if not able to get the snap name
        """
        if self.size is None or self.path is None:
            return None

        try:
            with SquashFsImage.from_file(self.path) as image:
                # on snap files when unsquashfs it's possible to find the snap.yaml file that
                # will have the snap name
                snap_file = [file for file in image if "snap.yaml" == file.name][0].read_text()
                return yaml.safe_load(snap_file)["name"]
        except Exception as e:
            logger.error("Failed to get the snap name from the resource: %s", self.path)
            raise snap.SnapError("") from e


def snap_install_or_refresh(resource: SnapResource, channel: str) -> None:
    """Install or refresh the snap.

    Before installing the snap, it will try to remove the upstream snap that could be installed on
    older versions of this charm.

    If the channel is changed, the snap.add method is able to identify and refresh the charm to the
    new channel.

    Raises an exception on error.
    """
    remove_upstream_snap()

    if not resource:
        # installing from snap store if previously installed from resource is problematic, so
        # it's necessary to remove it first
        remove_snap_as_resource()
        logger.debug("installing %s from snapcraft store", SNAP_NAME)
        snap.add(SNAP_NAME, channel=channel)
    elif resource.snap_name == SNAP_NAME:
        logger.info("installing %s from resource.", resource.snap_name)
        # installing from a resource if installed from snap store previously is not problematic
        snap.install_local(resource.path, dangerous=True)
    else:
        logger.warning("%s is not a valid resource.", resource.snap_name)
        logger.warning(
            "Please remove the current resource to install from snap store or pass a "
            "charmed-openstack-exporter snap file."
        )
        return

    logger.info("installed %s snap.", SNAP_NAME)
    workaround_bug_268()


def remove_upstream_snap() -> None:
    """Remove the old snap from upstream to not conflict with the charmed-openstack-exporter.

    Raises an exception on error.
    """
    try:
        snap.remove([UPSTREAM_SNAP])
    except snap.SnapError as e:
        logger.error(f"failed to remove {UPSTREAM_SNAP} snap: %s", str(e))
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
            snap.remove(SNAP_NAME)
        except snap.SnapError as e:
            logger.error("failed to remove snap as a resource: %s", str(e))
            raise e


def get_installed_snap_service(snap_name: str) -> SnapService:
    """Return the snap service of the snap if it's installed."""
    try:
        snap_client = snap.SnapCache()[snap_name]
    except snap.SnapNotFoundError as e:
        logger.error("unable to get snap client: %s", str(e))
        raise e

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
