# AGENTS.md

## Core Rules

- Follow careful coding: state assumptions, avoid silent interpretation, keep changes minimal, and verify claims with concrete checks.
- Implement only fields, endpoints, and behavior documented for the current module.
- Prefer stability over completeness: fewer correct fields are better than broad partial support.
- Use typed Python, `pydantic` or dataclasses for DTOs, and `logging` instead of `print`.
- Keep handwritten Python modules around 400 lines. Split before 500 lines unless the file is generated, a migration, or a dense declarative structure where splitting hurts readability.

## Architecture

- Decompose by domain. Do not mix DTOs, repositories, services, task orchestration, controllers, and integration mapping in one module.
- Put shared DTOs, constants, protocols, and small utilities in `shared` modules.
- Put database access in repositories.
- Put orchestration/use-case logic in services.
- Put integration adapter and mapper logic in dedicated adapter/runtime modules.
- Warehouse connections must come from dbt `profiles.yml` and the active dbt target.
- Do not add separate `.env` credential variables when the same setting belongs in `profiles.yml`.
- Do not configure a concrete manifest file in `.env`; configure the dbt project directory and derive `target/manifest.json`.
- Direct imports from `dbt.adapters.*` are allowed only inside `src/dbt_dag/dbt_runtime`.
- Application code must depend on `WarehouseAdapterProtocol`, not dbt adapter classes.

## Documentation Sync

- When domain models, ORM models, DTOs, or relationships change, update `docs/data-models.md` in the same change.
- When routes, endpoints, controllers, or responsibilities change, update `docs/endpoints.md` in the same change.
- Record architectural, product, and integration decisions in `docs/decisions.md` when they create or change a rule.
- Decision records must include a stable id, creation date, status, context, decision, and implementation consequences.
- Never delete superseded decisions. Add `supersedes` on the new decision and `superseded_by` on the old decision.

## Quality

- Run `make lint` before commit.
- `make lint` must run `autoflake`, `isort`, `black`, `flake8`, and `mypy`.
- Keep all quality stages green without weakening rules.
- Use `black` and `isort` with `profile=google`, `max-line-length=100`.
- Use absolute imports inside the package.
- Do not add functionality only to satisfy a linter. Use behavior-preserving refactoring only.

## Time And Retries

- Normalize timestamps to `MSK`.
- Truncate timestamps to day for daily aggregation.
- Use exponential backoff with jitter for retries.
- Retry `429` and `5xx` responses up to 5 attempts.

## Frontend

- Use Tailwind 4.
- Keep global Tailwind setup in `src/dbt_dag/web/static/css/tailwind.css`.
- Keep shared primitives such as buttons in `src/dbt_dag/web/static/css/components.css`.
- Keep feature-specific Tailwind-only styling in templates, partials, or feature files instead of `components.css`.
