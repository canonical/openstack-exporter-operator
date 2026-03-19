# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import datetime
from unittest import mock

import pytest

from ssdlc import Service, SSDLCSysEvent, log_ssdlc_system_event


class TestLogSsdlcSystemEvent:
    """Test log_ssdlc_system_event function."""

    @pytest.mark.parametrize(
        "event, expected_event_str, expected_description",
        [
            (
                SSDLCSysEvent.STARTUP,
                "sys_startup:charmed-openstack-exporter",
                "openstack-exporter start service charmed-openstack-exporter",
            ),
            (
                SSDLCSysEvent.SHUTDOWN,
                "sys_shutdown:charmed-openstack-exporter",
                "openstack-exporter shutdown service charmed-openstack-exporter",
            ),
            (
                SSDLCSysEvent.RESTART,
                "sys_restart:charmed-openstack-exporter",
                "openstack-exporter restart service charmed-openstack-exporter",
            ),
            (
                SSDLCSysEvent.CRASH,
                "sys_crash:charmed-openstack-exporter",
                "openstack-exporter service charmed-openstack-exporter crash",
            ),
        ],
    )
    @mock.patch("ssdlc.logger")
    @mock.patch("ssdlc.datetime")
    def test_log_ssdlc_system_event(
        self,
        mock_datetime,
        mock_logger,
        event,
        expected_event_str,
        expected_description,
    ):
        mock_now = mock.MagicMock()
        mock_now.isoformat.return_value = "2025-01-01T12:00:00+00:00"
        mock_datetime.now.return_value.astimezone.return_value = mock_now

        log_ssdlc_system_event(event)

        logged = mock_logger.warning.call_args[0][0]
        assert logged["datetime"] == "2025-01-01T12:00:00+00:00"
        assert logged["appid"] == "service.charmed-openstack-exporter"
        assert logged["event"] == expected_event_str
        assert logged["level"] == "WARN"
        assert logged["description"] == expected_description

    @mock.patch("ssdlc.logger")
    @mock.patch("ssdlc.datetime")
    def test_log_ssdlc_system_event_with_msg(self, mock_datetime, mock_logger):
        mock_now = mock.MagicMock()
        mock_now.isoformat.return_value = "2025-01-01T12:00:00+00:00"
        mock_datetime.now.return_value.astimezone.return_value = mock_now

        log_ssdlc_system_event(SSDLCSysEvent.CRASH, msg="Out of memory")

        logged = mock_logger.warning.call_args[0][0]
        assert logged["description"] == (
            "openstack-exporter service charmed-openstack-exporter crash Out of memory"
        )

    @mock.patch("ssdlc.logger")
    @mock.patch("ssdlc.datetime")
    def test_log_ssdlc_system_event_custom_service(self, mock_datetime, mock_logger):
        mock_now = mock.MagicMock()
        mock_now.isoformat.return_value = "2025-01-01T12:00:00+00:00"
        mock_datetime.now.return_value.astimezone.return_value = mock_now

        log_ssdlc_system_event(
            SSDLCSysEvent.STARTUP,
            subject=Service.CHARMED_OPENSTACK_EXPORTER,
        )

        logged = mock_logger.warning.call_args[0][0]
        assert logged["appid"] == "service.charmed-openstack-exporter"
        assert logged["event"] == "sys_startup:charmed-openstack-exporter"

    @mock.patch("ssdlc.logger")
    @mock.patch("ssdlc.datetime")
    def test_log_ssdlc_system_event_datetime_format(self, mock_datetime, mock_logger):
        """Test that datetime is in ISO 8601 format with timezone."""
        # Use a real datetime to test formatting
        test_time = datetime.datetime(2025, 1, 15, 14, 30, 45, tzinfo=datetime.timezone.utc)
        mock_datetime.now.return_value.astimezone.return_value = test_time

        log_ssdlc_system_event(SSDLCSysEvent.STARTUP)

        logged_data = mock_logger.warning.call_args[0][0]
        # Verify ISO 8601 format with timezone
        assert logged_data["datetime"] == "2025-01-15T14:30:45+00:00"
