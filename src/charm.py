#!/usr/bin/env python3
#
# Copyright 2024 Canonical
# See LICENSE file for licensing details.
"""OpenStack Exporter Operator.

This charm provide golang-openstack-exporter snap as part of the Charmed
OpenStack deployment.
"""

import logging
from typing import Any

import ops

logger = logging.getLogger(__name__)


class OpenstackExporterOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: tuple[Any]) -> None:
        """Initialize the charm."""
        super().__init__(*args)


if __name__ == "__main__":  # pragma: nocover
    ops.main(OpenstackExporterOperatorCharm)
