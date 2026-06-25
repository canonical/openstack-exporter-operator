# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""SSDLC (Secure Software Development Lifecycle) Logging.

These events provide critical visibility into the asset's lifecycle and health, and can help
detect potential tampering or malicious activities aimed at altering system behavior.
"""

from datetime import datetime, timezone
from enum import Enum
from logging import getLogger

logger = getLogger(__name__)


class SSDLCSysEvent(str, Enum):  # noqa: N801
    """Constant event defined in SSDLC."""

    STARTUP = "sys_startup"
    SHUTDOWN = "sys_shutdown"
    RESTART = "sys_restart"
    CRASH = "sys_crash"


_EVENT_LEVELS = {
    SSDLCSysEvent.STARTUP: "WARN",
    SSDLCSysEvent.SHUTDOWN: "WARN",
    SSDLCSysEvent.CRASH: "WARN",
    SSDLCSysEvent.RESTART: "WARN",
}


_EVENT_DESCRIPTIONS = {
    SSDLCSysEvent.STARTUP: "openstack-exporter start service %s",
    SSDLCSysEvent.SHUTDOWN: "openstack-exporter shutdown service %s",
    SSDLCSysEvent.RESTART: "openstack-exporter restart service %s",
    SSDLCSysEvent.CRASH: "openstack-exporter service %s crash",
}


class Service(str, Enum):
    """Service names for openstack-exporter charm."""

    CHARMED_OPENSTACK_EXPORTER = "charmed-openstack-exporter"


def log_ssdlc_system_event(
    event: SSDLCSysEvent,
    subject: Service = Service.CHARMED_OPENSTACK_EXPORTER,
    msg: str = "",
) -> None:
    """Log system event in SSDLC required format.

    Args:
        event: The SSDLC system event type
        subject: Service enum (defaults to CHARMED_OPENSTACK_EXPORTER)
        msg: Optional additional message

    """
    level = _EVENT_LEVELS[event]
    description_template = _EVENT_DESCRIPTIONS[event]
    description = f"{description_template % subject.value} {msg}".strip()

    now = datetime.now(timezone.utc).astimezone()

    logger.warning(
        {
            "datetime": now.isoformat(),
            "appid": f"service.{subject.value}",
            "event": f"{event.value}:{subject.value}",
            "level": level,
            "description": description,
        },
    )
