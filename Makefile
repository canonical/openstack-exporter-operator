DEFAULT_GOAL=help

PROJECTPATH=$(dir $(realpath $(MAKEFILE_LIST)))
CHARMCRAFT_FILE="charmcraft.yaml"
CHARM_NAME=$(shell cat ${PROJECTPATH}/${CHARMCRAFT_FILE} | grep -E "^name:" | awk '{print $$2}')
CHARM_LOCATION=$(shell find ${PROJECTPATH} -type f -name "${CHARM_NAME}*.charm" | head -n 1)

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make                            - show help text"
	@echo " make update-charm-libs          - update charm's libraries"
	@echo " make clean                      - remove unneeded files"
	@echo " make build                      - build the charm"
	@echo " make integration                - run the tests defined in the integration subdirectory"
	@echo ""


update-charm-libs:
	./scripts/update-charm-libs.sh

clean:
	@echo "Cleaning existing build"
	@rm -f ${PROJECTPATH}/${CHARM_NAME}*.charm
	@charmcraft clean

build: clean
	@echo "Building charm"
	@charmcraft -v pack

integration: build
	CHARM_LOCATION=${CHARM_LOCATION} tox -e integration -- ${FUNC_ARGS}

.PHONY: help update-charm-libs clean build integration
