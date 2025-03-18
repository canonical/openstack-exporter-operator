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
                [("credentials", "keystone"), ("cos-agent", "grafana-agent")],
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
                [("credentials", "keystone"), ("cos-agent", "grafana-agent")],
                {
                    "keystone_data": {"random": "data"},
                    "upstream_present": False,
                    "snap_present": True,
                    "snap_active": True,
                    "resource_path": "/path/to/snap/resource",
                },
                ops.BlockedStatus(
                    "Snap resource provided, so snap_channel is unused. "
                    "Please unset it: juju config {app_name} --reset snap_channel"
                ),
            ),
            # Scenario 6: Snap not installed
            (
                {},  # Default config
                [("credentials", "keystone"), ("cos-agent", "grafana-agent")],
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
                [("credentials", "keystone"), ("cos-agent", "grafana-agent")],
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
                [("credentials", "keystone"), ("cos-agent", "grafana-agent")],
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

        # In cases app_name in expected message
        if (
            isinstance(expected_status, ops.BlockedStatus)
            and "{app_name}" in expected_status.message
        ):
            expected_status = ops.BlockedStatus(
                expected_status.message.format(app_name=self.harness.charm.app.name)
            )

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

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.snap_install_or_refresh")
    def test_get_keystone_data(self, _, mock_get_installed_snap_service):
        """Test retrieving Keystone data from relations in different scenarios."""
        # Setup mocks
        mock_upstream = mock.MagicMock()
        mock_upstream.present = True
        mock_get_installed_snap_service.return_value = mock_upstream

        self.harness.begin()

        # Scenario 1: No relations exist
        result = self.harness.charm._get_keystone_data()
        assert result == {}

        # Scenario 2: Relation exists but no units
        rel_id = self.harness.add_relation("credentials", "keystone")
        assert self.harness.charm._get_keystone_data() == {}

        # Scenario 3: Relation exists with a unit with incomplete data
        self.harness.add_relation_unit(rel_id, "keystone/0")
        incomplete_data = {
            "service_protocol": "https",
            "service_hostname": "keystone.test",
            # Missing other fields
        }
        self.harness.update_relation_data(rel_id, "keystone/0", incomplete_data)
        assert self.harness.charm._get_keystone_data() == {}

        # Scenario 4: One unit with complete data
        complete_data = {
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
        self.harness.update_relation_data(rel_id, "keystone/0", complete_data)
        result = self.harness.charm._get_keystone_data()
        assert result == complete_data

        # Scenario 5: Multiple units with and without complete data
        self.harness.add_relation_unit(rel_id, "keystone/1")
        second_unit_data = {
            "service_protocol": "http",
            # Missing other fields
        }
        self.harness.update_relation_data(rel_id, "keystone/1", second_unit_data)

        # Should still return the complete data from the first unit
        result = self.harness.charm._get_keystone_data()
        assert result == complete_data

        # Scenario 6: Multiple relations, with complete data in the second relation
        second_rel_id = self.harness.add_relation("credentials", "another-keystone")
        self.harness.add_relation_unit(second_rel_id, "another-keystone/0")
        second_rel_data = {
            "service_protocol": "http",
            "service_hostname": "another-keystone.test",
            "service_port": "5000",
            "service_username": "anotheruser",
            "service_password": "anotherpass",
            "service_project_name": "anotherproject",
            "service_project_domain_name": "anotherdomain",
            "service_user_domain_name": "anotheruserdomain",
            "service_region": "anotherregion",
        }
        self.harness.update_relation_data(second_rel_id, "another-keystone/0", second_rel_data)

        # Should still return data from the first relation that has valid data
        result = self.harness.charm._get_keystone_data()
        assert result == complete_data

        # Scenario 7: Remove first relation, should now get data from second relation
        self.harness.remove_relation(rel_id)
        result = self.harness.charm._get_keystone_data()
        assert result == second_rel_data

    @mock.patch("charm.get_installed_snap_service")
    @mock.patch("charm.OpenstackExporterOperatorCharm._get_keystone_data")
    @mock.patch("charm.snap_install_or_refresh")
    def test_snap_service_with_keystone_data(
        self, _, mock_get_keystone_data, mock_get_installed_snap_service
    ):
        """Test snap service behaviour with and without keystone data in _configure method."""
        # Setup mock
        mock_snap_service = mock.MagicMock()
        mock_upstream_service = mock.MagicMock()
        mock_upstream_service.present = False
        mock_get_installed_snap_service.side_effect = lambda snap: (
            mock_upstream_service if snap == UPSTREAM_SNAP else mock_snap_service
        )
        self.harness.begin()

        # Add relation to pass the first check in _configure
        self.harness.add_relation("cos-agent", "grafana-agent")

        # Test with no Keystone data
        mock_get_keystone_data.return_value = {}
        self.harness.charm._configure(mock.MagicMock())
        mock_snap_service.stop.assert_called_once()

        # Test with Keystone data present
        mock_get_keystone_data.return_value = {"some": "data"}
        mock_snap_service.reset_mock()
        # Mock _write_cloud_config to avoid real file operations
        with mock.patch.object(self.harness.charm, "_write_cloud_config"):
            self.harness.charm._configure(mock.MagicMock())

            # With data present, stop should not be called
            mock_snap_service.stop.assert_not_called()

    @pytest.mark.parametrize(
        "file_size, model_error, expected_result",
        [
            (1024, False, "/path/to/snap/resource"),  # Scenario 1: Non-empty file
            (0, False, None),  # Scenario 2: Empty file
            (-1, False, None),  # Scenario 3: Empty file with negative size
            (1024, True, None),  # Scenario 4: ModelError when fetching resource
        ],
    )
    def test_get_resource(self, file_size, model_error, expected_result, mocker):
        """Test get_resource method with different scenarios."""
        # Setup mocks
        mock_getsize = mocker.patch("charm.os.path.getsize")
        mock_getsize.return_value = file_size

        self.harness.begin()

        if model_error:
            mock_fetch = mocker.patch.object(
                self.harness.charm.model.resources,
                "fetch",
                side_effect=ops.model.ModelError("cannot fetch charm resource"),
            )
        else:
            mock_fetch = mocker.patch.object(self.harness.charm.model.resources, "fetch")
            mock_fetch.return_value = Path("/path/to/snap/resource")

        result = self.harness.charm.get_resource()

        if result is not None:
            result = result.as_posix()

        assert result == expected_result

        if not model_error:
            mock_fetch.assert_called_once()

    @mock.patch("charm.OpenstackExporterOperatorCharm.install")
    def test_on_upgrade(self, mock_install):
        """Test the charm is installed in upgrade event."""
        self.harness.begin()
        upgrade_event = mock.MagicMock()
        self.harness.charm._on_upgrade(upgrade_event)
        mock_install.assert_called_once()
