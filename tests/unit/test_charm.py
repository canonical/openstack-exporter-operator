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
        with pytest.raises(SnapError, match="My Error"):
            self.harness.charm.on.install.emit()

    @mock.patch("charm.OpenstackExporterOperatorCharm.install")
    def test_on_upgrade(self, mock_install):
        """Test the charm is installed in upgrade event."""
        self.harness.begin()
        upgrade_event = mock.MagicMock()
        self.harness.charm._on_upgrade(upgrade_event)
        mock_install.assert_called_once()

    @pytest.mark.parametrize(
        "config_option, cofig_value",
        [
            ("port", 9180),
            ("port", 8080),
            ("port", 80),
            ("cache_ttl", "300s"),
            ("cache_ttl", "300m"),
            ("cache_ttl", "300h"),
            ("cache_ttl", "300d"),
            ("snap_channel", "latest/stable"),
            ("snap_channel", "latest/candidate"),
            ("snap_channel", "latest/beta"),
            ("snap_channel", "latest/edge"),
        ],
    )
    def test_config_change_with_valid_config(self, config_option, cofig_value, mocker):
        """Test config change with valid config."""
        mocked_upstream_service = mock.MagicMock()
        mocked_upstream_service.present = True
        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_get_installed_snap_service.return_value = mocked_upstream_service
        mock_install = mocker.patch("charm.OpenstackExporterOperatorCharm.install")

        self.harness.begin()
        self.harness.update_config({config_option: cofig_value})

        # If valid config, install method can be called from _configure
        mock_install.assert_called_once()

    @pytest.mark.parametrize(
        "config_option, cofig_value",
        [
            ("port", 0),
            ("port", -1),
            ("port", 65536),
            ("cache_ttl", "300.1s"),
            ("cache_ttl", "300 seconds"),
            ("cache_ttl", "300 s"),
            ("cache_ttl", "300y"),
            ("snap_channel", "invalid/channel"),
            ("snap_channel", "latest-stable"),
            ("snap_channel", "Latest/Beta"),
            ("snap_channel", "latest/edge/"),
        ],
    )
    def test_config_change_with_invalid_config(self, config_option, cofig_value, mocker):
        """Test config change with invalid config."""
        if config_option == "port":
            validate_function = "charm.validate_port"
            error_msg = f"Port must be between 1 and 65535, got {cofig_value}"
        elif config_option == "cache_ttl":
            validate_function = "charm.validate_cache_ttl"
            error_msg = (
                f"cache_ttl must be in format <number><unit> "
                f"where unit is s, m, h, or d, got {cofig_value}"
            )
        elif config_option == "snap_channel":
            validate_function = "charm.validate_snap_channel"
            error_msg = (
                f"Invalid snap_channel, must be one of 'latest/stable', 'latest/candidate', "
                f"'latest/beta', 'latest/edge', got {cofig_value}"
            )

        mock_logger = mocker.patch("charm.logger.error")
        mocker.patch(validate_function, return_value=error_msg)
        mocker.patch("charm.get_installed_snap_service")

        self.harness.begin()
        self.harness.update_config({config_option: cofig_value})
        mock_logger.assert_called_once_with(error_msg)
