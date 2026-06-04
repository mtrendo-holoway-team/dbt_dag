# Endpoints

## Pages And Partials

- `GET /`: Render the main visualizer page.
- `GET /inspector/project`: Render the project inspector partial when no graph node is selected.
- `GET /inspector/node/{node_id}`: Render the selected node inspector shell partial with tokenized HTMX block placeholders and inline description in the header.
- `GET /inspector/node/{node_id}/last-update`: Render the last update inspector block.
- `GET /inspector/node/{node_id}/partition`: Render the partition inspector block for a BigQuery model node.
- `GET /inspector/node/{node_id}/actions`: Render the actions inspector block.
- `GET /inspector/node/{node_id}/tasks`: Render the tasks inspector block.
- `GET /static/{file_path}`: Serve source static files and built Vite assets from `static/dist`.

## API

- `GET /api/graph`: Return graph nodes, runtime metadata, edges, columns, and project summary.
- `GET /api/metadata/revision`: Return the current graph metadata revision and refresh timestamp.
- `GET /search?q=...`: Return model/source/exposure matches for the slash-command overlay search.
- `POST /actions/node/{node_id}/build`: Start `dbt build --select <node>` for a node and return the updated tasks inspector block.
- `POST /actions/node/{node_id}/refresh-partitions`: Start a background refresh of the local partition snapshot cache for a BigQuery model node and return the updated partition inspector block.
