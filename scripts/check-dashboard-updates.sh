#!/bin/sh

# Checkout the dashboard from the upstream repository and see if there is a new
# version available or not.

ROOT_DIR="$(dirname $0)/.."
LOCAL_PATH="$ROOT_DIR/src"
UPSTREAM_PATH="https://opendev.org/openstack/sunbeam-charms/raw/branch/main/charms/openstack-exporter-k8s/src"

# Get the remote and local file
LOCAL_FILE="$LOCAL_PATH/grafana_dashboards/openstack-exporter.json"
REMOTE_FILE="$(mktemp)"
wget -O $REMOTE_FILE $UPSTREAM_PATH/grafana_dashboards/openstack-exporter.json

# Compare them and get the exit status
diff $LOCAL_FILE $REMOTE_FILE
DIFF_STATUS=$?

# Remove the temporary remote file
rm -f $REMOTE_FILE

# Exit 1 if there's any difference
if [ $DIFF_STATUS -ne 0 ]; then
  echo "Differences detected in the file ./src/grafana_dashboards/openstack-exporter.json"
  exit 1
fi
