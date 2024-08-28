#!/usr/bin/env python3
# Copyright 2024 Canonical
#
# See LICENSE file for licensing details.

import json
import logging
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from zaza import model

from charm import CLOUD_NAME, OS_CLIENT_CONFIG, SNAP_NAME, UPSTREAM_SNAP

logger = logging.getLogger(__name__)

APP_NAME = "openstack-exporter"
STATUS_TIMEOUT = 120  # must be larger than the time defined in zaza-yaml

VERSION_COLUMN = 1
REVISION_COLUMN = 2
CHANNEL_COLUMN = 3


class OpenstackExporterBaseTest(unittest.TestCase):
    """Base Class for charm integration tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for the test class."""
        cls.leader_unit = model.get_lead_unit(APP_NAME)
        cls.leader_unit_entity_id = cls.leader_unit.entity_id


class OpenstackExporterConfigTest(OpenstackExporterBaseTest):
    """Test config changes for openstack exporter."""

    def test_clouds_yaml(self):
        """Test clouds.yaml exists and not empty."""
        # Make sure the clouds yaml is set to the place we expect
        command = f"sudo snap get {SNAP_NAME} os-client-config"
        results = model.run_on_leader(APP_NAME, command)
        clouds_yaml_path = results.get("Stdout", "").strip()
        self.assertEqual(int(results.get("Code", "-1")), 0)
        self.assertEqual(clouds_yaml_path, OS_CLIENT_CONFIG)

        # Make sure the clouds yaml is not empty and it's a valid yaml
        command = f"cat $(sudo snap get {SNAP_NAME} os-client-config)"
        results = model.run_on_leader(APP_NAME, command)
        clouds_yaml = results.get("Stdout", "").strip()
        data = yaml.safe_load(clouds_yaml)
        openstack_auths = data["clouds"][CLOUD_NAME]
        self.assertEqual(int(results.get("Code", "-1")), 0)
        self.assertNotEqual(clouds_yaml, "")
        self.assertNotEqual(openstack_auths, {})

    def test_configure_port(self):
        """Test changing the listening port."""
        # Change config: port
        key = "port"
        new_value = "10000"  # different port (will be reset shortly)
        model.set_application_config(APP_NAME, {key: new_value})
        model.block_until_all_units_idle()

        # Get snap config: web.listen-address and verify it's applied
        command = f"sudo snap get {SNAP_NAME} web.listen-address"
        results = model.run_on_leader(APP_NAME, command)
        self.assertEqual(results.get("Stdout", "").strip(), f":{new_value}")

        # Verify that we can curl at new listening address
        command = f"curl -q localhost:{new_value}/metrics"
        results = model.run_on_leader(APP_NAME, command)
        self.assertEqual(int(results.get("Code", "-1")), 0)

        # Reset config: port
        model.reset_application_config(APP_NAME, [key])
        model.block_until_all_units_idle()

        # Verify that we can curl at old listening address
        command = "curl -q localhost:9180/metric"  # curl at default port
        results = model.run_on_leader(APP_NAME, command)
        self.assertEqual(int(results.get("Code", "-1")), 0)

    def test_configure_snap_channel(self):
        """Test changing the snap channel."""
        snap_info_before = get_snap_info(SNAP_NAME)
        self.assertEqual(snap_info_before["channel"], "latest/stable")

        # Change snap channel
        new_channel = "latest/edge"
        model.set_application_config(APP_NAME, {"snap_channel": new_channel})
        model.block_until_all_units_idle()

        snap_info_after = get_snap_info(SNAP_NAME)
        self.assertEqual(snap_info_after["channel"], new_channel)

        model.reset_application_config(APP_NAME, ["snap_channel"])

    def test_snap_as_resource(self):
        """Test using the snap as resource.

        Snap when used as resource will have 'x' in the revision. E.g: x1 and won't be affected
        by the user changing the snap channel charm configuration.
        """
        # snap from snapstore won't have "x" in the revision
        snap_info_before = get_snap_info(SNAP_NAME)
        self.assertNotIn("x", snap_info_before["revision"])

        # juju cannot access resources at /tmp, so we create a tmp folder at the current directory
        with tempfile.TemporaryDirectory(dir="./") as tmpdir:
            tmp_path = Path(tmpdir)
            download_cmd = f"snap download --target-directory={tmpdir} {SNAP_NAME}"
            subprocess.run(download_cmd.split(), check=False)

            resource_file = [file for file in tmp_path.iterdir() if ".snap" in file.name][0]
            model.attach_resource(APP_NAME, "openstack-exporter", str(resource_file))
            model.block_until_all_units_idle()

            # local installed snaps will have "x" in the revision
            snap_info_resource = get_snap_info(SNAP_NAME)
            self.assertIn("x", snap_info_resource["revision"])

            # changing channel won't affect the snap installed as resource
            # Change snap channel
            new_channel = "latest/beta"
            model.set_application_config(APP_NAME, {"snap_channel": new_channel})
            model.block_until_all_units_idle()
            channel_after = get_snap_info(SNAP_NAME)["channel"]
            self.assertNotEqual(channel_after, new_channel)
            self.assertEqual(channel_after, snap_info_resource["channel"])

            # passing an empty file will re-install the snap from the store and use the charm
            # channel config
            temp_file_path = Path(tmpdir) / f"{SNAP_NAME}.snap"
            temp_file_path.touch()
            model.attach_resource(APP_NAME, "openstack-exporter", str(temp_file_path))
            model.block_until_all_units_idle()

            snap_info_after = get_snap_info(SNAP_NAME)
            self.assertNotIn("x", snap_info_after["revision"])
            self.assertEqual(snap_info_after["channel"], new_channel)

            model.reset_application_config(APP_NAME, ["snap_channel"])

    def test_configure_ssl_ca(self):
        """Test changing the ssl_ca."""
        # Change config: ssl_ca
        key = "ssl_ca"
        new_value = "random_ca"  # bad ssl_ca (will be reset shortly)
        old_value = model.get_application_config(APP_NAME).get(key)
        model.set_application_config(APP_NAME, {key: new_value})
        # Change cache to false to not get previous scrape results
        model.set_application_config(APP_NAME, {"cache": "false"})
        model.block_until_all_units_idle()

        # Get snap config: os-client-config and verify it's applied
        command = f"cat $(sudo snap get {SNAP_NAME} os-client-config)"
        results = model.run_on_leader(APP_NAME, command)
        clouds_yaml = results.get("Stdout", "").strip()
        data = yaml.safe_load(clouds_yaml)
        cacert = data["clouds"][CLOUD_NAME]["cacert"]
        self.assertEqual(cacert, f"{new_value}")

        # Verify the exporter crashes because of wrong ssl_ca
        command = "curl -q localhost:9180/metrics"
        results = model.run_on_leader(APP_NAME, command)
        self.assertNotEqual(int(results.get("Code", "-1")), 0)

        # Reset config: ssl_ca
        model.set_application_config(APP_NAME, {key: old_value})
        model.block_until_all_units_idle()

        # Verify the exporter is active again because of good ssl_ca
        command = "curl -q localhost:9180/metrics"
        results = model.run_on_leader(APP_NAME, command)
        self.assertEqual(int(results.get("Code", "-1")), 0)

        # Enable cache again
        model.set_application_config(APP_NAME, {"cache": "true"})
        model.block_until_all_units_idle()


class OpenstackExporterStatusTest(OpenstackExporterBaseTest):
    """Test status changes for openstack exporter."""

    def test_keystone_relation_changed(self):
        """Test keystone relation changed will reach expected status.

        Test the expected charm status when removing keystone relation and
        adding keystone relation back.
        """
        # Remove keystone relation
        model.remove_relation(APP_NAME, "credentials", "keystone:identity-admin")
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "blocked", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(self.leader_unit.workload_status_message, "Keystone is not related")

        # Be patient: wait until the relation is completely removed
        model.block_until_all_units_idle()

        # Add back keystone relation
        model.add_relation(APP_NAME, "credentials", "keystone:identity-admin")
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "active", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(self.leader_unit.workload_status_message, "")

    def test_grafana_agent_relation_changed(self):
        """Test grafana-agent relation changed will reach expected status.

        Test the expected charm status when removing grafana-agent relation and
        adding grafana-agent relation back.
        """
        # Remove grafana-agent relation
        model.remove_relation(APP_NAME, "cos-agent", "grafana-agent:cos-agent")
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "blocked", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(self.leader_unit.workload_status_message, "Grafana Agent is not related")

        # Be patient: wait until the relation is completely removed
        model.block_until_all_units_idle()

        # Add back grafan-agent relation
        model.add_relation(APP_NAME, "cos-agent", "grafana-agent:cos-agent")
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "active", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(self.leader_unit.workload_status_message, "")

    def test_openstack_exporter_snap_down(self):
        """Test openstack exporter snap down will reach expected status.

        Manually stop (to simulate exporter snap down) the exporter snap and
        test the charm will go to expected status.
        """
        # Stop the exporter snap
        command = f"sudo snap stop {SNAP_NAME}.service"
        model.run_on_leader(APP_NAME, command)
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "blocked", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(
            self.leader_unit.workload_status_message,
            "snap service is not running, please check snap service",
        )

        # Start the exporter snap
        command = f"sudo snap start {SNAP_NAME}.service"
        model.run_on_leader(APP_NAME, command)
        model.block_until_unit_wl_status(
            self.leader_unit_entity_id, "active", timeout=STATUS_TIMEOUT
        )
        self.assertEqual(self.leader_unit.workload_status_message, "")

    def test_upstream_exporter_as_resource(self):
        """Test using the upstream golang as resource will block the unit."""
        # juju cannot access resources at /tmp, so we create a tmp folder at the current directory
        with tempfile.TemporaryDirectory(dir="./") as tmpdir:
            tmp_path = Path(tmpdir)
            download_cmd = (
                f"wget -q -P {tmpdir} https://github.com/canonical/openstack-exporter-operator/"
                "releases/download/rev2/golang-openstack-exporter_amd64.snap"
            )
            subprocess.run(download_cmd.split(), check=False)

            resource_file = tmp_path / "golang-openstack-exporter_amd64.snap"
            model.attach_resource(APP_NAME, "openstack-exporter", str(resource_file))
            model.block_until_unit_wl_status(
                self.leader_unit_entity_id, "blocked", timeout=STATUS_TIMEOUT
            )
            snaps_installed = [snap["name"] for snap in get_snaps_installed()]
            self.assertIn(UPSTREAM_SNAP, snaps_installed)
            expected_msg = (
                f"{UPSTREAM_SNAP} should not be used anymore. "
                "Please add an empty file as resource. See more information in the docs: "
                "https://charmhub.io/openstack-exporter#known-issues"
            )
            self.assertEqual(self.leader_unit.workload_status_message, expected_msg)

            # passing an empty file will unblock the unit
            temp_file_path = Path(tmpdir) / f"{SNAP_NAME}.snap"
            temp_file_path.touch()
            model.attach_resource(APP_NAME, "openstack-exporter", str(temp_file_path))
            model.block_until_unit_wl_status(
                self.leader_unit_entity_id, "active", timeout=STATUS_TIMEOUT
            )


def get_snaps_installed() -> dict[str, str]:
    """Get the snaps installed in the leader unit."""
    cmd = "curl -sS --unix-socket /run/snapd.socket http://localhost/v2/snaps"
    return json.loads(model.run_on_leader(APP_NAME, cmd).get("Stdout", ""))["result"]


def get_snap_info(snap_name: str) -> list[dict[str, str]]:
    """Get the snap information."""
    snaps = get_snaps_installed()
    return [snap for snap in snaps if snap["name"] == snap_name][0]
