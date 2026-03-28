# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for media servers (Plex, Jellyfin). It's a monorepo with a Python backend and SvelteKit frontend. Licensed AGPL-3.0.

## Development Commands

### Dev Server (recommended)

```bash
uv run dev_cli                     # Start both backend + frontend with auto-reload
uv run dev_cli --backend-only      # Backend only (port 8000)
uv run dev_cli --frontend-only     # Frontend only (port 5173)
uv run dev_cli --skip-auth         # Skip auth (inject mock admin user)
uv run dev_cli --skip-checks       # Skip preflight checks
uv run dev_cli stop                # Stop running dev servers
```

The dev CLI auto-installs dependencies, runs Alembic migrations, generates a SECRET_KEY, and configures CORS.

### Backend (from `backend/`)

```bash
uv sync --extra dev                                # Install dependencies
uv run pytest                                      # Run tests (parallel by default via -n auto)
uv run pytest tests/test_totp.py                   # Run single test file
uv run pytest tests/test_totp.py -k test_name      # Run single test
uv run pytest -n0                                  # Run tests without parallelism
uv run basedpyright                                # Type checking
uv run ruff check .                                # Lint
uv run ruff format .                               # Format
uv run alembic upgrade head                        # Run migrations
uv run alembic revision --autogenerate -m "desc"   # Create migration
```

### Frontend (from `frontend/`)

```bash
bun install                        # Install dependencies
bun run dev                        # Dev server
bun run build                      # Production build (svelte-adapter-bun)
bun run test                       # Run tests (vitest)
bun run test -- src/path/file.test.ts  # Run single test file
bun --cwd frontend run check       # svelte-check type checking
```

### Root-level

```bash
bun install                        # Install prek (pre-commit runner)
bun run lint                       # Run all pre-commit hooks
```

### API Type Generation

With the backend running: `bun run --cwd frontend generate:api` generates `frontend/src/lib/api/types.d.ts` from the OpenAPI schema at `http://localhost:8000/docs/openapi.json`.

## Architecture

### Monorepo Layout

```
backend/          Python 3.14, Litestar, SQLAlchemy, Granian ASGI server
  src/zondarr/    Application source (src layout)
  tests/          pytest + hypothesis property-based tests
  migrations/     Alembic database migrations
frontend/         Svelte 5 (Runes), SvelteKit 2, Bun runtime
  src/routes/     SvelteKit file-based routing
  src/lib/        Shared code (api client, components, stores, utils)
dev_cli/          Python dev server orchestrator
```

### Backend Layers (backend/src/zondarr/)

- **`app.py`**: Application factory (`create_app()`) — wires Litestar with DI, middleware, lifespans, exception handlers. `app` module-level instance for Granian deployment.
- **`config.py`**: `Settings` msgspec Struct loaded from environment variables.
- **`api/`**: Litestar Controllers (class-based route handlers) + `schemas.py` (msgspec Structs for request/response DTOs).
- **`services/`**: Business logic layer — orchestrates repositories and external systems.
- **`repositories/`**: Data access layer — generic `Repository[T: Base]` base class (PEP 695 generics) with CRUD operations. All DB errors wrapped in `RepositoryError`.
- **`models/`**: SQLAlchemy 2.0 async models. `Base`, `TimestampMixin`, `UUIDPrimaryKeyMixin` in `models/base.py`.
- **`core/`**: Cross-cutting concerns — database lifecycle (`db_lifespan`, `provide_db_session`), domain exceptions (`ZondarrError` hierarchy), constrained types (`core/types.py`), auth (JWT + TOTP), CSRF middleware, background tasks.
- **`media/`**: Provider plugin system for media servers.

### Media Provider System

Extensible provider architecture in `backend/src/zondarr/media/`:

- **`protocol.py`**: `MediaClient` Protocol — structural subtyping interface for media server clients (connection test, library retrieval, user management).
- **`provider.py`**: `ProviderDescriptor` Protocol — declares metadata, client class, admin auth, join flow, OAuth support, and optional route handlers.
- **`registry.py`**: `ClientRegistry` singleton — stores `ProviderDescriptor` instances keyed by `server_type` string.
- **`providers/`**: Implementations (`plex/`, `jellyfin/`). Each has a client, auth handler, and provider descriptor.
- Registration happens in `providers/__init__.py` via `register_all_providers()`, called at app startup.

### Frontend Architecture

- **Svelte 5 Runes** exclusively (`$state`, `$derived`, `$props`, `$effect`) — no legacy Svelte 4 patterns.
- **Route groups**: `(admin)/` (authenticated), `(auth)/` (login/setup), `(public)/` (join flow).
- **API client**: `src/lib/api/client.ts` uses `openapi-fetch` with types generated from backend OpenAPI schema. Auto-refreshes JWT on 401.
- **Auth flow**: HttpOnly cookies (`zondarr_access_token`, `zondarr_refresh_token`), validated in `hooks.server.ts` (SSR-side).
- **Styling**: UnoCSS with `presetWind4` + `presetShadcn` + `presetIcons`. Component library: shadcn-svelte (owned components in `src/lib/components/ui/`).

### Dependency Injection

Litestar DI via `Provide()` in `create_app()`:
- `session`: async generator yielding `AsyncSession` with auto commit/rollback.
- `settings`: `Settings` from app state.
- Services/repositories are instantiated in controller methods, receiving the injected session.

### Database

- Development: SQLite (`aiosqlite`)
- Production: PostgreSQL (`asyncpg`)
- Migrations use Alembic with `render_as_batch=True` for SQLite ALTER TABLE support.
- The dev CLI auto-runs `alembic upgrade head` on startup.

## Code Conventions

### Backend (Python)

- **Python 3.14** — uses deferred annotations, PEP 695 type parameter syntax (`class Repository[T: Base]`), `type` statement for type aliases.
- **msgspec** for all serialization (not Pydantic). API schemas and Settings are `msgspec.Struct` classes.
- **Positional-only parameters** (`/`) for IDs and credentials in media client methods to prevent keyword leakage in logs.
- **Ruff** for linting and formatting: line-length 88, double quotes, rule sets E4/E7/E9/F/I/B/UP/S/C4/RUF.
- **basedpyright** `recommended` mode for type checking.
- **structlog** for logging.
- Domain exceptions extend `ZondarrError(message, error_code, **context)`.
- Tests use pytest with `pytest-asyncio` (auto mode), `pytest-xdist` (parallel), and `hypothesis` for property-based testing.

### Frontend (TypeScript/Svelte)

- **Biome** for linting and formatting: tabs, single quotes, line width 100.
- **TypeScript strict mode** with `noUncheckedIndexedAccess`.
- **Zod** for client-side schema validation.
- Uses `openapi-fetch` typed client — always regenerate types after API changes.

### Pre-commit (prek)

On commit: trailing-whitespace, end-of-file-fixer, ruff (check + format), biome.
On push: basedpyright, svelte-check, pytest, vitest.
Direct commits to `main` are blocked by the `no-commit-to-branch` hook.
