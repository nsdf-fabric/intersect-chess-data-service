import h5py
import numpy as np
import pytest


@pytest.fixture
def hdf5_dir(tmp_path):
    """Provide a temporary directory for HDF5 test files."""
    return tmp_path


@pytest.fixture
def sample_hdf5(hdf5_dir):
    """Create a minimal HDF5 file mimicking the NEW HDF5 structure.

    Structure: <entry>/<detector_id>/<fit>/<hkl>/centers/{labx, labz, values}
    Each dataset is resizable (maxshape=(None,)) to allow SWMR appends.
    """
    filepath = hdf5_dir / "new_strain_map.nxs"
    entry = "v8-p3-10s-0deg_dataset1_strainanalysis"
    det = "0"
    fit = "uniformfit"
    hkl = "2_2_2"
    base_path = f"{entry}/{det}/{fit}/{hkl}/centers"

    with h5py.File(filepath, "w", libver="latest") as f:
        grp = f.create_group(base_path)
        grp.create_dataset("labx", data=np.array([1.0, 2.0, 3.0]), maxshape=(None,))
        grp.create_dataset("labz", data=np.array([4.0, 5.0, 6.0]), maxshape=(None,))
        grp.create_dataset("values", data=np.array([10.0, 20.0, 30.0]), maxshape=(None,))

    return filepath, base_path


@pytest.fixture
def empty_hdf5(hdf5_dir):
    """Create an HDF5 file with empty (0-length) resizable datasets."""
    filepath = hdf5_dir / "empty_strain_map.nxs"
    entry = "v8-p3-10s-0deg_dataset1_strainanalysis"
    det = "0"
    fit = "uniformfit"
    hkl = "2_2_2"
    base_path = f"{entry}/{det}/{fit}/{hkl}/centers"

    with h5py.File(filepath, "w", libver="latest") as f:
        grp = f.create_group(base_path)
        grp.create_dataset("labx", shape=(0,), maxshape=(None,), dtype="float64")
        grp.create_dataset("labz", shape=(0,), maxshape=(None,), dtype="float64")
        grp.create_dataset("values", shape=(0,), maxshape=(None,), dtype="float64")

    return filepath, base_path
