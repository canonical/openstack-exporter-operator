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
RESOURCE_NAME = "exporter-snap"
SNAP_NAME = "golang-openstack-exporter"
SNAP_SERVICE_NAME = "service"

# Snap config options global constants
WEB_TELEMETRY_PATH = "/metrics"
# Perhaps /etc/openstack/clouds.yaml? But it will need snap auto connection
# for system-files. We should revisit this later.
OS_CLIENT_CONFIG = Path(USER_HOME) / ".openstack" / "clouds.yaml"


class ExporterSnapConfig(BaseModel):
    """Available options on the snap.

    Below shows an example about the snap config option:

    {
        "cloud": "",
        "collect-metric-time": false,
        "disable-cinder-agent-uuid": false,
        "disable-deprecated-metrics": false,
        "disable-metrics": "",
        "disable-service": {
            "baremetal": false,
            "compute": false,
            "container-infra": false,
            "database": false,
            "dns": false,
            "gnocchi": false,
            "identity": false,
            "image": false,
            "load-balancer": false,
            "network": false,
            "object-store": false,
            "orchestration": false,
            "placement": false,
            "volume": false
        },
        "disable-slow-metrics": false,
        "domain-id": "",
        "endpoint-type": "",
        "log": {
            "format": "",
            "level": ""
        },
        "multi-cloud": false,
        "os-client-config": "",
        "prefix": "",
        "web": {
            "listen-address": "",
            "telemetry-path": ""
        }
    }

    """

    # TODO: uncomment those options if we decide to expose them to the charm
    # config.

    cloud: str = Field(default="", alias="cloud")
    # collect_metric_time: bool = Field(
    #     default=False,
    #     alias="collect-metric-time",
    #     validation_alias="collect_metric_time",
    # )
    # disable_cinder_agent_uuid: bool = Field(
    #     default=False,
    #     alias="disable-cinder-agent-uuid",
    #     validation_alias="disable_cinder_agent_uuid",
    # )
    # disable_deprecated_metrics: bool = Field(
    #     default=False,
    #     alias="disable-deprecated-metrics",
    #     validation_alias="disable_deprecated_metrics",
    # )
    disable_metrics: str = Field(
        default="",
        alias="disable-metrics",
        validation_alias="disable_metrics",
    )
    disable_service: dict[str, bool] = Field(
        default_factory=lambda: {},
        alias="disable-service",
        validation_alias="disable_service",
    )
    # disable_slow_metrics: bool = Field(
    #     default=False,
    #     alias="disable-slow-metrics",
    #     validation_alias="disable_slow_metrics",
    # )
    domain_id: str = Field(default="", alias="domain-id", validation_alias="domain_id")
    endpoint_type: str = Field(default="", alias="endpoint-type", validation_alias="endpoint_type")
    log: dict[str, str] = Field(default_factory=lambda: {}, alias="log")
    # multi_cloud: bool = Field(default=False, alias="multi-cloud")
    os_client_config: str = Field(
        default="", alias="os-client-config", validation_alias="os_client_config"
    )
    prefix: str = Field(default="", alias="prefix")
    web: dict[str, str] = Field(default_factory=lambda: {}, alias="web")

    @field_validator("disable_service")
    @classmethod
    def validate_disable_service(cls, options: dict[str, bool]) -> dict[str, bool]:
        """Validate the disable_service's choices."""
        # This should be updated when the golang openstack exporter upstream
        # and the snap updates it's command line option for this part.
        # https://github.com/openstack-exporter/openstack-exporter
        available_choices = {
            "network",
            "compute",
            "image",
            "voluem",
            "identity",
            "object-store",
            "load-balancer",
            "container-infra",
            "dns",
            "baremetal",
            "gnocchi",
            "database",
            "orchestration",
            "placement",
        }
        keys = set(options.keys())
        if not keys.issubset(available_choices):
            raise ValueError(f"{keys} must be in {available_choices}")
        return options

    @field_validator("endpoint_type")
    @classmethod
    def validate_endpoint_type(cls, option: str) -> str:
        """Validate the endpoint_type's choices."""
        available_choices = {"public", "admin", "internal"}
        canonical_option = option.lower()
        if canonical_option not in available_choices:
            raise ValueError(f"'endpoint_type' must be in {available_choices}")
        return canonical_option

    @field_validator("log")
    @classmethod
    def validate_log(cls, options: dict[str, str]) -> dict[str, str]:
        """Validate the log's choices."""
        available_choices = {"format", "level"}
        keys = set(options.keys())
        if not keys.issubset(available_choices):
            raise ValueError(f"{keys} must be in {available_choices}")

        available_level_choices = {"debug", "info", "warn", "error"}
        log_level = options.get("level", "").lower()
        if log_level and log_level not in available_level_choices:
            raise ValueError(f"'log.level' must be in {available_level_choices}")

        available_format_choices = {"logfmt", "json"}
        log_format = options.get("format", "").lower()
        if log_format and log_format not in available_format_choices:
            raise ValueError(f"'log.format' must be in {available_format_choices}")

        canonical_options = {}
        if log_level:
            canonical_options["level"] = log_level
        if log_format:
            canonical_options["format"] = log_format
        return canonical_options

    @field_validator("web")
    @classmethod
    def validate_web(cls, options: dict[str, str]) -> dict[str, str]:
        """Validate the web's choices."""
        available_choices = {"listen-address", "telemetry-path"}
        keys = set(options.keys())
        if not keys.issubset(available_choices):
            raise ValueError(f"{keys} must be in {available_choices}")
        listen_address = options.get("listen-address", "")
        if listen_address and not listen_address.startswith(":"):
            listen_address = f":{listen_address}"
        try:
            _ = int(listen_address[1:])
        except ValueError as e:
            raise ValueError(
                "'web.listen-address' must be in the format of colon + integer (e.g. ':8080')."
            ) from e

        telemetry_path = options.get("telemetry-path", "")

        canonical_options = {}
        if listen_address:
            canonical_options["listen-address"] = listen_address
        if telemetry_path:
            canonical_options["telemetry-path"] = telemetry_path
        return canonical_options

    @classmethod
    def from_charm_config(cls, config: model.ConfigData) -> "ExporterSnapConfig":
        """Construct an `ExporterSnapConfig` from charm config."""
        return cls(
            cloud=config["cloud"],
            # collect_metric_time=config["collect-metric-time"],
            # disable_cinder_agent_uuid=config["disable-slow-metrics"],
            # disable_deprecated_metrics=config["disable-deprecated-metrics"],
            disable_metrics=config["disable-metrics"],
            disable_service={
                service.strip(): True for service in config["disable-services"].strip().split()
            },
            # disable_slow_metrics=config["disable-slow-metrics"],
            domain_id=config["domain-id"],
            endpoint_type=config["endpoint-type"],
            log={"level": config["log-level"], "format": config["log-format"]},
            # multi_cloud=config["multi-cloud"],
            os_client_config=str(OS_CLIENT_CONFIG),
            prefix=config["prefix"],
            web={"listen-address": str(config["port"]), "telemetry-path": WEB_TELEMETRY_PATH},
        )
