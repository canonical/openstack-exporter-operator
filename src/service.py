"""Utility module to help manage the snap service with guarding functions."""

from functools import wraps
from logging import getLogger
from typing import Any, Callable, Optional

from charms.operator_libs_linux.v2 import snap

logger = getLogger(__name__)


def guard_client(func: Callable) -> Callable:
    """Ensure the we can get the snap client before running a snap operation."""

    @wraps(func)
    def wrapper(self: "SnapService", *args: Any, **kwargs: dict[Any, Any]) -> None:
        fn = func.__name__  # This should be a verb
        if not self.snap_client:
            logger.error(
                "cannot %s %s because it's unable to get snap client", fn, self.service_name
            )
            return
        logger.info("%s %s", fn, self.service_name)
        return func(self, *args, **kwargs)

    return wrapper


def guard_installed(func: Callable) -> Callable:
    """Ensure the snap is installed before running a snap operation."""

    @wraps(func)
    def wrapper(self: "SnapService", *args: Any, **kwargs: dict[Any, Any]) -> None:
        fn = func.__name__  # This should be a verb
        if not self.check_installed():
            logger.error("cannot %s %s because it's not installed", fn, self.service_name)
            return
        logger.info("%s %s", fn, self.service_name)
        return func(self, *args, **kwargs)

    return wrapper


class SnapService:
    """A class representing the a snap service (only support one service)."""

    def __init__(self, name: str, service_name: str) -> None:
        """Initialize the class."""
        self.name = name
        self.service_name = service_name
        self.snap_client = self.get_client()

    def get_client(self) -> Optional[snap.Snap]:
        """Return the snap client, or None if the snap cannot be found."""
        try:
            client = snap.SnapCache()[self.name]
        except snap.SnapNotFoundError as e:
            logger.warning("unable to get snap client: %s", str(e))
            return None
        return client

    def install(self, resource: str) -> None:
        """Install or refresh the snap."""
        try:
            logger.debug("installing snap.")
            logger.debug("fetching from resource.")
            snap_client = snap.install_local(resource, dangerous=True)
        except snap.SnapError as e:
            logger.error("failed to install snap: %s", str(e))
            raise e  # need to crash on_install event if it's not okay
        else:
            self.snap_client = snap_client
            logger.info("installed %s snap.", self.name)

    @guard_client
    @guard_installed
    def remove(self) -> None:
        """Remove the snap."""
        try:
            snap.remove([self.name])
        except snap.SnapError as e:
            logger.info("failed to remove snap.")
            logger.error(str(e))
        else:
            logger.info("removed %s snap.", self.name)

    @guard_client
    def check_active(self) -> bool:
        """Return True if the snap service is active."""
        return self.snap_client.services.get(self.service_name, {}).get("active", False)  # type: ignore

    @guard_client
    def check_installed(self) -> bool:
        """Return True if the snap is installed."""
        return self.snap_client.present  # type: ignore

    @guard_client
    @guard_installed
    def start(self, enable: bool = True) -> None:
        """Start and enable the snap service."""
        self.snap_client.start(enable=enable)  # type: ignore

    @guard_client
    @guard_installed
    def stop(self, disable: bool = True) -> None:
        """Stop and disable the snap service."""
        self.snap_client.stop(disable=disable)  # type: ignore

    @guard_client
    @guard_installed
    def configure(self, snap_config: dict[str, Any]) -> None:
        """Configure the snap service."""
        # Store is previous state, for later use.
        previously_active = self.check_active()

        self.snap_client.set(snap_config, typed=True)  # type: ignore

        # Changing snap configuration will also restart the snap service, so we
        # need to explicitly preserve the state of the snap service.
        if not previously_active:
            self.stop()
