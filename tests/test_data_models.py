import pytest

from intersect_chess_data_service.data_models import (
    MonitoringConfig,
    NewMeasurementData,
    ValueErrorPair,
)


class TestMonitoringConfig:
    def test_default_config_uses_json(self):
        config = MonitoringConfig(filename="/path/to/reduced_data.json")
        assert config.source_format == "json"
        assert config.labx_key == "labx"
        assert config.labz_key == "labz"
        assert config.json_value_mode == "single_key"
        assert config.value_key == "0/data/uniform_strain"
        assert config.value_error_pairs is None
        assert config.error_threshold is None
        assert config.skip_invalid_values is True
        assert config.dataset_path is None
        assert config.dataset_names is None

    def test_average_values_config(self):
        config = MonitoringConfig(
            filename="/path/to/reduced_data.json",
            json_value_mode="average_values",
            value_error_pairs=[
                {
                    "value_key": "0/data/uniform_strain",
                    "error_key": "0/data/uniform_strain_stdev",
                },
                {
                    "value_key": "0/data/unconstrained_strain",
                    "error_key": "0/custom/unconstrained_error",
                },
            ],
            error_threshold=0.05,
        )
        assert config.json_value_mode == "average_values"
        assert config.value_error_pairs == [
            ValueErrorPair(
                value_key="0/data/uniform_strain",
                error_key="0/data/uniform_strain_stdev",
            ),
            ValueErrorPair(
                value_key="0/data/unconstrained_strain",
                error_key="0/custom/unconstrained_error",
            ),
        ]
        assert config.error_threshold == 0.05

    def test_average_values_requires_value_error_pairs(self):
        with pytest.raises(ValueError, match="value_error_pairs is required"):
            MonitoringConfig(
                filename="/path/to/reduced_data.json",
                json_value_mode="average_values",
                error_threshold=0.05,
            )

    def test_average_values_rejects_empty_entries(self):
        with pytest.raises(ValueError, match="value_error_pairs"):
            MonitoringConfig(
                filename="/path/to/reduced_data.json",
                json_value_mode="average_values",
                value_error_pairs=[],
                error_threshold=0.05,
            )

    def test_average_values_rejects_incomplete_pair(self):
        with pytest.raises(ValueError, match="error_key"):
            MonitoringConfig(
                filename="/path/to/reduced_data.json",
                json_value_mode="average_values",
                value_error_pairs=[{"value_key": "0/data/unconstrained_strain"}],
                error_threshold=0.05,
            )

    def test_average_values_rejects_empty_pair_key(self):
        with pytest.raises(ValueError, match="key must not be empty"):
            MonitoringConfig(
                filename="/path/to/reduced_data.json",
                json_value_mode="average_values",
                value_error_pairs=[{"value_key": "0/data/unconstrained_strain", "error_key": ""}],
                error_threshold=0.05,
            )

    def test_average_values_requires_error_threshold(self):
        with pytest.raises(ValueError, match="error_threshold is required"):
            MonitoringConfig(
                filename="/path/to/reduced_data.json",
                json_value_mode="average_values",
                value_error_pairs=[
                    {
                        "value_key": "0/data/unconstrained_strain",
                        "error_key": "0/data/unconstrained_strain_stdev",
                    }
                ],
            )

    def test_legacy_hdf5_config_is_inferred(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
            poll_interval=0.5,
        )
        assert config.source_format == "hdf5"
        assert config.filename == "/path/to/file.nxs"
        assert config.dataset_path == "entry/0/uniformfit/2_2_2/centers"
        assert config.poll_interval == 0.5

    def test_default_poll_interval(self):
        config = MonitoringConfig(filename="/path/to/reduced_data.json")
        assert config.poll_interval == 0.5

    def test_hdf5_default_dataset_names(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            source_format="hdf5",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        assert config.dataset_names == ["labx", "labz", "values"]

    def test_explicit_hdf5_config(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            source_format="hdf5",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
            dataset_names=["x", "z", "d"],
            swmr=False,
        )
        assert config.source_format == "hdf5"
        assert config.dataset_names == ["x", "z", "d"]
        assert config.swmr is False

    def test_dataset_names_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="exactly 3 items"):
            MonitoringConfig(
                filename="/path/to/file.nxs",
                source_format="hdf5",
                dataset_path="entry/0/uniformfit/2_2_2/centers",
                dataset_names=["labx", "labz"],
            )

    def test_hdf5_requires_dataset_path(self):
        with pytest.raises(ValueError, match="dataset_path is required"):
            MonitoringConfig(filename="/path/to/file.nxs", source_format="hdf5")


class TestNewMeasurementData:
    def test_valid_measurement(self):
        data = NewMeasurementData(labx=1.0, labz=2.0, center_value=3.0)
        assert data.labx == 1.0
        assert data.labz == 2.0
        assert data.center_value == 3.0

    def test_to_dial_update_payload(self):
        """Verify data can be converted to the format Dial expects:
        next_x: [labx, labz], next_y: center_value
        """
        data = NewMeasurementData(labx=-47.33, labz=-242.5, center_value=0.0123)
        payload = data.to_dial_payload()
        assert payload["next_x"] == [-47.33, -242.5]
        assert payload["next_y"] == 0.0123

    def test_negative_values(self):
        data = NewMeasurementData(labx=-47.33, labz=-242.5, center_value=-0.001)
        assert data.labx == -47.33
        assert data.labz == -242.5
        assert data.center_value == -0.001
