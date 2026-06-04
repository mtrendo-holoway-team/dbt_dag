# Endpoints

## Pages And Partials

- `GET /`: Render the main visualizer page.
- `GET /inspector/project`: Render the project inspector partial.
- `GET /inspector/node/{node_id}`: Render the selected node inspector partial.
- `GET /inspector/node/{node_id}/partitions`: Render the partition calendar partial for a BigQuery model node.
- `GET /tasks/node/{node_id}`: Return node task state as JSON.
- `GET /static/{file_path}`: Serve source static files and built Vite assets from `static/dist`.

## API

- `GET /api/graph`: Return graph nodes, runtime metadata, edges, columns, and project summary.
- `GET /api/metadata/revision`: Return the current graph metadata revision and refresh timestamp.
- `GET /search?q=...`: Return model/source/exposure matches for slash search.
- `POST /actions/node/{node_id}/build`: Start `dbt build --select <node>` for a node and return created task state.
- `POST /actions/node/{node_id}/refresh-partitions`: Start a background refresh of the local partition snapshot cache for a BigQuery model node and return the updated partition partial.
