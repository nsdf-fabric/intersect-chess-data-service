from __future__ import annotations

import logging
import threading

from intersect_sdk import (
    IntersectBaseCapabilityImplementation,
    IntersectEventDefinition,
    intersect_message,
    intersect_status,
)

from .data_models import MonitoringConfig, NewMeasurementData
from .monitor import HDF5DatasetMonitor

logger = logging.getLogger(__name__)


class ChessDataEgressCapability(IntersectBaseCapabilityImplementation):
    """INTERSECT capability that monitors HDF5 files and emits events on new measurements."""

    intersect_sdk_capability_name = "chess-data-egress"

    intersect_sdk_events = {
        "new_measurement": IntersectEventDefinition(
            event_type=NewMeasurementData,
            event_documentation="Emitted when a new measurement is detected in the HDF5 file",
        ),
    }

    def __init__(self):
        super().__init__()
        self._monitor: HDF5DatasetMonitor | None = None
        self._monitor_thread: threading.Thread | None = None
        self._monitoring = False

    @intersect_message()
    def start_monitoring(self, config: MonitoringConfig) -> str:
        """Start monitoring an HDF5 file for new measurements."""
        if self._monitor is not None:
            self.stop_monitoring()

        self._monitor = HDF5DatasetMonitor(
            filename=config.filename,
            dataset_path=config.dataset_path,
            callback=self._on_new_data,
            poll_interval=config.poll_interval,
            dataset_names=config.dataset_names,
        )
        self._monitor_thread = threading.Thread(target=self._monitor.run, daemon=True)
        self._monitor_thread.start()
        self._monitoring = True

        logger.info("Monitoring started for %s", config.filename)
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

        self._monitoring = False
        logger.info("Monitoring stopped")
        return "Idle"

    @intersect_status()
    def status(self) -> str:
        """Return current monitoring status."""
        return "Monitoring" if self._monitoring else "Idle"

    def _on_new_data(self, measurement: NewMeasurementData):
        """Callback invoked by the monitor when new data is detected."""
        logger.info(
            "New measurement: labx=%.4f, labz=%.4f, value=%.6f",
            measurement.labx,
            measurement.labz,
            measurement.center_value,
        )
        self.intersect_sdk_emit_event("new_measurement", measurement.model_dump())
