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
        "5s",
        "30s",
        "1478s",
        "+5s",
        "5.0s",
        "5.6s",
        "5.s",
        ".5s",
        "1.0s",
        "1.00s",
        "1.004s",
        "1.0040s",
        "100.00100s",
        "10ns",
        "11us",
        "12\u05bcs",  # U+00B5
        "12\u03bcs",  # U+03BC
        "13ms",
        "14s",
        "15m",
        "16h",
        "3h30m",
        "10.5s4m",
        "2m3.4s",
        "1h2m3s4ms5us6ns",
        "39h9m14.425s",
        "52763797000ns",
        "0.3333333333333333333h",
        "9007199254740993ns",
        "9223372036854775807ns",
        "9223372036854775.807us",
        "9223372036s854ms775us807ns",
        "+9223372036854775808ns",
        "+9223372036854775.808us",
        "+9223372036s854ms775us808ns",
        "+2562047h47m16.854775808s",
        "0.100000000000000000000h",
        "0.830103483285477580700h",
    ],
)
def test_validate_cache_ttl_valid(cache_ttl):
    """Test validate cache_ttl function with valid cache_ttl.

    Test cases from https://cs.opensource.google/go/go/+/master:src/time/time_test.go;l=994
    Exclude zero and negative sign values.

    """
    assert validate_cache_ttl(cache_ttl) is None


@pytest.mark.parametrize(
    "cache_ttl",
    [
        "",
        "3",
        "-",
        "+",
        "s",
        ".",
        "0",
        "+0s-.",
        "-3h30m",
        "0s0m",
        ".s",
        "+.s",
        "1d",
        "\x85\x85",
        "\xffff",
        "hello \xffff world",
        "\ufffd",  # utf8.RuneError
        "\ufffd hello \ufffd world",  # utf8.RuneError
    ],
)
def test_validate_cache_ttl_invalid(cache_ttl):
    """Test validate cache_ttl function with invalid cache_ttl.

    Test cases from https://cs.opensource.google/go/go/+/master:src/time/time_test.go;l=994
    Added invalid cases for empty string, zero value, single unit, and negative sign.

    """
    assert validate_cache_ttl(cache_ttl) is not None


@pytest.mark.parametrize(
    "snap_channel",
    [
        "latest/stable",
        "latest/candidate",
        "latest/beta",
        "latest/edge",
        "v32/beta",
        "latest/edge/test-fix-bug1",
    ],
)
def test_validate_snap_channel_valid(snap_channel):
    """Test validate snap_channel function with valid snap_channel."""
    assert validate_snap_channel(snap_channel) is None


@pytest.mark.parametrize(
    "snap_channel",
    [
        "",
        "invalid-channel",
        "/latest/stable",
        "LatestBeta",
        "latestedge/",
        "v1/edge/",
        "latest//edge",
        "//latest/edge",
    ],
)
def test_validate_snap_channel_invalid(snap_channel):
    """Test validate snap_channel function with invalid snap_channel."""
    assert validate_snap_channel(snap_channel) == (
        f"Invalid snap_channel format: {snap_channel}. Expected format like 'track/risk'."
    )
