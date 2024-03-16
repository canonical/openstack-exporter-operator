"""Utility module to help manage the snap service."""

from abc import ABC, abstractmethod
from functools import wraps
from logging import getLogger
from typing import Any, Callable, Optional

from charms.operator_libs_linux.v2 import snap
from config import ExporterSnapConfig

logger = getLogger(__name__)


def guard(func: Callable) -> Callable:
    """Ensure the snap is installed before running a snap operation."""

    @wraps(func)
    def wrapper(self: "SnapService", *args: Any, **kwargs: dict[Any, Any]) -> None:
        try:
            fn = func.__name__  # This should be a verb
            if not self.installed:
                logger.warning("cannot %s %s because it's not installed", fn, self.service_name)
                return
            func(self, *args, **kwargs)
            logger.info("%s %s", fn, self.service_name)
        except snap.SnapNotFoundError as e:
            logger.error(str(e))
            logger.error("failed to %s %s", fn, self.service_name)

    return wrapper


class Service(ABC):
    """An abstract class defining the spec of a service."""

    @property
    @abstractmethod
    def active(self) -> bool:
        """Return True is the service is active."""

    @property
    @abstractmethod
    def installed(self) -> bool:
        """Return True is the service is installed."""

    @abstractmethod
    def start(self, enable: bool = False) -> None:
        """Start the service and optionally enable the service."""

    @abstractmethod
    def stop(self, disable: bool = False) -> None:
        """Stop the service and optionally disable the service."""

    @abstractmethod
    def install(self, *args: Any) -> None:
        """Install the service."""

    @abstractmethod
    def uninstall(self, *args: Any) -> None:
        """Uninstall the service."""

    @abstractmethod
    def configure(self, *args: Any) -> None:
        """Configure the service."""


class SnapService(Service):
    """A class representing the a snap service (only support one service)."""

    def __init__(self, name: str, service_name: str) -> None:
        """Initialize the class."""
        self.name = name
        self.service_name = service_name

    @property
    def client(self) -> snap.Snap:
        """Get the snap client for the exporter.

        Return:
        ------
            snap client (snap.Snap): The snap client.

        Raises:
        ------
            snap.SnapNotFoundError: Raises `SnapNotFoundError` if the snap
                cannot be found on snap store or locally.

        """
        return snap.SnapCache()[self.name]

    @property
    def active(self) -> bool:
        """Return True if the snap service is active.

        Returns
        -------
            True if the snap is active.

        """
        try:
            service = self.client.services.get(self.service_name)
            if not service.get("active", False):
                logger.warning("snap service is not active.")
                return False
        except snap.SnapNotFoundError as e:
            logger.error("unable to get snap client: %s", str(e))
            return False
        else:
            logger.debug("snap service is active.")
            return True

    @property
    def installed(self) -> bool:
        """Return True if the snap is installed.

        Returns
        -------
            True if the snap is installed.

        """
        try:
            if not self.client.present:
                logger.warning("snap is not installed.")
                return False
        except snap.SnapNotFoundError as e:
            logger.error("unable to get snap client: %s", str(e))
            return False
        else:
            logger.debug("snap is installed.")
            return True

    def install(self, channel: str, resource: Optional[str]) -> None:
        """Install or refresh the snap.

        Args:
        ----
            channel (str): The channel of the snap.
            resource (str or None): The path-to-resource for the local snap (optional).

        Returns:
        -------
            None

        """
        logger.info("installing snap.")
        try:
            if resource:
                logger.info("fetching from resource.")
                snap.install_local(resource, dangerous=True)
            else:
                logger.info("fetching from snap store.")
                snap.add([self.name], channel=channel)
        except snap.SnapError as e:
            logger.info("failed to snap installed.")
            logger.error(str(e))
        else:
            logger.info("installed %s snap.", self.name)

    @guard
    def uninstall(self) -> None:
        """Remove the snap."""
        snap.remove([self.name])

    @guard
    def start(self, enable: bool = True) -> None:
        """Start and enable the snap service.

        Args:
        ----
            enable (bool): Enable the service as well.

        Returns:
        -------
            None

        """
        self.client.start(enable=enable)

    @guard
    def stop(self, disable: bool = True) -> None:
        """Stop and disable the snap service.

        Args:
        ----
            disable (bool): Disable the service as well.

        Returns:
        -------
            None

        """
        self.client.stop(disable=disable)

    @guard
    def configure(self, config: dict[str, Any]) -> None:
        """Configure the snap service.

        Args:
        ----
            config (dict): The config options.

        Returns:
        -------
            None

        """
        previously_active = self.active
        snap_config = ExporterSnapConfig.from_charm_config(config)
        self.client.set(snap_config.dict(by_alias=True), typed=True)

        # Changing snap configuration will also restart the snap service, so we
        # need to explicitly preserve the state of the snap service.
        if not previously_active:
            self.stop()
