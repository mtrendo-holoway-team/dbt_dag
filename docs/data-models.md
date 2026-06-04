# Data Models

## DTOs

- `DbtProjectPaths`: resolved dbt project directory, derived `target/manifest.json` path, and profiles directory.
- `DbtRuntimeProfile`: resolved dbt profile name, active target, adapter kind, and project paths.
- `DbtManifestNode`: normalized dbt resource used by the graph and inspectors.
- `NodeRuntimeMetadata`: per-node runtime metadata with execution time, update timestamp, source labels, freshness, border width, and border color.
- `GraphPayload`: graph nodes, including package name, runtime metadata, graph edges, columns, and project summary.
- `GraphStateSnapshot`: thread-safe in-memory graph, manifest, runtime metadata, revision, and refresh timestamp.
- `NodeTaskDTO`: persisted dbt action task state for a node.
- `PartitionDayCellDTO`: one calendar day for partition coverage with `empty`, `half`, or `full` fill level.
- `ModelPartitionCalendarDTO`: per-model partition calendar state, median row count, sync status, stale flag, and month groups.

## Database Tables

### `node_tasks`

Stores subprocess tasks started from node actions.

- `id`: integer primary key.
- `node_id`: manifest unique id.
- `command`: full dbt command.
- `status`: `created`, `running`, `succeeded`, or `failed`.
- `created_at`, `started_at`, `finished_at`: MSK-normalized timestamps.
- `exit_code`: subprocess exit code when finished.
- `logs_excerpt`: bounded stdout/stderr excerpt.

### `manifest_source_state`

Stores the last ingested manifest source state.

- `id`: integer primary key.
- `manifest_path`: resolved manifest path.
- `checksum`: manifest checksum.
- `last_ingested_at`: MSK-normalized timestamp.

### `model_partition_snapshots`

Stores the current local cache of partition row counts for one model.

- `id`: integer primary key.
- `model_unique_id`: manifest unique id for the model.
- `partition_date`: partition date displayed in the inspector calendar.
- `partition_key`: original partition identifier from `stg__dbt_run_partition_info`.
- `row_count`: cached row count for the partition snapshot row.
- `source_inserted_at`: warehouse `inserted_at` for the source snapshot row.
- `synced_at`: MSK-normalized timestamp when the local cache was replaced.

### `model_partition_sync_state`

Stores sync status for the current partition cache of one model.

- `id`: integer primary key.
- `model_unique_id`: manifest unique id for the model.
- `last_source_inserted_at`: newest warehouse `inserted_at` included in the local cache.
- `last_synced_at`: last successful local sync timestamp in MSK.
- `last_checked_at`: last sync attempt timestamp in MSK.
- `sync_status`: `idle`, `running`, `succeeded`, or `failed`.
- `last_error`: last sync error message, if any.
