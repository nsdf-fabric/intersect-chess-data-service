import logging
import threading

from intersect_sdk import (
    IntersectBaseCapabilityImplementation,
    IntersectEventDefinition,
    intersect_message,
    intersect_status,
)

from .data_models import MonitoringConfig, NewMeasurementData
from .monitor import HDF5DatasetMonitor, JSONStreamResultsMonitor

logger = logging.getLogger(__name__)


class ChessDataEgressCapability(IntersectBaseCapabilityImplementation):
    """INTERSECT capability that monitors CHESS reduced data and emits measurements."""

    intersect_sdk_capability_name = "chess_data_egress"
    intersect_sdk_events = {
        "new_measurement": IntersectEventDefinition(event_type=NewMeasurementData),
    }

    def __init__(self):
        super().__init__()
        self._monitor: HDF5DatasetMonitor | JSONStreamResultsMonitor | None = None
        self._monitor_thread: threading.Thread | None = None

    @intersect_message()
    def start_monitoring(self, config: MonitoringConfig) -> str:
        """Start monitoring a reduced data source for new measurements."""
        if self._monitor is not None:
            self.stop_monitoring()

        if config.source_format == "json":
            self._monitor = JSONStreamResultsMonitor(
                filename=config.filename,
                labx_key=config.labx_key,
                labz_key=config.labz_key,
                value_key=config.value_key,
                callback=self._on_new_data,
                poll_interval=config.poll_interval,
                skip_invalid_values=config.skip_invalid_values,
            )
        elif config.source_format == "hdf5":
            self._monitor = HDF5DatasetMonitor(
                filename=config.filename,
                dataset_path=config.dataset_path or "",
                callback=self._on_new_data,
                poll_interval=config.poll_interval,
                dataset_names=config.dataset_names,
                swmr=config.swmr,
            )
        else:
            raise ValueError(f"Unsupported source_format: {config.source_format}")
        self._monitor_thread = threading.Thread(target=self._monitor.run, daemon=True)
        self._monitor_thread.start()

        logger.info("Monitoring started for %s (%s)", config.filename, config.source_format)
        return f"Monitoring {config.filename}"

    @intersect_message()
    def stop_monitoring(self) -> str:
        """Stop the current monitoring session."""
        if self._monitor is not None:
            self._monitor.stop()
            if self._monitor_thread is not None:
                self._monitor_thread.join(timeout=5.0)
            self._monitor = None
            self._monitor_thread = None

        logger.info("Monitoring stopped")
        return "Idle"

    @intersect_status()
    def status(self) -> str:
        """Return current monitoring status."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return "Monitoring"
        return "Idle"

    def _on_new_data(self, measurement: NewMeasurementData):
        """Callback invoked by the monitor when new data is detected."""
        logger.info(
            "New measurement: labx=%.4f, labz=%.4f, value=%.6f",
            measurement.labx,
            measurement.labz,
            measurement.center_value,
        )
        self.intersect_sdk_emit_event("new_measurement", measurement)
