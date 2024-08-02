#!/bin/sh

# Update charm libraries that are managed with charmcraft.

ROOT_DIR="$(dirname $0)/.."

cd $ROOT_DIR

charmcraft fetch-lib charms.operator_libs_linux.v2.snap
charmcraft fetch-lib charms.grafana_agent.v0.cos_agent
