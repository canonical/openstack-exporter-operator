# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Configuration validation functions."""

import logging
import re
from typing import Optional, cast

import yaml
from cosl import CosTool
from cosl.cos_tool import OfficialRuleFileFormat

logger = logging.getLogger(__name__)

MAX_PORT = 65535

# Allowable duration units for cache_ttl from https://pkg.go.dev/time#ParseDuration
VALID_UNITS = {"ns", "us", "\u00b5s", "\u03bcs", "ms", "s", "m", "h"}

# Regex patterns for cache_ttl
NUMBER_PATTERN = r"(\d+\.?\d*|\d*\.\d+)"
DURATION_PATTERN = (
    rf"^\+?{NUMBER_PATTERN}[a-zµ\u03bc\u05bc]+({NUMBER_PATTERN}[a-zµ\u03bc\u05bc]+)*$"
)


def validate_port(port: int) -> Optional[str]:
    """Validate port configuration.

    Return error message if invalid, None if valid.

    """
    if port <= 0 or port > MAX_PORT:
        return f"Port must be between 1 and {MAX_PORT}, got {port}"
    return None


def validate_cache_ttl(cache_ttl: str) -> Optional[str]:
    """Validate cache_ttl configuration.

    Allow patterns in https://pkg.go.dev/time#ParseDuration,
    Add constraints for negative and zero values.
    No overflow checks (ParseDuration can handle extremely large values appropriately at runtime)

    Return error message if invalid, None if valid.

    """
    if not cache_ttl:
        return f"Cache_ttl must be non-empty. Got {cache_ttl}"

    if cache_ttl[0] == "-":
        return f"Cache_ttl must be non-negative. Got {cache_ttl}"

    # Validate overall format
    if not re.fullmatch(DURATION_PATTERN, cache_ttl):
        return (
            "Cache_ttl is not in a valid format. It must be a valid format for "
            "https://pkg.go.dev/time#ParseDuration; for example '20m' or '2h30m'"
        )

    # Get each number-unit pair
    matches = re.findall(r"(\d+\.?\d*|\d*\.\d+)([a-zµ\u03bc\u05bc]+)", cache_ttl)

    # Validate non-zero duration
    if not any(float(number) for number, _ in matches):
        return f"Cache_ttl must be non-zero. Got {cache_ttl}"

    # Validate units
    for _, unit in matches:
        if unit not in VALID_UNITS:
            return (
                f"Cache_ttl has invalid time unit: {unit}. "
                f"Valid units are 'ns', 'us' (or 'µs'), 'ms', 's', 'm', 'h'."
            )

    return None


def validate_alert_rules(config: str) -> Optional[str]:
    """Validate the alert_rules configuration.

    The value is a full Prometheus rules document that replaces the shipped alert rules.
    Empty string (default) keeps the shipped rules and is valid.

    The document is validated with the bundled `cos-tool` binary via `cosl.CosTool`, which
    uses Prometheus' own rule parser, so invalid PromQL expressions and durations are rejected.

    Return error message if invalid, None if valid.

    """
    if not config.strip():
        return None

    try:
        data = yaml.safe_load(config)
    except yaml.YAMLError as error:
        return f"alert_rules is not valid YAML: {error}"

    if not isinstance(data, dict) or not data.get("groups"):
        return "alert_rules must be a Prometheus rules document with a top-level 'groups' key."

    valid, errors = CosTool("promql").validate_alert_rules(cast(OfficialRuleFileFormat, data))
    if not valid:
        return f"alert_rules failed Prometheus validation: {errors}"

    return None
