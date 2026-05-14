# CLAUDE.md

This file provides guidance to AI coding agents when working in this repository.

## Project overview

Zondarr is unified invitation and user management for Plex and Jellyfin media servers. Monorepo with two main apps:

- `backend/` — Python 3.14 + Litestar + msgspec + Granian + SQLAlchemy 2.0 (async) + Alembic. Package name: `zondarr` (`backend/src/zondarr/`).
- `frontend/` — Bun + SvelteKit 2 + Svelte 5 (Runes only) + UnoCSS (`presetWind4` + `presetShadcn`) + shadcn-svelte + `openapi-fetch`.
- `dev_cli/` — Python helper that boots backend + frontend together with shared bootstrap token / port wiring.
- `migrations/` lives at `backend/migrations/` (Alembic, async, `render_as_batch=True` for SQLite).
- Root `package.json` only manages `prek` (the pre-commit runner). Real workspaces live in `backend/` and `frontend/`.

Most changes land in either `backend/src/zondarr/` or `frontend/src/`. Cross-cutting changes that touch HTTP contracts almost always require regenerating frontend API types — see "Task workflows" below.

## Commands

All `uv` commands run from `backend/`. All `bun` commands run from `frontend/` (or use `--cwd frontend` from root).

Install:

```bash
bun install                        # root (installs prek)
bun install --cwd frontend         # frontend deps
uv sync --project backend --all-extras   # backend deps (incl. dev)
```

Run dev (both servers, recommended):

```bash
uv run --project backend dev_cli                 # starts backend:8000 + frontend:5173
uv run --project backend dev_cli --skip-auth     # bypass auth with synthetic admin
uv run --project backend dev_cli stop            # stop both
```

Run individually:

```bash
# Backend
cd backend && uv run granian zondarr.app:app --interface asgi --host 0.0.0.0 --port 8000
# Frontend
bun run --cwd frontend dev
```

Build / check / test / lint:

```bash
# Backend (cd backend first)
uv run pytest                        # all tests
uv run pytest tests/path/to_test.py  # single file
uv run pytest -k test_name           # single test
uv run basedpyright                  # typecheck
uv run ruff check .                  # lint
uv run ruff format .                 # format

# Frontend (from root, or cd frontend)
bun run --cwd frontend test          # vitest --run
bun run --cwd frontend check         # svelte-check (typecheck)
bun run --cwd frontend build         # production build
bunx --bun biome check frontend/     # lint + format (Biome)
bunx --bun biome check --write frontend/   # auto-fix
```

CI-equivalent validation (matches `.github/workflows/code-quality.yml`):

```bash
bun run --cwd frontend test
cd backend && uv run pytest
cd backend && uv run basedpyright
bun run --cwd frontend check
```

Pre-commit gates (installed via `bun run prepare`):

```bash
bun run lint                # prek run --all-files (Biome + Ruff)
bun run lint:staged         # prek run (staged only)
```

Regenerate frontend API types from backend OpenAPI (backend must be running on :8000):

```bash
bun run --cwd frontend generate:api
```

## High-level architecture

### Backend (`backend/src/zondarr/`)

App factory: `app.py::create_app()` returns a `Litestar` instance and is the canonical entry. Granian loads the module-level `app = create_app()`. Layered DI:

- `api/` — Litestar `Controller` classes (one per resource: `auth`, `invitations`, `users`, `servers`, `wizards`, `oauth`, `join`, `providers`, `settings`, `totp`, `logs`, `health`, `dashboard`). Controllers declare `dependencies = {...: Provide(provide_xxx)}` to get services/repositories.
- `services/` — business logic; orchestrates repositories + media clients + external systems. Exported via `services/__init__.py`.
- `repositories/` — data access. Inherit from `Repository[T: Base]` (`repositories/base.py`) for generic CRUD with `RepositoryError` wrapping.
- `models/` — SQLAlchemy 2.0 async models. All inherit `Base`; most also use `TimestampMixin` and `UUIDPrimaryKeyMixin` from `models/base.py`. Register new models in `models/__init__.py` so Alembic autogen sees them.
- `core/` — cross-cutting: `database.py` (async session + lifespan), `auth.py` (JWT), `csrf.py`, `exceptions.py` (domain errors), `tasks.py` (background task manager), `retry.py` (RetryPolicy + circuit breaker), `log_buffer.py`, `types.py` (`msgspec.Meta`-annotated aliases).
- `media/` — media-server plugin system. `protocol.py::MediaClient` is the `Protocol` clients implement; `provider.py::ProviderDescriptor` declares per-provider metadata, auth, OAuth, and route handlers; `registry.py::registry` is the singleton; `providers/{plex,jellyfin}/` are concrete implementations. Register new providers in `media/providers/__init__.py::register_all_providers()`.

App wiring: controllers are listed explicitly in `create_app()`'s `route_handlers`; additional handlers can be contributed by a provider via `ProviderDescriptor.route_handlers`. Lifespans (`db_lifespan`, bootstrap-token, log stream, background tasks) are composed in `create_app()`.

Domain errors (`core/exceptions.py`) — `AuthenticationError`, `ValidationError`, `NotFoundError`, `RedemptionError`, `ExternalServiceError`, `MediaServerUnreachableError`, `RepositoryError` — have matching handlers wired in `create_app()`'s `exception_handlers`. Throwing one of these is the correct way to signal failure from a service/controller.

### Frontend (`frontend/src/`)

- `routes/` uses SvelteKit groups: `(admin)/`, `(auth)/`, `(public)/`, plus `api/`. Each group has its own `+layout.svelte`. `hooks.server.ts` is the auth gate — it resolves the user from `zondarr_access_token` cookie (or `DEV_SKIP_AUTH`), refreshes via `zondarr_refresh_token`, and redirects unauthenticated requests to `/login` and onboarding-required users to `/setup`.
- `lib/api/client.ts` is the typed `openapi-fetch` client (`api.GET("/api/v1/...")`). Types are generated into `lib/api/types.d.ts` — never hand-edit. A response interceptor auto-refreshes on 401 by replaying a cloned request, then bounces to `/login`. Use `createScopedClient(fetch)` inside SvelteKit `load` functions to pass through SvelteKit's `fetch`.
- `lib/components/ui/` — shadcn-svelte components owned in-tree. `lib/components/{join,wizard,setup,dashboard,auth}/` — feature components.
- `lib/stores/*.svelte.ts` — Runes-based stores (e.g. `providers.svelte.ts`).
- `lib/schemas/` — Zod schemas for form validation.
- Styling: UnoCSS classes only (no Tailwind directly); `cr-bg`/`cr-border`/`cr-accent` are theme tokens. shadcn-svelte form bits live in `lib/components/ui/form/`.

### Dev orchestration (`dev_cli/`)

`dev_cli/__main__.py` → `cli.py::run()` → `DevRunner` (`runner.py`) spawns Granian and `bun run dev` as subprocesses, shares a bootstrap-token file at `backend/data/.bootstrap_token`, sets `PUBLIC_API_URL` / `CORS_ORIGINS`, and writes pidfiles. Granian is pinned to `--workers 1 --runtime-mode st` because SQLite write locks contend with multiple workers — do not change this without switching the dev DB to Postgres.

## Task workflows

### Add a new API endpoint

1. Define request/response structs in the controller file (use `msgspec.Struct` and annotated types from `core/types.py`).
2. Add the handler to the appropriate `Controller` in `backend/src/zondarr/api/<resource>.py`; declare any new DI providers under `dependencies`.
3. If the controller is new, register it in `backend/src/zondarr/app.py::create_app()`'s `route_handlers` list.
4. Implement business logic in `services/`, data access in `repositories/`.
5. Run `uv run basedpyright && uv run pytest`.
6. Regenerate frontend types: start the backend, then `bun run --cwd frontend generate:api`.
7. Consume the endpoint via `api.GET/POST/...` in `frontend/src/lib/api/client.ts` callers.

### Add a database migration

1. Add/modify the model under `backend/src/zondarr/models/` and ensure it's exported from `models/__init__.py` (autogen depends on this).
2. From `backend/`, run `uv run alembic revision --autogenerate -m "<slug>"`. The file lands in `backend/migrations/versions/`, named with the timestamp template from `alembic.ini`, and is auto-formatted by `ruff` via the configured post-write hook.
3. Review the generated migration. `render_as_batch=True` is on for SQLite ALTER TABLE support — verify it's correct for PostgreSQL too.
4. Apply: `uv run alembic upgrade head`.

### Add a media-server provider

1. Create `backend/src/zondarr/media/providers/<name>/` with at minimum: a client implementing `media/protocol.py::MediaClient`, an `AdminAuthProvider`, and a `ProviderDescriptor` subclass declaring metadata, `client_class`, `admin_auth`, `join_flow`, and optionally `route_handlers` / `create_oauth_flow_provider`.
2. Register in `media/providers/__init__.py::register_all_providers()`.
3. Capabilities and supported permissions are declared on the client class (`capabilities()`, `supported_permissions()`) — the frontend reads these via `/api/v1/providers` to choose toggles.

### Add a frontend page

1. Place under `src/routes/(admin|auth|public)/<path>/+page.svelte`. Use `+page.ts` for universal load, `+page.server.ts` for server-only load/actions. Auth/onboarding gating is handled centrally by `hooks.server.ts`; add the path to `PUBLIC_PATHS` only if it must be reachable while unauthenticated.
2. Inside `load`, prefer `createScopedClient(fetch)` over the module-level `api` so SvelteKit can hydrate and cookies flow correctly during SSR.
3. Use Runes (`$state`, `$derived`, `$props`, `$effect`) — no Svelte 4 stores or `export let` for new code.

### Add a background job

Wire it into `core/tasks.py::background_tasks_lifespan` (already composed into the app lifespan in `create_app()`). Use `BackgroundTaskManager` rather than ad-hoc `asyncio.create_task` so shutdown is clean.

## Decision tables

| Situation | Use this | Avoid |
| --- | --- | --- |
| Validating a wizard step interaction | `services/interactions/` `InteractionHandler` registry; add a handler class | Inline `if interaction_type == ...` branches in controllers/services |
| Talking to a media server | `registry.create_client_for_server(server)` from `media/registry.py` | Importing `PlexClient` / `JellyfinClient` directly |
| Persisting a new entity | A `Repository[T]` subclass in `repositories/` | Calling `session.add(...)` from controllers/services |
| Calling backend from SvelteKit `load` | `createScopedClient(event.fetch)` from `$lib/api/client` | The module-level `api` (loses SSR cookie/fetch) |
| Calling backend from a component | Module-level `api` from `$lib/api/client` | `globalThis.fetch` to the API base |
| Defining request/response types in Python | `msgspec.Struct` + `Annotated[..., msgspec.Meta(...)]` from `core/types.py` | Pydantic, dataclasses, plain dicts |
| Returning an error from a controller/service | `raise` a domain exception from `core/exceptions.py` | `return {"error": ...}` or raw `HTTPException` |
| Cross-component frontend state | A `lib/stores/*.svelte.ts` Runes store or Context API | Prop-drilling through layouts; module-level `$state` for per-user data |
| Frontend form validation | Zod schema in `lib/schemas/` + shadcn-svelte `Form.*` | Hand-rolled validation in the component |
| Styling | UnoCSS utility classes + theme tokens (`cr-*`) | Raw Tailwind classes, inline styles, or component-level CSS |

## Code patterns and examples

Controller with DI (`api/wizards.py`):

```python
class WizardController(Controller):
    path: str = "/api/v1/wizards"
    tags: Sequence[str] | None = ["Wizards"]
    dependencies: Mapping[str, Provide | AnyCallable] | None = {
        "wizard_repository": Provide(provide_wizard_repository),
        "wizard_service": Provide(provide_wizard_service),
    }
```

Repository (`repositories/base.py`) uses PEP 695 generics and wraps errors:

```python
class Repository[T: Base](ABC):
    @property
    @abstractmethod
    def _model_class(self) -> type[T]: ...

    async def get_by_id(self, id: UUID) -> T | None:
        try:
            return await self.session.get(self._model_class, id)
        except Exception as e:
            raise RepositoryError(..., operation="get_by_id", original=e) from e
```

Settings struct (`config.py`) — pattern for new structs:

```python
class Settings(msgspec.Struct, kw_only=True, forbid_unknown_fields=True):
    port: Annotated[int, msgspec.Meta(ge=1, le=65535)] = 8000
    cors_origins: Annotated[list[str], msgspec.Meta(description="...")] = []
```

Typed API call from Svelte:

```ts
const { data, error } = await api.GET('/api/v1/providers');
if (data) setProviders(data);
```

SvelteKit load with scoped client:

```ts
import { createScopedClient } from '$lib/api/client';
export const load = async ({ fetch }) => {
  const api = createScopedClient(fetch);
  const { data } = await api.GET('/api/v1/users', { params: { query: { limit: 50 } } });
  return { users: data ?? [] };
};
```

## Project-specific rules

- Do not change Granian's `--workers 1 --runtime-mode st` in `dev_cli/runner.py` while the dev DB is SQLite — multiple workers cause write-lock contention.
- Do not hand-edit `frontend/src/lib/api/types.d.ts`; regenerate with `bun run --cwd frontend generate:api` after backend changes.
- Do not write `# noqa` or `# pyright: ignore` to silence type/lint errors unless you also document why on the same line; `app.py` has a single justified `E402` per-file ignore in `pyproject.toml`.
- Do not import concrete provider classes (`PlexClient`, `JellyfinClient`) from controllers/services; go through `registry` so credentials, capabilities, and env-var overrides are applied.
- Do not instantiate database sessions directly; depend on `session: AsyncSession` via Litestar DI (`Provide(provide_db_session)` is wired globally).
- Do not commit to `main` directly — `no-commit-to-branch` pre-commit hook will block it; open a PR.
- Backend targets Python 3.14 with deferred annotations — write `Foo | None`, not `Optional["Foo"]`, and skip forward-reference quoting.
- Frontend is Svelte 5 Runes only: `$state` / `$derived` / `$props` / `$effect`. No `export let`, `$:`, or writable stores in new code.
- Tests are pre-push, not pre-commit — they will run on `git push` via prek hooks, so don't be surprised by the delay.

## References

- `backend/README.md` — backend dev quick-reference.
- `.augment/rules/backend-dev-pro.md` — deep reference for Litestar + msgspec + Granian + basedpyright patterns; consult before non-trivial backend refactors.
- `.augment/rules/frontend-dev-pro.md` — deep reference for Svelte 5 Runes + SvelteKit + UnoCSS + shadcn-svelte; consult before non-trivial frontend refactors or component additions.
- `.github/workflows/code-quality.yml` — source of truth for CI commands; mirror these locally when validating before push.
- `backend/migrations/env.py` and `backend/alembic.ini` — read before authoring or editing migrations.
- `backend/src/zondarr/media/provider.py` and `media/registry.py` — read before adding a new media provider.
- `frontend/src/hooks.server.ts` — read before changing auth/onboarding redirects or adding public routes.
