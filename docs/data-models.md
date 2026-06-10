# Data Models

## DTOs

- `DbtProjectPaths`: resolved dbt project directory, derived `target/manifest.json` path, and profiles directory.
- `DbtRuntimeProfile`: resolved dbt profile name, active target, adapter kind, and project paths.
- `DbtManifestNode`: normalized dbt resource used by the graph and inspectors.
- `NodeRuntimeMetadata`: per-node runtime metadata with execution time, update timestamp, source labels, freshness buckets (`last_2h`, `last_24h`, `last_48h`, `stale`, `unknown`), logarithmic border width from `1..6` by runtime duration, and fixed `sky-800` border color.
- `GraphPayload`: graph nodes, including package name, normalized dbt tags, node-type badge letter, runtime metadata, graph edges, rounded group panels with member node ids, columns, and project summary.
- `GraphStateSnapshot`: thread-safe in-memory graph, manifest, runtime metadata, revision, and refresh timestamp.
- `NodeTaskDTO`: persisted dbt action task state for a node.
- `ModelTestResultDTO`: one dbt test attached to a model, with the latest known status and execution time.
- `ModelTestSummaryDTO`: per-model aggregate test status used by the inspector and graph node indicator.
- `PartitionDayCellDTO`: one calendar day for partition coverage with `empty`, `half`, or `full` fill level, plus optional per-day `MIN(_dbt_updated_at)` freshness timestamp in MSK.
- `ModelPartitionCalendarDTO`: per-model partition calendar state, median row count, sync status, stale flag, and month groups.
- `GraphPayload`: graph nodes now include a compact `test_indicator` status in addition to runtime metadata.

## Runtime Sources

- Model runtime metadata continues to merge `run_results.json` and warehouse metadata.
- Model test status resolves in two phases:
  - initial inspector and first graph snapshot use the latest available `run_results.json` test metadata;
  - warehouse enrichment uses `stg__dbt_test_runs` and overrides the same test by `test_unique_id`.
- Test existence comes from `manifest.json`, not from warehouse rows.

## `stg__dbt_test_runs`

Current known columns for the warehouse enrichment source:

- `invocation_id`: dbt invocation identifier.
- `run_started_at`: timestamp of the test run start. Used as the last-run timestamp for inspector freshness and ordering.
- `test_unique_id`: dbt unique id of the test.
- `test_name`: dbt test name.
- `model_unique_id`: dbt unique id of the related model.
- `model_name`: model name.
- `status`: dbt test status.
- `failures`: failure count.
- `execution_time`: execution time in seconds.
- `adapter_response`: adapter response text.
- `inserted_at`: warehouse ingestion timestamp.

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
- `partition_updated_at`: optional `MIN(_dbt_updated_at)` timestamp for the underlying table partition, normalized to MSK when the model relation exposes that column.
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
