# Intersect Chess Data Service

INTERSECT Data Egress Service for CHESS. Monitors HDF5 files produced by the
[chess-instrument-control-informer](../chess-instrument-control-informer) and
emits INTERSECT events when new measurement data is detected.

## Architecture Role

This service is the **INTERSECT Data Egress Service** in the CHESS autonomous
experiment loop:

1. `chess-instrument-control-informer` creates a NEW HDF5 file from the full
   strain map
2. **This service** monitors the NEW HDF5 file for new data points using
   HDF5 SWMR (Single Writer Multiple Reader) polling
3. When new data is detected, it emits an INTERSECT `new_measurement` event
   containing `{labx, labz, center_value}`
4. The campaign orchestrator routes this data to
   [Dial](../dial) as a `DialWorkflowDatasetUpdate` (`next_x: [labx, labz]`,
   `next_y: center_value`)

## Installation

```bash
uv sync
```

## Usage

### As an INTERSECT Service

```bash
# Start with local config
intersect-chess-data-service --config local-conf.json

# Or with Docker
docker compose up
```

### CLI Usage

The `intersect-chess-data-service` command is installed as a console script:

```bash
# Use the default config file (local-conf.json)
intersect-chess-data-service

# Specify a config file
intersect-chess-data-service --config /path/to/config.json

# Or set via environment variable
export CHESS_DATA_SERVICE_CONFIG_FILE=/path/to/config.json
intersect-chess-data-service
```

### INTERSECT Message Endpoints

- `start_monitoring(MonitoringConfig)` — Begin monitoring an HDF5 file
- `stop_monitoring()` — Stop the current monitoring session
- `status()` — Returns `"Monitoring"` or `"Idle"`

### INTERSECT Events

- `new_measurement` — Emitted when new data is detected. Payload:
  `{"labx": float, "labz": float, "center_value": float}`

### MonitoringConfig

```json
{
  "filename": "/data/new_strain_map.nxs",
  "dataset_path": "v8-p3-10s-0deg_dataset1_strainanalysis/0/uniformfit/2_2_2/centers",
  "poll_interval": 0.5,
  "dataset_names": ["labx", "labz", "values"]
}
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest tests/

# Lint
uv run ruff check --fix
uv run ruff format --check
```

## Docker

```bash
# Build
docker build -t intersect-chess-data-service .

# Run with docker-compose (includes RabbitMQ broker)
docker compose up
```
