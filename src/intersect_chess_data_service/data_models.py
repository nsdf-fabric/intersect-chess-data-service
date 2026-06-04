from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ValueErrorPair(BaseModel):
    """Pair of JSON keys used to average values by their corresponding errors."""

    value_key: str = Field(description="JSON key containing values to average")
    error_key: str = Field(description="JSON key containing errors for value_key")

    @field_validator("value_key", "error_key")
    @classmethod
    def _check_key_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("key must not be empty")
        return v


class MonitoringConfig(BaseModel):
    """Configuration for monitoring CHESS reduced data."""

    filename: str = Field(description="Path to the JSON stream-results or HDF5 file to monitor")
    poll_interval: float = Field(
        default=0.5,
        description="Seconds between poll cycles",
    )
    source_format: Literal["json", "hdf5"] = Field(
        default="json",
        description="Input source format. JSON is the recommended CHESS feedback path.",
    )

    labx_key: str = Field(default="labx", description="JSON key containing lab x values")
    labz_key: str = Field(default="labz", description="JSON key containing lab z values")
    json_value_mode: Literal["single_key", "average_values"] = Field(
        default="single_key",
        description="How JSON target values should be derived from stream-results arrays",
    )
    value_key: str = Field(
        default="0/data/uniform_strain",
        description="JSON key containing the target measurement values",
    )
    value_error_pairs: list[ValueErrorPair] | None = Field(
        default=None,
        description="JSON value/error key pairs used by average_values mode",
    )
    error_threshold: float | None = Field(
        default=None,
        description="Maximum error accepted for values used by average_values mode",
    )
    skip_invalid_values: bool = Field(
        default=True,
        description="Skip JSON rows where coordinates or target values are null or NaN",
    )

    dataset_path: str | None = Field(
        default=None,
        description="HDF5-internal group path, e.g. 'entry/0/uniformfit/2_2_2/centers'",
    )
    dataset_names: list[str] | None = Field(
        default=None,
        description="Dataset names inside the group (x-coord, z-coord, values)",
    )
    swmr: bool = Field(
        default=True,
        description="Open the HDF5 file in SWMR reader mode",
    )

    @model_validator(mode="before")
    @classmethod
    def _infer_legacy_hdf5_config(cls, data):
        """Treat old configs with dataset_path as HDF5 unless source_format is explicit."""
        if isinstance(data, dict) and "source_format" not in data and data.get("dataset_path"):
            data = {**data, "source_format": "hdf5"}
        return data

    @field_validator("dataset_names")
    @classmethod
    def _check_dataset_names_length(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) != 3:
            raise ValueError(f"dataset_names must contain exactly 3 items, got {len(v)}: {v!r}")
        return v

    @field_validator("value_error_pairs")
    @classmethod
    def _check_value_error_pairs_not_empty(
        cls, v: list[ValueErrorPair] | None
    ) -> list[ValueErrorPair] | None:
        if v is not None and not v:
            raise ValueError("value_error_pairs must contain at least one pair")
        return v

    @model_validator(mode="after")
    def _validate_source_format_fields(self):
        if self.source_format == "hdf5":
            if not self.dataset_path:
                raise ValueError("dataset_path is required when source_format is 'hdf5'")
            if self.dataset_names is None:
                self.dataset_names = ["labx", "labz", "values"]
        if self.source_format == "json" and self.json_value_mode == "average_values":
            if not self.value_error_pairs:
                raise ValueError(
                    "value_error_pairs is required when json_value_mode is 'average_values'"
                )
            if self.error_threshold is None:
                raise ValueError(
                    "error_threshold is required when json_value_mode is 'average_values'"
                )
        return self


class NewMeasurementData(BaseModel):
    """A single new measurement detected in a CHESS reduced data source."""

    labx: float
    labz: float
    center_value: float

    def to_dial_payload(self) -> dict:
        """Convert to the format expected by Dial's update_workflow_with_data.

        Returns dict with next_x: [labx, labz] and next_y: center_value,
        matching DialWorkflowDatasetUpdate fields.
        """
        return {
            "next_x": [self.labx, self.labz],
            "next_y": self.center_value,
        }
