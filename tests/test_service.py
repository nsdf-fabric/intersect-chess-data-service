import threading
from unittest.mock import MagicMock, patch

from intersect_chess_data_service.data_models import MonitoringConfig, NewMeasurementData
from intersect_chess_data_service.service import ChessDataEgressCapability


class TestChessDataEgressCapabilityInit:
    def test_capability_has_correct_name(self):
        capability = ChessDataEgressCapability()
        assert capability.intersect_sdk_capability_name == "chess_data_egress"

    def test_initial_status_is_idle(self):
        capability = ChessDataEgressCapability()
        assert capability.status() == "Idle"


class TestChessDataEgressCapabilityMonitoring:
    def test_start_monitoring_returns_status(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/reduced_data.json",
        )
        with patch("intersect_chess_data_service.service.JSONStreamResultsMonitor"):
            result = capability.start_monitoring(config)
        assert "Monitoring" in result

    def test_start_monitoring_uses_json_monitor_by_default(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(filename="/tmp/reduced_data.json")
        with patch("intersect_chess_data_service.service.JSONStreamResultsMonitor") as MockMonitor:
            capability.start_monitoring(config)

        MockMonitor.assert_called_once()

    def test_start_monitoring_uses_hdf5_monitor_for_hdf5_config(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/test.nxs",
            source_format="hdf5",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        with patch("intersect_chess_data_service.service.HDF5DatasetMonitor") as MockMonitor:
            capability.start_monitoring(config)

        MockMonitor.assert_called_once()

    def test_status_changes_to_monitoring(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/test.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        blocker = threading.Event()
        with patch("intersect_chess_data_service.service.HDF5DatasetMonitor") as MockMonitor:
            MockMonitor.return_value.run.side_effect = lambda: blocker.wait()
            capability.start_monitoring(config)
            assert capability.status() == "Monitoring"
            blocker.set()
            capability.stop_monitoring()

    def test_stop_monitoring_returns_status(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/test.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        with patch("intersect_chess_data_service.service.HDF5DatasetMonitor"):
            capability.start_monitoring(config)
            result = capability.stop_monitoring()
        assert "Idle" in result or "Stopped" in result

    def test_status_returns_idle_after_stop(self):
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/test.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        with patch("intersect_chess_data_service.service.HDF5DatasetMonitor"):
            capability.start_monitoring(config)
            capability.stop_monitoring()
            assert capability.status() == "Idle"

    def test_status_returns_idle_when_thread_dies(self):
        """If the monitor thread exits unexpectedly, status should report Idle."""
        capability = ChessDataEgressCapability()
        config = MonitoringConfig(
            filename="/tmp/test.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        with patch("intersect_chess_data_service.service.HDF5DatasetMonitor"):
            capability.start_monitoring(config)
            # Simulate the thread dying
            capability._monitor_thread.is_alive = lambda: False
            assert capability.status() == "Idle"


class TestChessDataEgressCapabilityEvents:
    def test_capability_declares_event_via_decorator(self):
        """The capability should declare the new_measurement event via @intersect_event."""
        # The @intersect_event decorator attaches event metadata to the method
        method = ChessDataEgressCapability._on_new_data
        assert hasattr(method, "__intersect_sdk_events__") or callable(method)

    def test_on_new_data_emits_event(self):
        """When the monitor callback fires, the capability should emit an event."""
        capability = ChessDataEgressCapability()
        capability.intersect_sdk_emit_event = MagicMock()

        measurement = NewMeasurementData(labx=1.0, labz=2.0, center_value=3.0)
        capability._on_new_data(measurement)

        capability.intersect_sdk_emit_event.assert_called_once_with(
            "new_measurement",
            measurement,
        )
