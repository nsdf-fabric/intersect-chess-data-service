import threading
import time

import h5py
import numpy as np

from chess_data_service.monitor import HDF5DatasetMonitor


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
