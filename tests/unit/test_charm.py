# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest import mock

import ops
import ops.testing
import pytest
from ops.model import BlockedStatus

from charm import (
    CLOUD_NAME,
    OS_CLIENT_CONFIG,
    SNAP_NAME,
    OpenstackExporterOperatorCharm,
    SnapError,
)
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
        mock_upstream_service = mocker.Mock(spec_set=SnapService)
        mock_upstream_service.present = False
        mock_get_installed_snap_service.side_effect = (
            lambda snap: mock_snap_service if snap == SNAP_NAME else mock_upstream_service
        )

        mocker.patch("charm.OpenstackExporterOperatorCharm.install")

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

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.OpenstackExporterOperatorCharm.install")
    def test_config_changed_snap_channel(self, mock_install, _):
        """Test config changed when the snap channel changes.

        This should also update the snap_channel in _stored.
        """
        self.harness.begin()
        self.harness.update_config({"snap_channel": "latest/edge"})
        mock_install.assert_called_once()

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.OpenstackExporterOperatorCharm.install")
    def test_config_changed_upstream_resource(self, mock_install, mocked_installed_snap):
        """Test config change when using the upstream resource."""
        mocked_upstream = mock.MagicMock()
        mocked_upstream.present = True
        mocked_installed_snap.return_value = mocked_upstream
        self.harness.update_config({"snap_channel": "latest/edge"})
        mock_install.assert_not_called()

    @mock.patch("charm.OpenstackExporterOperatorCharm.get_resource", return_value="")
    @mock.patch("charm.snap_install_or_refresh")
    def test_install_snap(self, mock_install, _):
        self.harness.begin()
        self.harness.charm.on.install.emit()
        mock_install.assert_called_with("", "latest/stable")

    @mock.patch("charm.snap_install_or_refresh")
    def test_install_snap_error(self, mock_install):
        mock_install.side_effect = SnapError("My Error")
        self.harness.begin()
        self.harness.charm.on.install.emit()
        expected_msg = "Failed to remove/install openstack-exporter snap"
        assert self.harness.charm.unit.status == BlockedStatus(expected_msg)
