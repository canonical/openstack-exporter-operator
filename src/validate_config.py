# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Configuration validation functions."""

import re
from pathlib import Path
from typing import Collection, Optional

import yaml

MAX_PORT = 65535
PROMETHEUS_ALERT_RULES_DIR = Path(__file__).parent / "prometheus_alert_rules"

# Allowable duration units for cache_ttl from https://pkg.go.dev/time#ParseDuration
VALID_UNITS = {"ns", "us", "\u00b5s", "\u03bcs", "ms", "s", "m", "h"}

# Allowable duration units for Prometheus `for:` fields
PROM_DURATION_UNITS = {"ms", "s", "m", "h", "d", "w", "y"}

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


def alert_rule_names(rules_dir: Path = PROMETHEUS_ALERT_RULES_DIR) -> set[str]:
    """Return alert names shipped in Prometheus alert rule files."""
    names = set()
    for path in rules_dir.glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        for group in data.get("groups", []):
            for rule in group.get("rules", []):
                if alert := rule.get("alert"):
                    names.add(str(alert))
    return names


def validate_alert_for_duration(
    config: str, valid_alert_names: Optional[Collection[str]] = None
) -> Optional[str]:
    """Validate alert_for_duration configuration.

    Accepts a comma-separated list of AlertName=duration pairs.
    If valid_alert_names is passed, alert names must exist in that collection.
    Empty string is valid (means no overrides).

    Examples: "NovaComputeDown=2m", "NovaComputeDown=2m,NeutronStateCritical=30s"

    Return error message if invalid, None if valid.

    """
    if not config:
        return None
    if valid_alert_names is None:
        valid_alert_names = alert_rule_names()

    entry_pattern = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)=(.+)$")
    prom_pattern = re.compile(r"^(\d+(?:ms|[smhdwy]))+$")

    for raw in config.split(","):
        entry = raw.strip()
        if not entry:
            return f"alert_for_duration has an empty entry in {config!r}"
        m = entry_pattern.fullmatch(entry)
        if not m:
            return (
                f"alert_for_duration entry {entry!r} is not valid. "
                "Expected format: AlertName=duration"
            )
        name = m.group(1)
        if name not in valid_alert_names:
            return f"alert_for_duration alert {name!r} is not valid. Use a valid alert name."
        duration = m.group(2)
        if not prom_pattern.fullmatch(duration):
            return (
                f"alert_for_duration duration {duration!r} is not valid. "
                "Use Prometheus duration syntax, e.g. '30s', '2m', '1h30m'."
            )
        pairs = re.findall(r"(\d+)(ms|[smhdwy])", duration)
        if not any(int(n) for n, _ in pairs):
            return f"alert_for_duration duration must be non-zero. Got {duration!r}"

    return None


def parse_alert_for_duration(config: str) -> dict:
    """Parse alert_for_duration config string into {alert_name: duration}.

    Returns an empty dict when config is empty.
    """
    result = {}
    for raw in config.split(","):
        entry = raw.strip()
        if not entry:
            continue
        name, _, duration = entry.partition("=")
        result[name.strip()] = duration.strip()
    return result
