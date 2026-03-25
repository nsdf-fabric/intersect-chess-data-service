from __future__ import annotations

import logging
import os
import threading
from typing import Callable

import h5py

from .data_models import NewMeasurementData

logger = logging.getLogger(__name__)


class HDF5DatasetMonitor:
    """Monitors an HDF5 file for new data using SWMR (Single Writer Multiple Reader) polling.

    Three-phase approach:
      1. Wait for the file to exist on disk
      2. Wait for the target dataset group to exist inside the file
      3. Poll for dataset size changes, calling the callback for each new data point
    """

    def __init__(
        self,
        filename: str,
        dataset_path: str,
        callback: Callable[[NewMeasurementData], None],
        poll_interval: float = 0.5,
        dataset_names: list[str] | None = None,
    ):
        self.filename = filename
        self.dataset_path = dataset_path
        self.callback = callback
        self.poll_interval = poll_interval
        self.dataset_names = dataset_names or ["labx", "labz", "values"]
        self._stop_event = threading.Event()

    def stop(self):
        """Signal the monitor to stop."""
        self._stop_event.set()

    def run(self):
        """Main monitoring loop. Blocks until stop() is called."""
        self._wait_for_file()
        if self._stop_event.is_set():
            return

        self._wait_for_dataset()
        if self._stop_event.is_set():
            return

        self._poll_for_changes()

    def _wait_for_file(self):
        """Phase 1: Wait for the HDF5 file to appear on disk."""
        logger.info("Waiting for file: %s", self.filename)
        while not self._stop_event.is_set():
            if os.path.exists(self.filename):
                logger.info("File detected: %s", self.filename)
                return
            self._stop_event.wait(self.poll_interval)

    def _wait_for_dataset(self):
        """Phase 2: Wait for all required datasets to exist inside the file."""
        required_paths = [f"{self.dataset_path}/{name}" for name in self.dataset_names]
        logger.info("Waiting for datasets %s in %s", self.dataset_names, self.filename)
        while not self._stop_event.is_set():
            try:
                with h5py.File(self.filename, "r", libver="latest") as f:
                    if all(path in f for path in required_paths):
                        logger.info("All datasets found: %s", self.dataset_path)
                        return
            except OSError:
                pass
            self._stop_event.wait(self.poll_interval)

    def _poll_for_changes(self):
        """Phase 3: Poll loop — detect and report new data points.

        Opens the file fresh on each poll cycle so that a concurrent writer
        can append data between reads.  In production SWMR mode the file would
        stay open with ``dset.refresh()``, but the close-reopen strategy is
        also correct and avoids locking issues in non-SWMR test environments.
        """
        logger.info("Monitoring for changes in %s/%s", self.filename, self.dataset_path)

        last_shape = 0
        labx_name, labz_name, values_name = (
            self.dataset_names[0],
            self.dataset_names[1],
            self.dataset_names[2],
        )
        labx_key = f"{self.dataset_path}/{labx_name}"
        labz_key = f"{self.dataset_path}/{labz_name}"
        values_key = f"{self.dataset_path}/{values_name}"

        while not self._stop_event.is_set():
            try:
                with h5py.File(self.filename, "r", libver="latest") as f:
                    dset_labx = f[labx_key]
                    dset_labz = f[labz_key]
                    dset_values = f[values_key]

                    current_shape = dset_labx.shape[0]

                    if current_shape > last_shape:
                        for i in range(last_shape, current_shape):
                            measurement = NewMeasurementData(
                                labx=float(dset_labx[i]),
                                labz=float(dset_labz[i]),
                                center_value=float(dset_values[i]),
                            )
                            self.callback(measurement)
                        last_shape = current_shape
            except (OSError, KeyError) as exc:
                if not self._stop_event.is_set():
                    logger.debug("Transient error reading HDF5, will retry: %s", exc)
            except Exception:
                if not self._stop_event.is_set():
                    logger.warning("Unexpected error reading HDF5", exc_info=True)

            self._stop_event.wait(self.poll_interval)
