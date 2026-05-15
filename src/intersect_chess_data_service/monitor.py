from __future__ import annotations

import json
import logging
import math
import os
import threading
from collections.abc import Sequence
from typing import Callable

import h5py

from .data_models import NewMeasurementData

logger = logging.getLogger(__name__)


def _is_invalid_value(value: object) -> bool:
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


class JSONStreamResultsMonitor:
    """Monitors a flat CHESS reduced JSON stream-results file for new rows."""

    def __init__(
        self,
        filename: str,
        callback: Callable[[NewMeasurementData], None],
        poll_interval: float = 0.5,
        labx_key: str = "labx",
        labz_key: str = "labz",
        value_key: str = "0/data/uniform_strain",
        skip_invalid_values: bool = True,
    ):
        self.filename = filename
        self.callback = callback
        self.poll_interval = poll_interval
        self.labx_key = labx_key
        self.labz_key = labz_key
        self.value_key = value_key
        self.skip_invalid_values = skip_invalid_values
        self._stop_event = threading.Event()

    def stop(self):
        """Signal the monitor to stop."""
        self._stop_event.set()

    def run(self):
        """Main monitoring loop. Blocks until stop() is called."""
        self._wait_for_file()
        if self._stop_event.is_set():
            return

        self._poll_for_changes()

    def _wait_for_file(self):
        """Wait for the JSON file to appear on disk."""
        logger.info("Waiting for JSON file: %s", self.filename)
        while not self._stop_event.is_set():
            if os.path.exists(self.filename):
                logger.info("JSON file detected: %s", self.filename)
                return
            self._stop_event.wait(self.poll_interval)

    def _load_arrays(self) -> tuple[Sequence, Sequence, Sequence] | None:
        try:
            with open(self.filename, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Transient error reading JSON, will retry: %s", exc)
            return None

        try:
            labx = data[self.labx_key]
            labz = data[self.labz_key]
            values = data[self.value_key]
        except KeyError as exc:
            logger.warning("Required JSON key missing while monitoring %s: %s", self.filename, exc)
            return None

        if not all(isinstance(item, list) for item in (labx, labz, values)):
            logger.warning(
                "JSON keys %s, %s, and %s must all contain arrays",
                self.labx_key,
                self.labz_key,
                self.value_key,
            )
            return None

        return labx, labz, values

    def _poll_for_changes(self):
        """Poll the JSON file and emit each newly appended valid row."""
        logger.info(
            "Monitoring JSON results in %s using keys (%s, %s, %s)",
            self.filename,
            self.labx_key,
            self.labz_key,
            self.value_key,
        )

        last_index = 0
        while not self._stop_event.is_set():
            arrays = self._load_arrays()
            if arrays is None:
                self._stop_event.wait(self.poll_interval)
                continue

            labx, labz, values = arrays
            current_len = min(len(labx), len(labz), len(values))

            if current_len > last_index:
                for i in range(last_index, current_len):
                    raw_labx = labx[i]
                    raw_labz = labz[i]
                    raw_value = values[i]

                    if self.skip_invalid_values and (
                        _is_invalid_value(raw_labx)
                        or _is_invalid_value(raw_labz)
                        or _is_invalid_value(raw_value)
                    ):
                        logger.debug("Skipping invalid JSON row %s from %s", i, self.filename)
                        continue

                    try:
                        measurement = NewMeasurementData(
                            labx=float(raw_labx),
                            labz=float(raw_labz),
                            center_value=float(raw_value),
                        )
                    except (TypeError, ValueError) as exc:
                        logger.debug("Skipping non-numeric JSON row %s: %s", i, exc)
                        continue

                    self.callback(measurement)
                last_index = current_len

            self._stop_event.wait(self.poll_interval)


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
        swmr: bool = True,
    ):
        self.filename = filename
        self.dataset_path = dataset_path
        self.callback = callback
        self.poll_interval = poll_interval
        self.dataset_names = dataset_names or ["labx", "labz", "values"]
        if len(self.dataset_names) != 3:
            raise ValueError(
                f"dataset_names must contain exactly 3 items, got {len(self.dataset_names)}: {self.dataset_names!r}"
            )
        self.swmr = swmr
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
                with h5py.File(self.filename, "r", libver="latest", swmr=self.swmr) as f:
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
                with h5py.File(self.filename, "r", libver="latest", swmr=self.swmr) as f:
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
