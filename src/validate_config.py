"""Configuration validation functions."""

import re
from typing import Optional

MAX_PORT = 65535


def validate_port(port: int) -> Optional[str]:
    """Validate port configuration.

    Return error message if invalid, None if valid.

    """
    if port <= 0 or port > MAX_PORT:
        return f"Port must be between 1 and {MAX_PORT}, got {port}"
    return None


def validate_cache_ttl(cache_ttl: str) -> Optional[str]:
    """Validate cache_ttl configuration.

    Return error message if invalid, None if valid.

    """
    if not re.match(r"^\d+[smhd]$", cache_ttl):
        return f"cache_ttl must be in format <number><unit> \
                where unit is s, m, h, or d, got {cache_ttl}"
    return None


def validate_snap_channel(snap_channel: str) -> Optional[str]:
    """Validate snap_channel configuration.

    Return error message if invalid, None if valid.

    """
    if snap_channel != "latest/stable":
        if not re.match(r"^(latest/|[^/]+/)(stable|candidate|beta|edge)$", snap_channel):
            return f"Invalid snap_channel, must be one of 'latest/stable', \
                'latest/candidate', 'latest/beta', 'latest/edge', got {snap_channel}"
    return None
