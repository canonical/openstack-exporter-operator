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
    resource = mock.MagicMock(spec_set=service.SnapResource)
    resource.size = 128
    resource.snap_name = service.SNAP_NAME
    resource.path = path = "/var/resources/openstack-exporter.snap"
    service.snap_install_or_refresh(resource, "latest/stable")
    mock_remove_upstream.assert_called_once()
    mock_snap.install_local.assert_called_once_with(path, dangerous=True)
    mock_workaround.assert_called_once()
    mock_remove_resource.assert_not_called()


@mock.patch("service.remove_upstream_snap")
@mock.patch("service.remove_snap_as_resource")
@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap")
def test_snap_install_or_refresh_with_resource_from_upstream(
    mock_snap, mock_workaround, mock_remove_resource, mock_remove_upstream
):
    """Test snap installation with resource using the upstream."""
    resource = mock.MagicMock(spec_set=service.SnapResource)
    resource.size = 128
    resource.snap_name = service.UPSTREAM_SNAP
    resource.path = "/var/resources/openstack-exporter.snap"
    service.snap_install_or_refresh(resource, "my-channel")
    mock_remove_upstream.assert_called_once()
    mock_snap.install_local.assert_not_called()
    mock_workaround.assert_called_once()
    mock_remove_resource.assert_called_once()
    mock_snap.add.assert_called_once_with(service.SNAP_NAME, channel="my-channel")


@mock.patch("service.remove_upstream_snap")
@mock.patch("service.remove_snap_as_resource")
@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap")
def test_snap_install_or_refresh_snap_store(
    mock_snap, mock_workaround, mock_remove_resource, mock_remove_upstream
):
    """Test snap installation using the snap store by having an empty resource."""
    resource = mock.MagicMock(spec_set=service.SnapResource)
    resource.size = 0
    resource.snap_name = None
    service.snap_install_or_refresh(resource, "my-channel")
    resource.path = "/var/resources/openstack-exporter.snap"
    mock_remove_upstream.assert_called_once()
    mock_snap.install_local.assert_not_called()
    mock_snap.add.assert_called_once_with(service.SNAP_NAME, channel="my-channel")
    mock_workaround.assert_called_once()
    mock_remove_resource.assert_called_once()


@mock.patch("service.workaround_bug_268")
@mock.patch("service.snap.add")
def test_snap_install_or_refresh_exception_raises(mock_snap, mock_workaround):
    """Test that when an exception happens, it will raise an exception to the caller."""
    resource = mock.MagicMock(spec_set=service.SnapResource)
    mock_snap.side_effect = service.snap.SnapError("My Error")
    with pytest.raises(service.snap.SnapError):
        service.snap_install_or_refresh(resource, "my-channel")
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


@mock.patch("service.SquashFsImage.from_file")
@mock.patch("service.yaml.safe_load")
@mock.patch("service.os.path.getsize")
def test_snap_resource(mock_size, mock_yaml, mock_image):
    """Test the SnapResource class."""
    model = mock.MagicMock(spec_set=service.Model)
    mocked_resource = mock.MagicMock()
    mocked_resource.absolute.return_value = path = "/var/resources/openstack-exporter.snap"
    mock_size.return_value = size = 128
    model.resources.fetch.return_value = mocked_resource
    mock_file = mock.MagicMock()
    mock_file.name = "snap.yaml"
    mock_image.return_value.__enter__.return_value = [mock_file]
    mock_image.__exit__.return_value = None

    mock_yaml.return_value = {
        "name": "golang-openstack-exporter",
        "version": "latest",
        "summary": "OpenStack Exporter for Prometheus",
        "description": "The OpenStack exporter, exports Prometheus metrics",
        "apps": {
            "openstack-exporter": {
                "command": "bin/openstack-exporter",
                "plugs": ["home", "network", "network-bind"],
                "command-chain": ["snap/command-chain/snapcraft-runner"],
            }
        },
        "architectures": ["amd64"],
        "assumes": ["command-chain"],
        "base": "core18",
        "confinement": "strict",
        "grade": "devel",
    }

    resource = service.SnapResource("openstack-exporter", model)

    assert resource.path == path
    assert resource.size == size
    assert resource.snap_name == "golang-openstack-exporter"


def test_snap_resource_empty_path():
    """Test snap resource when the path is empty."""
    model = mock.MagicMock(spec_set=service.Model)
    model.resources.fetch.side_effect = service.ModelError("Failed to fetch")

    resource = service.SnapResource("openstack-exporter", model)
    assert resource.path is None
    assert resource.size is None
    assert resource.snap_name is None


@mock.patch("service.SquashFsImage.from_file")
def test_snap_resource_err(mock_image):
    """Test SnapResource fails to get the snap name."""
    model = mock.MagicMock(spec_set=service.Model)
    mock_image.side_effect = Exception("File not found")

    resource = service.SnapResource("openstack-exporter", model)

    with pytest.raises(service.snap.SnapError):
        _ = resource.snap_name
