# Intersect Chess Data Service

INTERSECT Data Egress Service for CHESS. Monitors CHESS reduced data sources and
emits INTERSECT events when new measurement data is detected.

## Architecture Role

This service is the **INTERSECT Data Egress Service** in the CHESS autonomous
experiment loop:

1. CHESS publishes reduced stream-results data.
2. **This service** monitors the reduced results for new rows.
3. When new data is detected, it emits an INTERSECT `new_measurement` event
   containing `{labx, labz, center_value}`.
4. The campaign orchestrator routes this data to
   [Dial](../dial) as a `DialWorkflowDatasetUpdate` (`next_x: [labx, labz]`,
   `next_y: center_value`).

JSON stream-results files are the recommended feedback path. HDF5/Nexus support
remains available for older tests, older configs, and visualization-oriented
workflows, but SWMR over Nexus files on NFS is not the preferred live feedback
mechanism.

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

- `start_monitoring(MonitoringConfig)` — Begin monitoring a reduced data source
- `stop_monitoring()` — Stop the current monitoring session
- `status()` — Returns `"Monitoring"` or `"Idle"`

### INTERSECT Events

- `new_measurement` — Emitted when new data is detected. Payload:
  `{"labx": float, "labz": float, "center_value": float}`

## MonitoringConfig

The service supports two input modes:

- `json` — recommended/default CHESS feedback path
- `hdf5` — backward-compatible HDF5/Nexus path

### JSON Mode

JSON stream-results files use a flat dictionary. Coordinates are top-level
arrays:

```text
labx
labz
```

Measurement arrays are stored under flat string keys, for example:

```text
0/data/norm
0/data/uniform_strain
0/data/unconstrained_strain
0/data/unconstrained_strain_stdev
0/uniform_fit/2_2_2/centers/values
0/unconstrained_fit/2_2_2/strains/values
```

Rows line up by index. For row `i`, the service reads
`data[labx_key][i]`, `data[labz_key][i]`, and `data[value_key][i]`.

```json
{
  "source_format": "json",
  "filename": "/path/to/reduced_data.json",
  "labx_key": "labx",
  "labz_key": "labz",
  "value_key": "0/data/uniform_strain",
  "poll_interval": 0.5,
  "skip_invalid_values": true
}
```

### HDF5 Backward Compatibility Mode

```json
{
  "source_format": "hdf5",
  "filename": "/path/to/new_strain_map.nxs",
  "dataset_path": "v8-p3-10s-0deg_dataset1_strainanalysis/0/uniformfit/2_2_2/centers",
  "dataset_names": ["labx", "labz", "values"],
  "poll_interval": 0.5,
  "swmr": false
}
```

Older HDF5 configs that omit `source_format` but include `dataset_path` are
treated as `hdf5` for compatibility.

## Upstream Location Files

This repository only provides the data egress service. The upstream
orchestrator/spec-side service should write fresh location files under the
CHESS `watch_root`; it should not append to an existing location file. For this
experiment, those files should contain two columns:

```text
labx labz
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
