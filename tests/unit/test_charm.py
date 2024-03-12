# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

import ops
import ops.testing
from charm import OpenstackExporterOperatorCharm


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = ops.testing.Harness(OpenstackExporterOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_dummy_install(self):
        """Dummy test case."""
        self.harness.charm.on.install.emit()
