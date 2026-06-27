# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Zondarr is unified invitation and user management for Plex and Jellyfin media servers. Monorepo with three parts:

- `backend/` — Python 3.14 + Litestar + msgspec + Granian + SQLAlchemy 2.0 (async) + Alembic. Package `zondarr` at `backend/src/zondarr/`.
- `frontend/` — Bun + SvelteKit 2 + Svelte 5 (Runes only) + UnoCSS (`presetWind4` + `presetShadcn`) + shadcn-svelte + `openapi-fetch`.
- `dev_cli/` — stdlib-only Python launcher that boots backend + frontend together with shared bootstrap-token and port wiring.

Root `package.json` only manages `prek` (the pre-commit runner); the real workspaces are `backend/` and `frontend/`. Migrations live at `backend/migrations/` (Alembic, async, `render_as_batch=True` for SQLite). Most changes land in `backend/src/zondarr/` or `frontend/src/`; changes to HTTP contracts require regenerating frontend API types (see Workflows).

## Commands

`uv` commands run from `backend/`; `bun` commands run from `frontend/` (or use `--cwd frontend` from root).

```bash
# Install
bun install                              # root (prek)
bun install --cwd frontend               # frontend deps
uv sync --project backend --all-extras   # backend deps incl. dev

# Dev servers (both; preflight auto-runs uv sync, alembic upgrade, bun install)
uv run dev_cli                           # backend:8000 + frontend:5173
uv run dev_cli --skip-auth               # inject synthetic admin, bypass auth
uv run dev_cli stop                      # stop both

# Backend (cd backend)
uv run pytest                            # all tests
uv run pytest tests/path/to_test.py      # one file
uv run pytest -k test_name               # one test
uv run basedpyright                      # typecheck
uv run ruff check . && uv run ruff format .   # lint + format

# Frontend (from root or cd frontend)
bun run --cwd frontend test              # vitest --run
bun run --cwd frontend check             # svelte-check (typecheck)
bun run --cwd frontend build             # production build
bunx biome check --write frontend/       # lint + format (Biome)

# Regenerate frontend API types (backend must be running on :8000)
bun run --cwd frontend generate:api
```

Lint everything via prek: `bun run lint` (`prek run --all-files`, runs Biome + Ruff). CI (`.github/workflows/code-quality.yml`) runs prek, then `cd backend && uv run basedpyright`, `bun run --cwd frontend check`, `cd backend && uv run pytest`, and `bun run --cwd frontend test` — mirror these before pushing.

## Architecture

### Backend (`backend/src/zondarr/`)

`app.py::create_app()` builds and returns the `Litestar` app (the canonical entry; Granian loads the module-level `app`). Layered with Litestar DI:

- `api/` — `Controller` classes, one per resource (`auth`, `invitations`, `users`, `servers`, `wizards`, `oauth`, `join`, `providers`, `settings`, `totp`, `logs`, `health`, `dashboard`). Controllers list `dependencies = {...: Provide(provide_xxx)}`. A new controller must be added to `create_app()`'s `route_handlers`.
- `services/` — business logic (e.g. the `interactions/` handler registry); `repositories/` — data access, subclassing `Repository[T: Base]` (`repositories/base.py`).
- `models/` — SQLAlchemy 2.0 async models inheriting `Base` (+ `TimestampMixin`/`UUIDPrimaryKeyMixin` from `models/base.py`). Register new models in `models/__init__.py` so Alembic autogen sees them.
- `core/` — `database.py` (async session + lifespan), `auth.py` (JWT), `csrf.py`, `exceptions.py` (domain errors), `tasks.py` (`BackgroundTaskManager`), `retry.py`, `types.py` (`msgspec.Meta` aliases).
- `media/` — provider plugin system. `protocol.py::MediaClient` is the client `Protocol`; `provider.py::ProviderDescriptor` declares per-provider metadata/auth/OAuth/routes; `registry.py::registry` is the singleton; concrete clients in `media/providers/{plex,jellyfin}/`, registered via `media/providers/__init__.py::register_all_providers()`.

Signal failure by raising a domain exception from `core/exceptions.py` (`AuthenticationError`, `ValidationError`, `NotFoundError`, `RedemptionError`, `ExternalServiceError`, `MediaServerUnreachableError`, `RepositoryError`); each has a handler wired in `create_app()`.

### Frontend (`frontend/src/`)

- `routes/` groups: `(admin)/`, `(auth)/`, `(public)/`, plus `api/`; each group has its own `+layout.svelte`. `hooks.server.ts` is the auth gate — resolves the user from the `zondarr_access_token` cookie (or `DEV_SKIP_AUTH`), refreshes via `zondarr_refresh_token`, and redirects unauthenticated → `/login`, onboarding-required → `/setup`.
- `lib/api/client.ts` — typed `openapi-fetch` client; module-level `api` plus `createScopedClient(fetch)` for SvelteKit `load`. Types are generated into `lib/api/types.d.ts` (never hand-edit). A 401 interceptor auto-refreshes, then bounces to `/login`.
- `lib/components/ui/` — shadcn-svelte (owned in-tree); `lib/stores/*.svelte.ts` — Runes stores; `lib/schemas/` — Zod form schemas. Styling is UnoCSS utility classes + `cr-*` theme tokens only.

### Dev orchestration (`dev_cli/`)

`dev_cli/runner.py::DevRunner` spawns `uv run granian ...` (cwd `backend/`) and `bun run dev` (cwd `frontend/`) as subprocesses, shares `backend/data/.bootstrap_token`, and sets `PUBLIC_API_URL`/`CORS_ORIGINS`. Granian is pinned to `--workers 1 --runtime-mode st` because SQLite write locks contend with multiple workers.

## Workflows

**Add an API endpoint:** define request/response `msgspec.Struct`s in the controller → add the handler to `api/<resource>.py` (declare new DI providers under `dependencies`) → if the controller is new, add it to `app.py::create_app()` `route_handlers` → implement logic in `services/`, data access in `repositories/` → `cd backend && uv run basedpyright && uv run pytest` → start the backend and run `bun run --cwd frontend generate:api` → consume via `api.GET/POST(...)`.

**Add a migration:** edit/add the model and export it from `models/__init__.py` → from `backend/`, `uv run alembic revision --autogenerate -m "<slug>"` (lands in `backend/migrations/versions/`) → review (`render_as_batch=True` is on for SQLite) → `uv run alembic upgrade head`.

**Add a media provider:** create `media/providers/<name>/` with a client implementing `MediaClient`, an `AdminAuthProvider`, and a `ProviderDescriptor` → register in `media/providers/__init__.py::register_all_providers()`. Capabilities/permissions are declared on the client class and surfaced to the frontend via `/api/v1/providers`.

**Add a frontend page:** place under `src/routes/(admin|auth|public)/<path>/+page.svelte` (`+page.ts` for universal load, `+page.server.ts` for server load/actions). Gating is central in `hooks.server.ts`; add the path to `PUBLIC_PATHS` only if it must be reachable while unauthenticated. In `load`, use `createScopedClient(fetch)` so cookies flow during SSR.

## Decision guide

| Task | Use | Avoid |
|---|---|---|
| Talk to a media server | `registry.create_client_for_server(...)` (`media/registry.py`) | Importing `PlexClient`/`JellyfinClient` directly |
| Persist an entity | a `Repository[T]` subclass | `session.add(...)` from a controller/service |
| Backend call in SvelteKit `load` | `createScopedClient(event.fetch)` | module-level `api` (loses SSR cookies) |
| Request/response types in Python | `msgspec.Struct` + `Annotated[..., msgspec.Meta(...)]` | Pydantic, dataclasses, dicts |
| Return an error | `raise` a `core/exceptions.py` domain error | `return {"error": ...}` / raw `HTTPException` |
| Frontend form validation | Zod schema in `lib/schemas/` + shadcn `Form.*` | hand-rolled validation |

## Code patterns

Repository base uses PEP 695 generics and wraps errors (`repositories/base.py`):

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

SvelteKit `load` with the scoped client (so SSR cookies/fetch flow):

```ts
import { createScopedClient } from '$lib/api/client';
export const load = async ({ fetch }) => {
  const api = createScopedClient(fetch);
  const { data } = await api.GET('/api/v1/users', { params: { query: { limit: 50 } } });
  return { users: data ?? [] };
};
```

## Repository-specific rules

- Keep Granian at `--workers 1 --runtime-mode st` in `dev_cli/runner.py` while the dev DB is SQLite — more workers cause write-lock contention.
- Never hand-edit `frontend/src/lib/api/types.d.ts`; regenerate with `bun run --cwd frontend generate:api` after backend contract changes.
- Reach media servers through `registry` (`media/registry.py`), not by importing `PlexClient`/`JellyfinClient`, so credentials, capabilities, and env overrides apply.
- Get DB sessions via Litestar DI (`session: AsyncSession`); do not instantiate sessions directly.
- Backend is Python 3.14 with deferred annotations — write `Foo | None`, not `Optional["Foo"]`, and skip forward-reference quoting. Frontend is Svelte 5 Runes only (`$state`/`$derived`/`$props`/`$effect`) — no `export let`, `$:`, or writable stores in new code.
- Do not `git commit` to `main` (the `no-commit-to-branch` prek hook blocks it); open a PR. Commit messages must follow Conventional Commits (`conventional-pre-commit`).
- Only add `# noqa`/`# pyright: ignore` with an inline reason; the one sanctioned exception is the `E402` per-file ignore for `app.py` in `backend/pyproject.toml`.
- Backend tests and type checks run at `pre-push` (prek), not pre-commit — expect a delay on `git push`.

## References

- `.augment/rules/backend-dev-pro.md` — Litestar + msgspec + Granian + basedpyright patterns; read before non-trivial backend refactors.
- `.augment/rules/frontend-dev-pro.md` — Svelte 5 Runes + SvelteKit + UnoCSS + shadcn-svelte; read before non-trivial frontend work.
- `.github/workflows/code-quality.yml` — source of truth for CI commands.
- `prek.toml` — pre-commit / pre-push hook definitions.
- `backend/migrations/env.py`, `backend/alembic.ini` — read before authoring or editing migrations.
- `backend/src/zondarr/media/provider.py`, `media/registry.py` — read before adding a media provider.
- `frontend/src/hooks.server.ts` — read before changing auth/onboarding redirects or public routes.
