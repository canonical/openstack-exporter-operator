#!/usr/bin/env python3
# Copyright 2024 Canonical
#
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, app_name):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    # Build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")
    app_name = "openstack-exporter"

    # Deploy the charm and wait for active/idle status
    await asyncio.gather(
        ops_test.model.deploy(charm, application_name=app_name),
        ops_test.model.wait_for_idle(
            apps=[app_name], status="active", raise_on_blocked=True, timeout=1000
        ),
    )
