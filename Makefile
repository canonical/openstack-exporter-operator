DEFAULT_GOAL=help

PROJECTPATH=$(dir $(realpath $(MAKEFILE_LIST)))
CHARMCRAFT_FILE="charmcraft.yaml"
CHARM_NAME=$(shell cat ${PROJECTPATH}/${CHARMCRAFT_FILE} | grep -E "^name:" | awk '{print $$2}')
CHARM_LOCATION=$(shell find ${PROJECTPATH} -type f -name "${CHARM_NAME}*.charm" | head -n 1)
CHARM_SNAP_LOCATION=$(shell find ${PROJECTPATH} -type f -name "charmed-openstack-exporter*.snap" | head -n 1)

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make                            - show help text"
	@echo " make update-charm-libs          - update charm's libraries"
	@echo " make check-dashboard-updates    - check if there's a new dashboard from the upstream"
	@echo " make sync-dashboards            - update the dashboards from upstream"
	@echo " make clean                      - remove unneeded files"
	@echo " make download-snap              - download snap release from github release assets"
	@echo " make build                      - build the charm"
	@echo " make integration                - run the tests defined in the integration subdirectory"
	@echo ""


update-charm-libs:
	./scripts/update-charm-libs.sh

clean:
	@echo "Cleaning existing build"
	@rm -f ${PROJECTPATH}/${CHARM_NAME}*.charm
	@charmcraft clean
	@echo "Remove download snap"
	@rm -f ${PROJECTPATH}/charmed-openstack-exporter*.snap

build: clean
	@echo "Building charm"
	@charmcraft -v pack

integration: build download-snap
	CHARM_LOCATION=${CHARM_LOCATION} CHARM_SNAP_LOCATION=${CHARM_SNAP_LOCATION} tox -e integration -- ${FUNC_ARGS}

.PHONY: help update-charm-libs check-dashboard-updates clean build download-snap integration sync-dashboards
