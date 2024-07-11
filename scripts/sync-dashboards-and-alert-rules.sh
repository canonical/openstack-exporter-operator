#!/bin/sh
# Sync the dashboards  and alert rules from https://opendev.org/openstack/sunbeam-charms/src/branch/main/charms/openstack-exporter-k8s/src

git remote add -f sunbeam https://opendev.org/openstack/sunbeam-charms.git
git checkout -b staging-branch sunbeam/main
git subtree split -P charms/openstack-exporter-k8s/src -b k8s-exporter
git checkout k8s-exporter
git rm -r $(ls | grep -vE '^grafana_dashboards$|^prometheus_alert_rules$')
git commit -m "Remove unwanted files"
git checkout main
git subtree add -P src/sunbeam k8s-exporter --squash