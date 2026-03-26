import pytest

from intersect_chess_data_service.data_models import MonitoringConfig, NewMeasurementData


class TestMonitoringConfig:
    def test_valid_config(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
            poll_interval=0.5,
        )
        assert config.filename == "/path/to/file.nxs"
        assert config.dataset_path == "entry/0/uniformfit/2_2_2/centers"
        assert config.poll_interval == 0.5

    def test_default_poll_interval(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        assert config.poll_interval == 0.5

    def test_default_dataset_names(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
        )
        assert config.dataset_names == ["labx", "labz", "values"]

    def test_custom_dataset_names(self):
        config = MonitoringConfig(
            filename="/path/to/file.nxs",
            dataset_path="entry/0/uniformfit/2_2_2/centers",
            dataset_names=["x", "z", "d"],
        )
        assert config.dataset_names == ["x", "z", "d"]

    def test_dataset_names_rejects_wrong_length(self):
        with pytest.raises(ValueError, match="exactly 3 items"):
            MonitoringConfig(
                filename="/path/to/file.nxs",
                dataset_path="entry/0/uniformfit/2_2_2/centers",
                dataset_names=["labx", "labz"],
            )


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
