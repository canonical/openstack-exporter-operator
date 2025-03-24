"""Configuration validation functions."""

import re
from typing import Optional

MAX_PORT = 65535

# Allowable duration units for cache_ttl from https://pkg.go.dev/time#ParseDuration
VALID_UNITS = {"ns", "us", "\u05bcs", "\u03bcs", "ms", "s", "m", "h"}

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
    if not cache_ttl or cache_ttl[0] == "-":
        return f"Cache_ttl must be non-empty and non-negative. Got {cache_ttl}"

    # Validate overall format
    if not re.fullmatch(DURATION_PATTERN, cache_ttl):
        return f"Invalid regex format. Valid pattern is {DURATION_PATTERN}. Got {cache_ttl}"

    # Get each number-unit pair
    matches = re.findall(r"(\d+\.?\d*|\d*\.\d+)([a-zµ\u03bc\u05bc]+)", cache_ttl)

    # Validate non-zero duration
    if not any(float(number) for number, _ in matches):
        return f"Cache_ttl must be non-zero. Got {cache_ttl}"

    # Validate units
    for _, unit in matches:
        if unit not in VALID_UNITS:
            return f"Invalid time unit {unit}. Valid units are {VALID_UNITS}."

    return None


def validate_snap_channel(snap_channel: str) -> Optional[str]:
    """Validate snap_channel configuration.

    Return error message if invalid, None if valid.

    """
    if "/" not in snap_channel:
        return f"Invalid snap_channel format: {snap_channel}. Expected format like 'track/risk'."

    parts = snap_channel.split("/")
    for part in parts:
        if not part:
            return (
                f"Invalid snap_channel format: {snap_channel}. Expected format like 'track/risk'."
            )

    return None
