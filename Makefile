DEFAULT_GOAL=help

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make                            - show help text"
	@echo " make update-charm-libs          - update charm's libraries"
	@echo " make check-dashboard-updates    - check if there's a new dashboard from the upstream"
	@echo ""


update-charm-libs:
	./scripts/update-charm-libs.sh

check-dashboard-updates:
	./scripts/check-dashboard-updates.sh

.PHONY: help update-charm-libs check-dashboard-updates
