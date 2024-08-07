#!/usr/bin/env python3
# Copyright 2024 Canonical
#
# See LICENSE file for licensing details.

import logging
import unittest

import yaml
from charm import CLOUD_NAME, OS_CLIENT_CONFIG
from zaza import model

logger = logging.getLogger(__name__)

APP_NAME = "openstack-exporter"
SNAP_NAME = "golang-openstack-exporter"
STATUS_TIMEOUT = 120  # must be larger than the time defined in zaza-yaml


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
