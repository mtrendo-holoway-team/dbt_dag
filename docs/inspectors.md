# Inspectors

## Creating A New Inspector

1. Extend `NodeInspectorContextDTO` with the minimum new field needed by the block.
2. Populate that field in `NodeInspectorContextFactory` behind an explicit `include_<block>` flag.
3. Add `src/dbt_dag/inspectors/<block>.py` with `TEMPLATE_NAME` and `build_template_context(...)`.
4. Add a dedicated template under `src/dbt_dag/web/templates/inspectors/blocks/<block>.html`.
5. Register a page route in `PagesController`.
6. Insert the shell placeholder in `inspectors/shell.html` at the required position.
7. Mark refresh behavior explicitly:
   - `data-inspector-refresh="none"` for static blocks.
   - `data-inspector-refresh="metadata"` for metadata-driven HTMX refresh.
   - custom `data-*` attributes plus client JS for deferred enrichment.
8. Update docs in the same change:
   - `docs/endpoints.md` for the route.
   - `docs/data-models.md` for new DTOs or payload fields.
   - `docs/decisions.md` if the block changes an architectural rule.

## Semantic Status Colors

- `status-dot-passed`: green filled circle. Used for passing tests and normal partition presence.
- `status-dot-stale`: amber filled circle. Used for stale tests and low partition presence.
- `status-dot-failed`: red filled circle. Used for failed tests and critical partition presence.
- `status-dot-missing`: red outline circle. Used when tests are absent or a partition day has no data.

These classes live in `src/dbt_dag/web/static/css/components.css` and should be reused instead of duplicating ad hoc border/background colors in templates or JS.
