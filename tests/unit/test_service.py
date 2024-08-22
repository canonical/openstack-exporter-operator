# Copyright 2024 Canonical
# See LICENSE file for licensing details.

from unittest import mock

import pytest

import service


@mock.patch("service.remove_upstream_snap")
@mock.patch("service.remove_snap_as_resource")
@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap")
def test_snap_install_or_refresh_with_resource(
    mock_snap, mock_workaround, mock_remove_resource, mock_remove_upstream
):
    """Test snap installation with resource."""
    result = service.snap_install_or_refresh("my-resource", "latest/stable")
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
    mock_snap.remove.assert_called_with(["golang-openstack-exporter"])


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
