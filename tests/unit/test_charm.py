# Copyright 2024 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from pathlib import Path
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
from service import UPSTREAM_SNAP, SnapService


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

    @pytest.mark.parametrize(
        "config,relations,test_values,expected_status",
        [
            # Scenario 1: No credentials relation
            (
                {},  # Default config
                [],  # No relations
                {
                    "keystone_data": {},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus("Keystone is not related"),
            ),
            # Scenario 2: With credentials relation but no data
            (
                {},  # Default config
                [("credentials", "keystone")],
                {
                    "keystone_data": {},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.WaitingStatus("Waiting for credentials from keystone"),
            ),
            # Scenario 3: No cos-agent relation
            (
                {},  # Default config
                [("credentials", "keystone")],  # Only credentials relation
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus("Grafana Agent is not related"),
            ),
            # Scenario 4: With upstream snap present
            (
                {},  # Default config
                [
                    ("credentials", "keystone"),
                    ("cos-agent", "openstack-exporter"),
                ],  # Both relations
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": True,  # Upstream snap present
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus(
                    "golang-openstack-exporter detected. Please see: "
                    "https://charmhub.io/openstack-exporter#known-issues"
                ),
            ),
            # Scenario 5: Non-default snap channel with resource
            (
                {"snap_channel": "latest/edge"},
                [("credentials", "keystone"), ("cos-agent", "opentelemetry-collector")],
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus(
                    "Snap resource provided, so snap_channel is unused. "
                    "Please unset it: juju config openstack-exporter --reset snap_channel"
                ),
            ),
            # Scenario 6: Snap not installed
            (
                {},  # Default config
                [("credentials", "keystone"), ("cos-agent", "opentelemetry-collector")],
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": False,
                    "snap_active": False,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus(
                    f"{SNAP_NAME} snap is not installed. "
                    "Please wait for installation to complete, "
                    "or manually reinstall the snap if the issue persists."
                ),
            ),
            # Scenario 7: Snap installed but service not active
            (
                {},  # Default config
                [("credentials", "keystone"), ("cos-agent", "opentelemetry-collector")],
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": False,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus(
                    f"{SNAP_NAME} snap service is not active. "
                    "Please wait for configuration to complete, "
                    "or manually start the service the issue persists."
                ),
            ),
            # Scenario 8: Everything ok
            (
                {"snap_channel": "latest/stable"},  # Default snap channel
                [("credentials", "keystone"), ("cos-agent", "opentelemetry-collector")],
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.ActiveStatus(),
            ),
        ],
    )
    def test_on_collect_unit_status(self, config, relations, test_values, expected_status, mocker):
        """Test the _on_collect_unit_status method with different scenarios."""
        # Setup mock event and services
        mock_event = mocker.MagicMock()
        mock_snap_service = mocker.MagicMock()
        mock_upstream_service = mocker.MagicMock()

        # Configure mocks and services
        mocker.patch("charm.snap_install_or_refresh")
        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_upstream_service if snap == UPSTREAM_SNAP else mock_snap_service
        )
        mock_get_keystone_data = mocker.patch(
            "charm.OpenstackExporterOperatorCharm._get_keystone_data"
        )
        mock_get_keystone_data.return_value = test_values["keystone_data"]
        mock_get_resource = mocker.patch("charm.OpenstackExporterOperatorCharm.get_resource")
        mock_get_resource.return_value = test_values["resource_path"]
        mock_upstream_service.present = test_values["upstream_present"]
        mock_snap_service.present = test_values["snap_present"]
        mock_snap_service.is_active.return_value = test_values["snap_active"]

        self.harness.begin()

        self.harness.update_config(config)

        for relation_name, endpoint in relations:
            self.harness.add_relation(relation_name, endpoint)

        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_any_call(expected_status)

    @pytest.mark.parametrize(
        "protocol, expected_verify",
        [
            ("https", True),  # HTTPS with verify
            ("http", False),  # HTTP without verify
        ],
    )
    def test_write_cloud_config(self, protocol, expected_verify, mocker):
        """Test that cloud config works correctly."""
        # Setup mocks
        mock_config = mocker.patch("charm.OS_CLIENT_CONFIG")
        mock_config_parent = mocker.MagicMock()
        mock_config.parent = mock_config_parent
        mocker.patch("charm.snap_install_or_refresh")

        mock_cacert = mocker.patch("charm.OS_CLIENT_CONFIG_CACERT")
        mock_yaml_dump = mocker.patch("charm.yaml.dump")
        mock_yaml_dump.return_value = "yaml content"

        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_upstream = mocker.MagicMock()
        mock_upstream.present = True
        mock_get_installed_snap_service.return_value = mock_upstream

        self.harness.begin()

        # Prepare test data
        test_data = {
            "service_protocol": protocol,
            "service_hostname": "keystone.test",
            "service_port": "5000",
            "service_username": "testuser",
            "service_password": "testpass",
            "service_project_name": "testproject",
            "service_project_domain_name": "testdomain",
            "service_user_domain_name": "testuserdomain",
            "service_region": "testregion",
        }
        self.harness.update_config({"ssl_ca": "test-ca-certificate"})
        expected_auth_url = f"{protocol}://keystone.test:5000/v3"

        self.harness.charm._write_cloud_config(test_data)

        # Common assertions
        mock_config_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_cacert.write_text.assert_called_once_with("test-ca-certificate")

        # Check the YAML content matches expectations
        expected_contents = {
            "clouds": {
                CLOUD_NAME: {
                    "region_name": "testregion",
                    "identity_api_version": "3",
                    "identity_interface": "internal",
                    "auth": {
                        "username": "testuser",
                        "password": "testpass",
                        "project_name": "testproject",
                        "project_domain_name": "testdomain",
                        "user_domain_name": "testuserdomain",
                        "auth_url": expected_auth_url,
                    },
                    "verify": expected_verify,
                    "cacert": str(mock_cacert),
                }
            }
        }
        mock_config.write_text.assert_called_with("yaml content")
        mock_yaml_dump.assert_called_with(expected_contents)

    def test_get_keystone_data_no_relations(self, mocker):
        """Test _get_keystone_data returns empty dict when no relations exist."""
        self._setup_common_mocks(mocker)
        self.harness.begin()
        result = self.harness.charm._get_keystone_data()
        assert result == {}

    def test_get_keystone_data_relation_no_units(self, mocker):
        """Test that _get_keystone_data returns empty.

        dict when relation exists but has no units.
        """
        self._setup_common_mocks(mocker)
        self.harness.begin()
        result = self.harness.charm._get_keystone_data()
        assert result == {}

    def test_get_keystone_data_relation_incomplete_data(self, mocker):
        """Test that _get_keystone_data returns empty dict when unit has incomplete data."""
        self._setup_common_mocks(mocker)
        self.harness.begin()
        rel_id = self.harness.add_relation("credentials", "keystone")
        self.harness.add_relation_unit(rel_id, "keystone/0")
        incomplete_data = {
            "service_protocol": "https",
            "service_hostname": "keystone.test",
            # Missing other fields
        }
        self.harness.update_relation_data(rel_id, "keystone/0", incomplete_data)

        result = self.harness.charm._get_keystone_data()
        assert result == {}

    def test_get_keystone_data_relation_complete_data(self, mocker):
        """Test that _get_keystone_data returns data when unit has complete data."""
        self._setup_common_mocks(mocker)
        self.harness.begin()
        rel_id = self.harness.add_relation("credentials", "keystone")
        self.harness.add_relation_unit(rel_id, "keystone/0")
        complete_data = self._get_complete_keystone_data()
        self.harness.update_relation_data(rel_id, "keystone/0", complete_data)

        result = self.harness.charm._get_keystone_data()
        assert result == complete_data

    def test_get_keystone_data_multiple_units_mixed_data(self, mocker):
        """Test that _get_keystone_data returns first complete .

        data when multiple units have mixed data quality.
        """
        self._setup_common_mocks(mocker)
        self.harness.begin()

        rel_id = self.harness.add_relation("credentials", "keystone")

        # Add first unit with complete data
        self.harness.add_relation_unit(rel_id, "keystone/0")
        complete_data = self._get_complete_keystone_data()
        self.harness.update_relation_data(rel_id, "keystone/0", complete_data)

        # Add second unit with incomplete data
        self.harness.add_relation_unit(rel_id, "keystone/1")
        incomplete_data = {
            "service_protocol": "http",
            # Missing other fields
        }
        self.harness.update_relation_data(rel_id, "keystone/1", incomplete_data)

        result = self.harness.charm._get_keystone_data()
        assert result == complete_data

    def test_get_keystone_data_multiple_relations(self, mocker):
        """Test that _get_keystone_data prioritises first relation with valid data."""
        self._setup_common_mocks(mocker)
        self.harness.begin()

        # First relation with complete data
        first_rel_id = self.harness.add_relation("credentials", "keystone")
        self.harness.add_relation_unit(first_rel_id, "keystone/0")
        first_complete_data = self._get_complete_keystone_data()
        self.harness.update_relation_data(first_rel_id, "keystone/0", first_complete_data)

        # Second relation with different but also complete data
        second_rel_id = self.harness.add_relation("credentials", "second-keystone")
        self.harness.add_relation_unit(second_rel_id, "second-keystone/0")
        second_complete_data = self._get_complete_keystone_data(
            protocol="http", hostname="second-keystone.test", username="seconduser"
        )
        self.harness.update_relation_data(second_rel_id, "second-keystone/0", second_complete_data)

        result = self.harness.charm._get_keystone_data()
        assert result == first_complete_data, "Should prefer data from first relation"

    def test_get_keystone_data_after_relation_removal(self, mocker):
        """Test that _get_keystone_data uses second relation after first is removed."""
        # Setup
        self._setup_common_mocks(mocker)
        self.harness.begin()

        # First relation with complete data
        first_rel_id = self.harness.add_relation("credentials", "keystone")
        self.harness.add_relation_unit(first_rel_id, "keystone/0")
        first_complete_data = self._get_complete_keystone_data()
        self.harness.update_relation_data(first_rel_id, "keystone/0", first_complete_data)

        # Second relation with different but also complete data
        second_rel_id = self.harness.add_relation("credentials", "second-keystone")
        self.harness.add_relation_unit(second_rel_id, "second-keystone/0")
        second_complete_data = self._get_complete_keystone_data(
            protocol="http", hostname="second-keystone.test", username="seconduser"
        )
        self.harness.update_relation_data(second_rel_id, "second-keystone/0", second_complete_data)

        # Remove first relation
        self.harness.remove_relation(first_rel_id)

        result = self.harness.charm._get_keystone_data()
        assert result == second_complete_data

    def _setup_common_mocks(self, mocker):
        """Set up common mocks for _get_keystone_data tests."""
        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_upstream = mocker.MagicMock()
        mock_upstream.present = True
        mock_get_installed_snap_service.return_value = mock_upstream
        mocker.patch("charm.snap_install_or_refresh")

    def _get_complete_keystone_data(self, **overrides):
        """Get complete keystone data with optional overrides."""
        data = {
            "service_protocol": "https",
            "service_hostname": "keystone.test",
            "service_port": "5000",
            "service_username": "testuser",
            "service_password": "testpass",
            "service_project_name": "testproject",
            "service_project_domain_name": "testdomain",
            "service_user_domain_name": "testuserdomain",
            "service_region": "testregion",
        }
        # Apply any overrides
        data.update(overrides)
        return data

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.OpenstackExporterOperatorCharm._get_keystone_data", return_value={})
    @mock.patch("charm.snap_install_or_refresh")
    def test_snap_service_with_no_keystone_data(self, _, __, mock_get_installed_snap_service):
        """Test snap service behavior when Keystone data is not available."""
        # Setup mocks
        mock_snap_service = mock.MagicMock()
        mock_upstream_service = mock.MagicMock()
        mock_upstream_service.present = False
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_upstream_service if snap == UPSTREAM_SNAP else mock_snap_service
        )
        self.harness.begin()
        self.harness.add_relation("cos-agent", "opentelemetry-collector")

        self.harness.charm._configure(mock.MagicMock())
        mock_snap_service.stop.assert_called_once()

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch(
        "charm.OpenstackExporterOperatorCharm._get_keystone_data", return_value={"some": "data"}
    )
    @mock.patch("charm.snap_install_or_refresh")
    def test_snap_service_with_keystone_data(self, _, __, mock_get_installed_snap_service):
        """Test snap service behavior when Keystone data is available."""
        # Setup mocks
        mock_snap_service = mock.MagicMock()
        mock_upstream_service = mock.MagicMock()
        mock_upstream_service.present = False
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_upstream_service if snap == UPSTREAM_SNAP else mock_snap_service
        )
        self.harness.begin()
        self.harness.add_relation("cos-agent", "opentelemetry-collector")

        # Mock _write_cloud_config to avoid real file operations
        with mock.patch.object(self.harness.charm, "_write_cloud_config"):
            self.harness.charm._configure(mock.MagicMock())

            # With data present, stop should not be called
            mock_snap_service.stop.assert_not_called()

    def test_get_resource_returns_path_for_non_empty_file(self, mocker):
        """Test get_resource returns the resource path when the file exists and is not empty."""
        self.harness.begin()
        mock_getsize = mocker.patch("charm.os.path.getsize")
        mock_getsize.return_value = 1024  # Non-empty file

        mock_fetch = mocker.patch.object(self.harness.charm.model.resources, "fetch")
        mock_fetch.return_value = Path("/path/to/snap/resource")

        result = self.harness.charm.get_resource()
        assert result == Path("/path/to/snap/resource")
        mock_fetch.assert_called_once()

    def test_get_resource_returns_none_for_empty_file(self, mocker):
        """Test get_resource returns None when the file exists but is empty."""
        self.harness.begin()
        mock_getsize = mocker.patch("charm.os.path.getsize")
        mock_getsize.return_value = 0  # Empty file

        mock_fetch = mocker.patch.object(self.harness.charm.model.resources, "fetch")
        mock_fetch.return_value = Path("/path/to/snap/resource")

        result = self.harness.charm.get_resource()
        assert result is None
        mock_fetch.assert_called_once()

    def test_get_resource_returns_none_for_negative_size_file(self, mocker):
        """Test get_resource returns None when the file size is negative."""
        self.harness.begin()
        mock_getsize = mocker.patch("charm.os.path.getsize")
        mock_getsize.return_value = -1  # Negative size

        mock_fetch = mocker.patch.object(self.harness.charm.model.resources, "fetch")
        mock_fetch.return_value = Path("/path/to/snap/resource")

        result = self.harness.charm.get_resource()
        assert result is None
        mock_fetch.assert_called_once()

    def test_get_resource_returns_none_when_model_error_occurs(self):
        """Test get_resource returns None when a ModelError occurs during fetch."""
        # Setup
        self.harness.begin()
        mock.patch.object(
            self.harness.charm.model.resources,
            "fetch",
            side_effect=ops.model.ModelError("cannot fetch charm resource"),
        )

        result = self.harness.charm.get_resource()
        assert result is None

    @mock.patch("charm.OpenstackExporterOperatorCharm.install")
    def test_on_upgrade(self, mock_install):
        """Test the charm is installed in upgrade event."""
        self.harness.begin()
        upgrade_event = mock.MagicMock()
        self.harness.charm._on_upgrade(upgrade_event)
        mock_install.assert_called_once()

    @pytest.mark.parametrize(
        "config_option, config_value",
        [
            ("port", 9180),
            ("port", 8080),
            ("port", 80),
            ("cache_ttl", "300s"),
            ("cache_ttl", "300m"),
            ("cache_ttl", "300h"),
            ("cache_ttl", "+1s"),
            ("cache_ttl", ".1m"),
            ("cache_ttl", "5.s"),
            ("cache_ttl", "5\u00b5s"),
            ("cache_ttl", "5\u03bcs"),
            ("cache_ttl", "30s"),
            ("cache_ttl", "3h30m"),
            ("cache_ttl", "10.5s4m"),
            ("cache_ttl", "2m3.4s"),
            ("cache_ttl", "1h2m3s4ms5us6ns"),
            ("cache_ttl", "39h9m14s"),
        ],
    )
    def test_config_change_with_valid_config(self, config_option, config_value, mocker):
        """Test config change with valid config."""
        mocked_upstream_service = mock.MagicMock()
        mocked_upstream_service.present = True
        mock_get_installed_snap_service = mocker.patch("charm.get_installed_snap_service")
        mock_get_installed_snap_service.return_value = mocked_upstream_service
        mock_install = mocker.patch("charm.OpenstackExporterOperatorCharm.install")
        mock_event = mock.MagicMock()

        self.harness.begin()
        self.harness.update_config({config_option: config_value})

        # If valid config, install method can be called from _configure
        mock_install.assert_called_once()

        # Status should be set to Active
        self.harness.charm._on_collect_unit_status(mock_event)
        mock_event.add_status.assert_called_with(ops.ActiveStatus())

    @pytest.mark.parametrize(
        "config_option, config_value",
        [
            ("port", 0),
            ("port", -1),
            ("port", 65536),
            ("cache_ttl", ""),
            ("cache_ttl", "3"),
            ("cache_ttl", "-"),
            ("cache_ttl", "+"),
            ("cache_ttl", "s"),
            ("cache_ttl", "."),
            ("cache_ttl", "0"),
            ("cache_ttl", "+0s"),
            ("cache_ttl", "-."),
            ("cache_ttl", "-3h30m"),
            ("cache_ttl", "0s0m"),
            ("cache_ttl", ".s"),
            ("cache_ttl", "+.s"),
            ("cache_ttl", "1d"),
        ],
    )
    def test_config_change_with_invalid_config(self, config_option, config_value, mocker):
        """Test config change and status being set with invalid config."""
        if config_option == "port":
            validate_function = "charm.validate_port"
            error_msg = f"Port must be between 1 and 65535, got {config_value}"
        elif config_option == "cache_ttl":
            validate_function = "charm.validate_cache_ttl"
            error_msg = (
                f"cache_ttl must be non-negative, non-zero, "
                f"and in correct pattern, got {config_value}"
            )

        mock_event = mock.MagicMock()
        mock_logger = mocker.patch("charm.logger.error")
        mocker.patch(validate_function, return_value=error_msg)
        mocker.patch("charm.get_installed_snap_service")

        self.harness.begin()
        self.harness.update_config({config_option: config_value})
        self.harness.charm._on_collect_unit_status(mock_event)

        mock_logger.assert_called_once_with(error_msg)
        mock_event.add_status.assert_any_call(ops.BlockedStatus(error_msg))
