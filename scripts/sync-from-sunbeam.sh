#!/bin/sh

# Clone the repository with sparse checkout
git clone --sparse --single-branch --depth=1 https://opendev.org/openstack/sunbeam-charms.git
cd sunbeam-charms

# Set sparse checkout paths
git sparse-checkout set charms/openstack-exporter-k8s/src/grafana_dashboards charms/openstack-exporter-k8s/src/prometheus_alert_rules

# Copy the necessary files to the src directory
cp -r charms/openstack-exporter-k8s/src/grafana_dashboards ../src/
cp -r charms/openstack-exporter-k8s/src/prometheus_alert_rules ../src/

# Clean up
cd ..
rm -rf sunbeam-charms
