# dbt DAG Visualizer

Local dbt project visualizer for `manifest.json` with a Litestar backend, htmx UI, Sigma.js graph rendering, and SQLite persistence.

## Stack

- Backend: Litestar
- Frontend: htmx, Sigma.js, Graphology, Vite, Tailwind 4
- Storage: SQLite, SQLAlchemy, Alembic
- Runtime: dbt project + `profiles.yml`

## Configuration

Copy `.env.example` to `.env` if defaults are not enough.

The app first searches for `dbt_project.yml` in the current directory and parents. If not found, use:

```env
DBT_PROJECT_DIR=/path/to/dbt/project
DBT_PROFILES_DIR=/path/to/.dbt
DBT_TARGET=dev
```

Warehouse credentials are read from dbt `profiles.yml`, not from app-specific env variables.

## Run

```bash
poetry install
npm install
poetry run dbt-dag
```

The local server listens on `http://127.0.0.1:5678`.

## Quality

```bash
poetry run pytest
npm run build
make lint
```
