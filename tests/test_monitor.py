import json
import math
import threading
import time

import h5py
import numpy as np

from intersect_chess_data_service.monitor import HDF5DatasetMonitor, JSONStreamResultsMonitor


def _run_monitor_until(monitor, predicate, timeout=2.0):
    thread = threading.Thread(target=monitor.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        time.sleep(0.05)
    monitor.stop()
    thread.join(timeout=2.0)
    assert not thread.is_alive()


class TestHDF5DatasetMonitorDetectsFileCreation:
    def test_monitor_waits_for_file_then_detects_it(self, hdf5_dir):
        """Monitor should wait for the file to appear on disk."""
        filepath = hdf5_dir / "delayed_file.nxs"
        dataset_path = "entry/0/uniformfit/2_2_2/centers"
        results = []

        def callback(data):
            results.append(data)

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=callback,
            poll_interval=0.1,
            swmr=False,
        )

        # Start monitoring in background thread
        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()

        # Give monitor a moment to start polling
        time.sleep(0.3)

        # Now create the file with data
        with h5py.File(filepath, "w", libver="latest") as f:
            grp = f.create_group(dataset_path)
            grp.create_dataset("labx", data=np.array([1.0]), maxshape=(None,))
            grp.create_dataset("labz", data=np.array([2.0]), maxshape=(None,))
            grp.create_dataset("values", data=np.array([3.0]), maxshape=(None,))

        # Wait for the monitor to detect the data
        time.sleep(1.0)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 1
        assert results[0].labx == 1.0
        assert results[0].labz == 2.0
        assert results[0].center_value == 3.0


class TestHDF5DatasetMonitorDetectsNewData:
    def test_monitor_detects_appended_data(self, sample_hdf5):
        """Monitor should detect when new data is appended to the datasets."""
        filepath, dataset_path = sample_hdf5
        results = []

        def callback(data):
            results.append(data)

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=callback,
            poll_interval=0.1,
            swmr=False,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()

        # Wait for initial data detection (3 existing points)
        time.sleep(0.5)
        initial_count = len(results)

        # Append new data point
        with h5py.File(filepath, "a", libver="latest") as f:
            for ds_name, val in [("labx", 4.0), ("labz", 7.0), ("values", 40.0)]:
                ds = f[f"{dataset_path}/{ds_name}"]
                ds.resize(ds.shape[0] + 1, axis=0)
                ds[-1] = val

        # Wait for monitor to detect the append
        time.sleep(1.0)
        monitor.stop()
        thread.join(timeout=2.0)

        # Should have detected new data beyond the initial
        assert len(results) > initial_count
        # The latest result should be the appended point
        last = results[-1]
        assert last.labx == 4.0
        assert last.labz == 7.0
        assert last.center_value == 40.0


class TestHDF5DatasetMonitorDetectsDatasetCreation:
    def test_monitor_waits_for_dataset_inside_existing_file(self, hdf5_dir):
        """Monitor should wait for the dataset to appear within an existing file."""
        filepath = hdf5_dir / "no_dataset_yet.nxs"
        dataset_path = "entry/0/uniformfit/2_2_2/centers"
        results = []

        # Create file without the target dataset
        with h5py.File(filepath, "w", libver="latest") as f:
            f.create_group("entry/0")

        def callback(data):
            results.append(data)

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=callback,
            poll_interval=0.1,
            swmr=False,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()

        time.sleep(0.3)

        # Now add the datasets
        with h5py.File(filepath, "a", libver="latest") as f:
            grp = f.create_group(dataset_path)
            grp.create_dataset("labx", data=np.array([10.0]), maxshape=(None,))
            grp.create_dataset("labz", data=np.array([20.0]), maxshape=(None,))
            grp.create_dataset("values", data=np.array([30.0]), maxshape=(None,))

        time.sleep(1.0)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 1
        assert results[0].labx == 10.0
        assert results[0].labz == 20.0
        assert results[0].center_value == 30.0

    def test_monitor_waits_for_all_datasets_not_just_first(self, hdf5_dir):
        """Monitor should not proceed until ALL required datasets exist."""
        filepath = hdf5_dir / "staggered_datasets.nxs"
        dataset_path = "entry/0/uniformfit/2_2_2/centers"
        results = []

        def callback(data):
            results.append(data)

        # Create file with only the first dataset (labx)
        with h5py.File(filepath, "w", libver="latest") as f:
            grp = f.create_group(dataset_path)
            grp.create_dataset("labx", data=np.array([1.0]), maxshape=(None,))

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=callback,
            poll_interval=0.1,
            swmr=False,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()

        # Give time for monitor to see labx but still be waiting
        time.sleep(0.5)
        assert len(results) == 0, "Monitor should not emit data before all datasets exist"

        # Now add the remaining datasets
        with h5py.File(filepath, "a", libver="latest") as f:
            grp = f[dataset_path]
            grp.create_dataset("labz", data=np.array([2.0]), maxshape=(None,))
            grp.create_dataset("values", data=np.array([3.0]), maxshape=(None,))

        time.sleep(1.0)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 1
        assert results[0].labx == 1.0
        assert results[0].labz == 2.0
        assert results[0].center_value == 3.0


class TestHDF5DatasetMonitorStopBehavior:
    def test_stop_terminates_monitor(self, sample_hdf5):
        """Monitor.stop() should cause the run loop to exit."""
        filepath, dataset_path = sample_hdf5

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=lambda d: None,
            poll_interval=0.1,
            swmr=False,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        time.sleep(0.3)

        monitor.stop()
        thread.join(timeout=2.0)
        assert not thread.is_alive()


class TestHDF5DatasetMonitorEmptyStart:
    def test_monitor_starts_from_empty_and_detects_first_data(self, empty_hdf5):
        """Monitor should handle initially empty datasets and detect the first append."""
        filepath, dataset_path = empty_hdf5
        results = []

        def callback(data):
            results.append(data)

        monitor = HDF5DatasetMonitor(
            filename=str(filepath),
            dataset_path=dataset_path,
            callback=callback,
            poll_interval=0.1,
            swmr=False,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        time.sleep(0.3)

        # Append first data point to empty datasets
        with h5py.File(filepath, "a", libver="latest") as f:
            for ds_name, val in [("labx", 5.0), ("labz", 15.0), ("values", 50.0)]:
                ds = f[f"{dataset_path}/{ds_name}"]
                ds.resize(1, axis=0)
                ds[0] = val

        time.sleep(1.0)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 1
        assert results[0].labx == 5.0
        assert results[0].labz == 15.0
        assert results[0].center_value == 50.0


class TestJSONStreamResultsMonitor:
    def test_monitor_emits_existing_rows(self, sample_json):
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(sample_json),
            callback=results.append,
            poll_interval=0.1,
        )

        _run_monitor_until(monitor, lambda: len(results) == 3)

        assert [item.labx for item in results] == [1.0, 2.0, 3.0]
        assert [item.labz for item in results] == [4.0, 5.0, 6.0]
        assert [item.center_value for item in results] == [10.0, 20.0, 30.0]

    def test_monitor_waits_for_file_creation(self, tmp_path, sample_json_data):
        filepath = tmp_path / "delayed_reduced_data.json"
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(filepath),
            callback=results.append,
            poll_interval=0.1,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        time.sleep(0.2)
        filepath.write_text(json.dumps(sample_json_data), encoding="utf-8")
        time.sleep(0.5)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 3

    def test_monitor_detects_appended_json_rows(self, sample_json, sample_json_data):
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(sample_json),
            callback=results.append,
            poll_interval=0.1,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        time.sleep(0.4)
        initial_count = len(results)

        updated = {key: list(value) for key, value in sample_json_data.items()}
        for key, value in (
            ("labx", 4.0),
            ("labz", 7.0),
            ("0/data/uniform_strain", 40.0),
            ("0/data/unconstrained_strain", 400.0),
            ("0/data/unconstrained_strain_stdev", 0.4),
            ("0/uniform_fit/2_2_2/centers/values", 69.4),
            ("0/unconstrained_fit/2_2_2/strains/values", 0.004),
        ):
            updated[key].append(value)
        sample_json.write_text(json.dumps(updated), encoding="utf-8")

        time.sleep(0.5)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) > initial_count
        assert results[-1].labx == 4.0
        assert results[-1].labz == 7.0
        assert results[-1].center_value == 40.0

    def test_monitor_uses_configurable_value_key(self, sample_json):
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(sample_json),
            value_key="0/data/unconstrained_strain",
            callback=results.append,
            poll_interval=0.1,
        )

        _run_monitor_until(monitor, lambda: len(results) == 3)

        assert [item.center_value for item in results] == [100.0, 200.0, 300.0]

    def test_monitor_skips_nan_and_null_values(self, tmp_path, sample_json_data):
        filepath = tmp_path / "invalid_values.json"
        data = {key: list(value) for key, value in sample_json_data.items()}
        data["0/data/uniform_strain"] = [10.0, None, float("nan")]
        filepath.write_text(json.dumps(data), encoding="utf-8")
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(filepath),
            callback=results.append,
            poll_interval=0.1,
        )

        _run_monitor_until(monitor, lambda: False, timeout=0.5)

        assert len(results) == 1
        assert results[0].center_value == 10.0
        assert not math.isnan(results[0].center_value)

    def test_monitor_survives_temporarily_malformed_json(self, tmp_path, sample_json_data):
        filepath = tmp_path / "malformed_then_valid.json"
        filepath.write_text('{"labx": [1.0], ', encoding="utf-8")
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(filepath),
            callback=results.append,
            poll_interval=0.1,
        )

        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        time.sleep(0.2)
        filepath.write_text(json.dumps(sample_json_data), encoding="utf-8")
        time.sleep(0.5)
        monitor.stop()
        thread.join(timeout=2.0)

        assert len(results) == 3

    def test_monitor_handles_missing_value_key(self, sample_json_data, tmp_path):
        filepath = tmp_path / "missing_value_key.json"
        data = {
            key: value for key, value in sample_json_data.items() if key != "0/data/uniform_strain"
        }
        filepath.write_text(json.dumps(data), encoding="utf-8")
        results = []
        monitor = JSONStreamResultsMonitor(
            filename=str(filepath),
            callback=results.append,
            poll_interval=0.1,
        )

        _run_monitor_until(monitor, lambda: False, timeout=0.5)

        assert results == []
