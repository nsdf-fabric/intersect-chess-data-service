from pydantic import BaseModel, Field, field_validator


class MonitoringConfig(BaseModel):
    """Configuration for monitoring an HDF5 dataset via SWMR polling."""

    filename: str = Field(description="Path to the HDF5 file to monitor")
    dataset_path: str = Field(
        description="HDF5-internal group path, e.g. 'entry/0/uniformfit/2_2_2/centers'"
    )
    poll_interval: float = Field(
        default=0.5,
        description="Seconds between SWMR poll cycles",
    )
    dataset_names: list[str] = Field(
        default=["labx", "labz", "values"],
        description="Dataset names inside the group (x-coord, z-coord, values)",
    )

    @field_validator("dataset_names")
    @classmethod
    def _check_dataset_names_length(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError(f"dataset_names must contain exactly 3 items, got {len(v)}: {v!r}")
        return v

    swmr: bool = Field(
        default=True,
        description="Open the HDF5 file in SWMR reader mode",
    )


class NewMeasurementData(BaseModel):
    """A single new measurement detected in the HDF5 file."""

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
