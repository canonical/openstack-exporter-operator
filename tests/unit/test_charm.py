# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import ops
import ops.testing
import pytest

from charm import CLOUD_NAME, OS_CLIENT_CONFIG, SNAP_NAME, OpenstackExporterOperatorCharm
from service import SnapService


class TestCharm:
    def setup_method(self, _):
        self.harness = ops.testing.Harness(OpenstackExporterOperatorCharm)

    def teardown_method(self, _):
        self.harness.cleanup()

    @pytest.mark.parametrize(
        "config",
        [
            ({"cache": False, "cache_ttl": "100s"}),
            ({"cache": True, "cache_ttl": "200s"}),
        ],
    )
    def test_config_changed(self, config, mocker):
        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_snap_service = mocker.Mock(spec_set=SnapService)
        mock_get_installed_snap_service.return_value = mock_snap_service

        self.harness.begin()

        # mock get_keystone_data
        mock_expect_keystone_data = mocker.Mock()
        self.harness.charm._get_keystone_data = mocker.Mock()
        self.harness.charm._get_keystone_data.return_value = mock_expect_keystone_data

        # mock _write_cloud_config
        self.harness.charm._write_cloud_config = mocker.Mock()

        self.harness.add_relation("cos-agent", "openstack-exporter")

        self.harness.update_config(config)
        self.harness.charm.on.config_changed.emit()

        mock_get_installed_snap_service.assert_called_with(SNAP_NAME)
        mock_snap_service.configure.assert_called_with(
            {
                "cloud": CLOUD_NAME,
                "os-client-config": str(OS_CLIENT_CONFIG),
                "web": {"listen-address": f":{config.get('port', 9180)}"},
                "cache": config["cache"],
                "cache-ttl": config["cache_ttl"],
            }
        )
        self.harness.charm._write_cloud_config.assert_called_with(mock_expect_keystone_data)
        mock_snap_service.restart_and_enable.assert_called()
        mock_snap_service.stop.assert_not_called()
