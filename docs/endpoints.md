# Endpoints

## Pages And Partials

- `GET /`: Render the main visualizer page.
- `GET /inspector/project`: Render the project inspector partial.
- `GET /inspector/node/{node_id}`: Render the selected node inspector partial.
- `GET /tasks/node/{node_id}`: Return node task state as JSON.

## API

- `GET /api/graph`: Return graph nodes, edges, columns, and project summary.
- `GET /search?q=...`: Return model/source/exposure matches for slash search.
- `POST /actions/node/{node_id}/build`: Start `dbt build --select <node>` for a node and return created task state.
