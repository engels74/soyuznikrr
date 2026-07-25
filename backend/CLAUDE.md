# Backend context

## Ownership and lifecycle

- `src/zondarr/api/` owns Litestar controllers and transport schemas;
  `src/zondarr/services/` owns workflows; `src/zondarr/repositories/` owns persistence;
  `src/zondarr/media/providers/` owns Plex/Jellyfin implementations.
- `src/zondarr/app.py:create_app()` is the composition root. Its lifespan order initializes the
  database before bootstrap/log/background-task lifespans, and its middleware order keeps CSRF
  ahead of authentication. Preserve those orderings when adding lifecycle or middleware work.
- Provider implementations are registered centrally by
  `src/zondarr/media/providers/register_all_providers()`. Add providers there rather than
  importing them opportunistically from controllers.

## Database and migrations

- Models inherit the shared `src/zondarr/models/base.py:Base`. Export every new model from
  `src/zondarr/models/__init__.py`; Alembic imports `Base` from that package so an unexported
  model is invisible to autogenerate.
- Alembic is authoritative for schema evolution. Do not add startup `create_all()` schema
  changes; add a migration under `migrations/versions/` and run
  `cd backend && uv run alembic upgrade head`.
- `DATABASE_URL` overrides `alembic.ini`; absent an override, both the app and Alembic use
  `backend/zondarr.db` when commands run from `backend/`.
- SQLite connections enable foreign keys, WAL, and `synchronous=NORMAL` in
  `src/zondarr/core/database.py`. Tests create their own in-memory schema in
  `tests/conftest.py`, so a passing normal test does not prove a migration works; verify schema
  changes by applying the Alembic upgrade.
- The injected request session commits after a successful handler and rolls back on exceptions.
  Service/repository code should not assume a commit has already happened.

## Security-sensitive behavior

- `DEV_SKIP_AUTH` is gated by `DEBUG`; use `uv run dev_cli --skip-auth`, not an isolated env var.
- CSRF is origin-based. Production mutating browser requests are denied when no trusted origin
  exists; server-side requests without `Origin`/`Referer` are intentionally allowed.
- JWT cookie parsing uses `FixedJWTCookieMiddleware` in `src/zondarr/core/auth.py` to work around
  Litestar treating raw cookie values like bearer headers. Do not replace it with the default
  middleware without updating the cookie-auth tests.

## Tests

- Pytest defaults to xdist `-n auto`; append `-n 0` for a deterministic single-case debugging
  run.
- Property tests reuse `tests/conftest.py:TestDB`; call `await db.clean()` at the start of every
  Hypothesis example before accessing its engine or session factory.
