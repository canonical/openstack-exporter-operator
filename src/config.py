"""Setting for the charm."""
# Copyright 2024 Canonical Ltd.
#
# See LICENSE file for licensing details.

from pathlib import Path

from ops import model
from pydantic import BaseModel, Field, field_validator

# Miscellaneous constants
USER_HOME = str(Path().home())

# Snap global constants
RESOURCE_NAME = "openstack-exporter"
SNAP_NAME = "golang-openstack-exporter"
SNAP_SERVICE_NAME = "service"

# Snap config options global constants
WEB_TELEMETRY_PATH = "/metrics"
CLOUD_NAME = "openstack"
OS_CLIENT_CONFIG = Path(USER_HOME) / "clouds.yaml"


class SnapConfig(BaseModel):
    """A snap config option data model."""

    cloud: str = Field(default="", alias="cloud")
    log: dict[str, str] = Field(default_factory=lambda: {}, alias="log")
    web: dict[str, str] = Field(default_factory=lambda: {}, alias="web")
    os_client_config: str = Field(default="", alias="os-client-config")

    @field_validator("log")
    @classmethod
    def validate_log(cls, options: dict[str, str]) -> dict[str, str]:
        """Validate the log's choices."""
        available_level_choices = {"debug", "info", "warn", "error"}
        log_level = options.get("level", "").lower()
        if log_level and log_level not in available_level_choices:
            raise ValueError(f"'log-level' must be in {available_level_choices}")

        canonical_options = {}
        if log_level:
            canonical_options["level"] = log_level
        return canonical_options

    @field_validator("web")
    @classmethod
    def validate_web(cls, options: dict[str, str]) -> dict[str, str]:
        """Validate the web's choices."""
        listen_address = options.get("listen-address", "")
        if listen_address and not listen_address.startswith(":"):
            listen_address = f":{listen_address}"
        try:
            _ = int(listen_address[1:])
        except ValueError as e:
            raise ValueError(
                "'port' must be in the format of colon + integer (e.g. ':8080')."
            ) from e

        canonical_options = {}
        if listen_address:
            canonical_options["listen-address"] = listen_address
        return canonical_options

    @classmethod
    def from_charm_config(cls, config: model.ConfigData) -> "SnapConfig":
        """Construct an `SnapConfig` from charm config."""
        return cls(
            cloud=CLOUD_NAME,
            log={"level": config["log-level"]},
            web={"listen-address": str(config["port"])},
            os_client_config=OS_CLIENT_CONFIG,
        )
