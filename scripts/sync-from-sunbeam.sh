#!/bin/sh

# the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# the temp directory used, within $DIR
# omit the -p parameter to create a temporal directory in the default location
WORK_DIR=`mktemp -d -p "$DIR"`

# check if tmp dir was created
if [[ ! "$WORK_DIR" || ! -d "$WORK_DIR" ]]; then
  echo "Could not create temp dir"
  exit 1
fi

# deletes the temp directory
function cleanup {      
  rm -rf "$WORK_DIR"
  echo "Deleted temp working directory $WORK_DIR"
}

# register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

# implementation of script starts here
# Clone the repository with sparse checkout
git clone --sparse --single-branch --depth=1 https://opendev.org/openstack/sunbeam-charms.git "$WORK_DIR/sunbeam-charms"
cd "$WORK_DIR/sunbeam-charms"

# Set sparse checkout paths
git sparse-checkout set charms/openstack-exporter-k8s/src/grafana_dashboards charms/openstack-exporter-k8s/src/prometheus_alert_rules

# Copy the necessary files to the src directory
cp -r charms/openstack-exporter-k8s/src/grafana_dashboards "$DIR/../src/"
cp -r charms/openstack-exporter-k8s/src/prometheus_alert_rules "$DIR/../src/"
