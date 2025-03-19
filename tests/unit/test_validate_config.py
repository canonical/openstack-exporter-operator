import pytest

from validate_config import validate_cache_ttl, validate_port, validate_snap_channel


@pytest.mark.parametrize(
    "port",
    [
        9180,
        1,
        65535,
    ],
)
def test_validate_port_valid(port):
    """Test validate port function with valid ports."""
    assert validate_port(port) is None


@pytest.mark.parametrize(
    "port",
    [
        0,
        -1,
        65536,
    ],
)
def test_validate_port_invalid(port):
    """Test validate port function with invalid ports."""
    assert validate_port(port) == f"Port must be between 1 and 65535, got {port}"


@pytest.mark.parametrize(
    "cache_ttl",
    [
        "1s",
        "1m",
        "1h",
        "1d",
    ],
)
def test_validate_cache_ttl_valid(cache_ttl):
    """Test validate cache_ttl function with valid cache_ttl."""
    assert validate_cache_ttl(cache_ttl) is None


@pytest.mark.parametrize(
    "cache_ttl",
    [
        "1",
        "1x",
        "1ms",
        "1y",
    ],
)
def test_validate_cache_ttl_invalid(cache_ttl):
    """Test validate cache_ttl function with invalid cache_ttl."""
    assert validate_cache_ttl(cache_ttl) == (
        f"cache_ttl must be in format <number><unit> where unit is s, m, h, or d, got {cache_ttl}"
    )


@pytest.mark.parametrize(
    "snap_channel",
    [
        "latest/stable",
        "latest/candidate",
        "latest/beta",
        "latest/edge",
    ],
)
def test_validate_snap_channel_valid(snap_channel):
    """Test validate snap_channel function with valid snap_channel."""
    assert validate_snap_channel(snap_channel) is None


@pytest.mark.parametrize(
    "snap_channel",
    [
        "invalid/channel",
        "latest-stable",
        "Latest/Beta",
        "latest/edge/",
    ],
)
def test_validate_snap_channel_invalid(snap_channel):
    """Test validate snap_channel function with invalid snap_channel."""
    assert validate_snap_channel(snap_channel) == (
        f"Invalid snap_channel, must be one of 'latest/stable', 'latest/candidate', "
        f"'latest/beta', 'latest/edge', got {snap_channel}"
    )
