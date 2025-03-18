# Copyright 2024 Canonical
# See LICENSE file for licensing details.

from unittest import mock

import pytest

import service


class TestSnapService:
    """Test SnapService class."""

    def test_configure(self, mocker):
        mock_client = mocker.Mock()
        snap_service = service.SnapService(mock_client)
        config = {"config-a": "a", "config-b": "b"}
        snap_service.configure(config)
        mock_client.set.assert_called_with(config, typed=True)


@mock.patch("service.remove_upstream_snap")
@mock.patch("service.remove_snap_as_resource")
@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap")
def test_snap_install_or_refresh_with_resource(
    mock_snap, mock_workaround, mock_remove_resource, mock_remove_upstream
):
    """Test snap installation with resource."""
    service.snap_install_or_refresh("my-resource", "latest/stable")
    mock_remove_upstream.assert_called_once()
    mock_snap.install_local.assert_called_once_with("my-resource", dangerous=True)
    mock_workaround.assert_called_once()
    mock_remove_resource.assert_not_called()


@mock.patch("service.remove_upstream_snap")
@mock.patch("service.remove_snap_as_resource")
@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap")
def test_snap_install_or_refresh_snap_store(
    mock_snap, mock_workaround, mock_remove_resource, mock_remove_upstream
):
    """Test snap installation using the snap store."""
    service.snap_install_or_refresh("", "my-channel")
    mock_remove_upstream.assert_called_once()
    mock_snap.install_local.assert_not_called()
    mock_snap.add.assert_called_once_with(service.SNAP_NAME, channel="my-channel")
    mock_workaround.assert_called_once()
    mock_remove_resource.assert_called_once()


@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap.add")
def test_snap_install_or_refresh_exception_raises(mock_snap, mock_workaround):
    """Test that when an exception happens, it will raise an exception to the caller."""
    mock_snap.side_effect = service.snap.SnapError("My Error")
    with pytest.raises(service.snap.SnapError):
        service.snap_install_or_refresh("", "my-channel")
    mock_workaround.assert_not_called()


@mock.patch("service.snap")
def test_remove_upstream_snap(mock_snap):
    """Test remove upstream snap function."""
    service.remove_upstream_snap()
    mock_snap.remove.assert_called_with([service.UPSTREAM_SNAP])


@mock.patch("service.snap.remove")
def test_remove_upstream_snap_exception(mock_snap_remove):
    """Test remove upstream snap function when raises exception."""
    mock_snap_remove.side_effect = service.snap.SnapError("My Error")
    with pytest.raises(service.snap.SnapError):
        service.remove_upstream_snap()


@mock.patch("service.snap.SnapCache")
@mock.patch("service.snap.remove")
def test_remove_snap_as_resource_remove(mock_snap_remove, mock_snap_cache):
    """Test remove snap as a resource."""
    snap_cache = mock.MagicMock()

    snap = mock.MagicMock()
    snap.present = True
    snap.revision = "x1"

    snap_cache.__getitem__.return_value = snap
    mock_snap_cache.return_value = snap_cache

    service.remove_snap_as_resource()

    mock_snap_remove.assert_called_once_with(service.SNAP_NAME)


@mock.patch("service.snap.SnapCache")
@mock.patch("service.snap.remove")
def test_remove_snap_as_resource_not_remove(mock_snap_remove, mock_snap_cache):
    """Test remove snap as a resource when the snap installed is not a resource."""
    snap_cache = mock.MagicMock()

    snap = mock.MagicMock()
    snap.present = True
    snap.revision = "1"

    snap_cache.__getitem__.return_value = snap
    mock_snap_cache.return_value = snap_cache

    service.remove_snap_as_resource()

    mock_snap_remove.assert_not_called()


@mock.patch("service.snap.SnapCache")
@mock.patch("service.snap.remove")
def test_remove_snap_as_resource_exception(mock_snap_remove, mock_snap_cache):
    """Test remove snap as resource when raises exception."""
    snap_cache = mock.MagicMock()

    snap = mock.MagicMock()
    snap.present = True
    snap.revision = "x1"

    snap_cache.__getitem__.return_value = snap
    mock_snap_cache.return_value = snap_cache

    mock_snap_remove.side_effect = service.snap.SnapError("My Error")
    with pytest.raises(service.snap.SnapError):
        service.remove_snap_as_resource()


def test_get_installed_snap_service(mocker):
    """Test retrieving snap service for different scenarios."""
    mock_snap_cache = mocker.patch("service.snap.SnapCache")
    mock_snap_client = mocker.Mock()
    mock_snap_cache.return_value = {
        "existing-snap": mock_snap_client,
    }
    mock_snap_service_init = mocker.patch("service.SnapService.__init__", return_value=None)

    # Scenario 1: Snap exists
    result = service.get_installed_snap_service("existing-snap")
    mock_snap_service_init.assert_called_once_with(mock_snap_client)
    assert isinstance(result, service.SnapService)

    # Scenario 2: Snap doesn't exist
    mock_snap_cache.reset_mock()
    mock_snap_service_init.reset_mock()
    mock_snap_cache.side_effect = service.snap.SnapNotFoundError("Snap not found")
    with pytest.raises(service.snap.SnapNotFoundError, match="Snap not found"):
        service.get_installed_snap_service("non-existing-snap")

    mock_snap_service_init.assert_not_called()

    # check error was logged
    mock_logger = mocker.patch("service.logger.error")
    with pytest.raises(service.snap.SnapNotFoundError):
        service.get_installed_snap_service("non-existing-snap")
    mock_logger.assert_called_once()


def test_restart_and_enable(mocker):
    """Test restart_and_enable method ensures service is restarted and enabled."""
    mock_snap_client = mocker.Mock()
    snap_service = service.SnapService(mock_snap_client)

    manager = mocker.Mock()
    manager.attach_mock(mock_snap_client.restart, "restart")
    manager.attach_mock(mock_snap_client.start, "start")

    snap_service.restart_and_enable()

    # Check the calls were made
    mock_snap_client.restart.assert_called_once()
    mock_snap_client.start.assert_called_once_with(enable=True)

    # Check the calls were made in the correct order
    expected_calls = [mocker.call.restart(), mocker.call.start(enable=True)]
    assert manager.mock_calls == expected_calls


def test_stop(mocker):
    """Test stop method correctly stops and disables the snap service."""
    mock_snap_client = mocker.Mock()
    snap_service = service.SnapService(mock_snap_client)
    snap_service.stop()

    mock_snap_client.stop.assert_called_once_with(disable=True)
    mock_snap_client.restart.assert_not_called()
    mock_snap_client.start.assert_not_called()


def test_is_active(mocker):
    """Test is_active correctly reports service status."""
    mock_snap_client = mocker.Mock()
    snap_service = service.SnapService(mock_snap_client)

    # All services are active
    all_active = {"service1": {"active": True}, "service2": {"active": True}}
    mock_snap_client.services = all_active
    assert snap_service.is_active() is True

    # One service is not active
    mixed_active = {"service1": {"active": True}, "service2": {"active": False}}
    mock_snap_client.services = mixed_active
    assert snap_service.is_active() is False

    # All services are not active
    none_active = {"service1": {"active": False}, "service2": {"active": False}}
    mock_snap_client.services = none_active
    assert snap_service.is_active() is False

    # Service missing 'active' key
    missing_key = {
        "service1": {"active": True},
        "service2": {},
    }
    mock_snap_client.services = missing_key
    assert snap_service.is_active() is False

    # Empty services dict
    mock_snap_client.services = {}
    assert snap_service.is_active() is True


def test_present_property(mocker):
    """Test the present property correctly reflects the snap client's present property."""
    mock_snap_client = mocker.Mock()
    snap_service = service.SnapService(mock_snap_client)

    mock_snap_client.present = True
    assert snap_service.present is True

    mock_snap_client.present = False
    assert snap_service.present is False

    # Make sure the property is accessed, not a method call
    assert isinstance(mock_snap_client.present, bool)
    assert not hasattr(mock_snap_client.present, "called")


def test_workaround_bug_268(mocker):
    """Test that the bug 268 workaround creates the correct systemd override."""
    # Mock the file system operations
    mock_makedirs = mocker.patch("os.makedirs")
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    mock_logger = mocker.patch("service.logger.info")

    service.workaround_bug_268()

    # Check for correct directory creation
    expected_dir = f"/etc/systemd/system/snap.{service.SNAP_NAME}.service.service.d"
    mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)

    # Check the file is opened with the correct path and mode
    mock_open.assert_called_once_with(f"{expected_dir}/bug_268.conf", "w")

    # Check the correct content is written to the file
    file_handle = mock_open()
    file_handle.write.assert_called_once_with(
        "[Service]\nEnvironment=OS_COMPUTE_API_VERSION=2.87\n"
    )

    # Check logged message
    mock_logger.assert_called_once_with("Adding service override to workaround bug 268")
