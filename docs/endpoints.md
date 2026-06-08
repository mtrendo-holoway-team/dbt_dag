# Endpoints

## Pages And Partials

- `GET /`: Render the main visualizer page.
- `GET /inspector/project`: Render the project inspector partial when no graph node is selected.
- `GET /inspector/node/{node_id}`: Render the selected node inspector shell partial with tokenized HTMX block placeholders and inline description in the header. Block order is actions, last update, tests, partitions, tasks.
- `GET /inspector/node/{node_id}/last-update`: Render the last update inspector block.
- `GET /inspector/node/{node_id}/tests`: Render the tests inspector block for a model node. The initial response uses `run_results.json`; `?include_warehouse=true` enriches the same block from `stg__dbt_test_runs`.
- `GET /inspector/node/{node_id}/partition`: Render the partition inspector block for a BigQuery model node.
- `GET /inspector/node/{node_id}/actions`: Render the actions inspector block.
- `GET /inspector/node/{node_id}/tasks`: Render the tasks inspector block.
- `GET /static/{file_path}`: Serve source static files and built Vite assets from `static/dist`.

## API

- `GET /api/graph`: Return graph nodes, runtime metadata, edges, group panels, columns, and project summary.
- `GET /api/metadata/revision`: Return the current graph metadata revision and refresh timestamp.
- `GET /search?q=...`: Return model/source/exposure matches for the slash-command overlay search.
- `POST /actions/node/{node_id}/execute/{action_name}`: Stream `dbt build|run|test|compile --select <node>` output as newline-delimited JSON for model nodes only. `compile` includes compiled SQL in the final event payload for clipboard copy.
- `POST /actions/node/{node_id}/refresh-partitions`: Start a background refresh of the local partition snapshot cache for a BigQuery model node and return the updated partition inspector block.
