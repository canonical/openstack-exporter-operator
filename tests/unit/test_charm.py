# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from unittest import mock

import ops
import ops.testing
import pytest
from charms.operator_libs_linux.v2.snap import SnapError

from charm import (
    CLOUD_NAME,
    OS_CLIENT_CONFIG,
    SNAP_NAME,
    OpenstackExporterOperatorCharm,
)
from service import SnapService
from service import UPSTREAM_SNAP


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
        mock_get_installed_snap_service = mocker.patch(
            "charm.get_installed_snap_service"
        )
        mock_snap_service = mocker.Mock(spec_set=SnapService)
        mock_upstream_service = mocker.Mock(spec_set=SnapService)
        mock_upstream_service.present = False
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_snap_service if snap == SNAP_NAME else mock_upstream_service
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
        self.harness.charm._write_cloud_config.assert_called_with(
            mock_expect_keystone_data
        )
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
    def test_config_changed_upstream_resource(
        self, mock_install, mocked_installed_snap
    ):
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
        with pytest.raises(SnapError, match="My Error"):
            self.harness.charm.on.install.emit()

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.OpenstackExporterOperatorCharm._get_keystone_data")
    @mock.patch("charm.OpenstackExporterOperatorCharm.get_resource")
    @mock.patch("charm.snap_install_or_refresh")
    def test_on_collect_unit_status(
        self,
        _,
        mock_get_resource,
        mock_get_keystone_data,
        mock_get_installed_snap_service,
    ):
        """Test the _on_collect_unit_status method with different scenarios."""
        # Mock services
        mock_event = mock.MagicMock()
        mock_snap_service = mock.MagicMock()
        mock_upstream_service = mock.MagicMock()
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_upstream_service if snap == UPSTREAM_SNAP else mock_snap_service
        )

        # Set initial values
        mock_get_keystone_data.return_value = {}
        mock_get_resource.return_value = "/path/to/snap/resource"
        mock_upstream_service.present = False
        mock_snap_service.present = True
        mock_snap_service.is_active.return_value = True

        self.harness.begin()

        # Scenario 1: No credentials relation
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus("Keystone is not related")
        )

        # Scenario 2: With credentials relation but no data
        self.harness.add_relation("credentials", "keystone")
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.WaitingStatus("Waiting for credentials from keystone")
        )

        # Scenario 3: No cos-agent relation
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus("Grafana Agent is not related")
        )

        # Scenario 4: With upstream snap present
        mock_upstream_service.present = True
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus(
                "golang-openstack-exporter detected. Please see: "
                "https://charmhub.io/openstack-exporter#known-issues"
            )
        )

        # Scenario 5: Non-default snap channel with resource
        self.harness.update_config({"snap_channel": "latest/edge"})
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus(
                "Snap resource provided, so snap_channel is unused. "
                f"Please unset it: juju config {self.harness.charm.app.name} --reset snap_channel"
            )
        )

        # Scenario 6: Snap not installed
        mock_upstream_service.present = False
        mock_snap_service.present = False
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus(
                f"{SNAP_NAME} snap is not installed. "
                "Please wait for installation to complete, "
                "or manually reinstall the snap if the issue persists."
            )
        )

        # Scenario 7: Snap installed but service not active
        mock_snap_service.present = True
        mock_snap_service.is_active.return_value = False
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(
            ops.BlockedStatus(
                f"{SNAP_NAME} snap service is not active. "
                "Please wait for configuration to complete, "
                "or manually start the service the issue persists."
            )
        )

        # Scenario 8: Everything ok
        mock_snap_service.is_active.return_value = True
        mock_get_keystone_data.return_value = {"random": "data"}
        # Reset snap_channel to default to avoid the resource warning
        self.harness.update_config({"snap_channel": "latest/stable"})
        self.harness.add_relation("cos-agent", "grafana-agent")

        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_called_with(ops.ActiveStatus())
