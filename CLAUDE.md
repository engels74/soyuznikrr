# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for Plex and Jellyfin media servers. It's a monorepo with a Python async backend and a Svelte 5 frontend.

## Commands

### Backend (run from `backend/`)

```bash
uv sync                              # Install dependencies
uv run pytest                        # Run all tests (parallel by default via -n auto)
uv run pytest tests/property/test_foo.py  # Run a single test file
uv run pytest -k "test_name"         # Run tests matching a pattern
uv run pytest --durations=20 -n auto # With timing analysis
uv run ruff check --fix .            # Lint (with autofix)
uv run ruff format .                 # Format
uv run basedpyright                  # Type check
```

**Database migrations** (from `backend/`):
```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

**Run dev server**: `granian zondarr.app:app --interface asgi --host 0.0.0.0 --port 8000`

### Frontend (run from `frontend/`)

```bash
bun install                          # Install dependencies
bun run dev                          # Vite dev server (port 5173)
bun run build                        # Production build
bun run test                         # Run Vitest tests
bun run check                        # svelte-check + TypeScript
bunx biome check --write .           # Lint + format
bun run generate:api                 # Regenerate API types from OpenAPI (requires backend running)
```

### Dev CLI (from repo root)

```bash
uv run dev_cli                    # Launch both backend + frontend dev servers
uv run dev_cli --backend-only     # Backend only
uv run dev_cli --frontend-only    # Frontend only
uv run dev_cli stop               # Stop all running dev servers
uv run dev_cli stop --backend-only  # Stop backend only
uv run dev_cli stop --force       # Send SIGKILL immediately
```

## Architecture

### Backend

**Stack**: Litestar, SQLAlchemy 2.0 async, msgspec, Granian, Python 3.14

**Layout** (`backend/src/zondarr/`):
- `app.py` — Litestar app factory (`create_app()`) with DI, lifespans, exception handlers
- `config.py` — Settings via `msgspec.Struct`, loaded from env vars
- `core/database.py` — Engine factory, session provider (auto commit/rollback), lifespan
- `core/tasks.py` — Background task manager (invitation expiry, server sync)
- `models/` — SQLAlchemy 2.0 models using `Mapped`/`mapped_column`, `Base`, `TimestampMixin`, `UUIDPrimaryKeyMixin`
- `repositories/` — Generic `Repository[T: Base]` (PEP 695) with CRUD operations; subclasses per entity
- `api/` — Litestar controllers, `schemas.py` (msgspec request/response types), `errors.py` (exception handlers)
- `services/` — Business logic (sync, wizard interactions)
- `media/clients/` — `MediaClient` ABC with Plex and Jellyfin implementations, registered via `registry.py`

**Key patterns**:
- App factory pattern: `create_app(settings=...)` for testing overrides
- DI via `Provide(provide_db_session)` — sessions auto-commit on success, rollback on exception
- `UUIDPrimaryKeyMixin` uses `default=uuid4` — UUID generated at flush, not construction. Pass `id=uuid4()` explicitly in tests to avoid per-entity flushes
- Domain exceptions (`ValidationError`, `NotFoundError`, `ExternalServiceError`) mapped to HTTP responses
- DB drivers: aiosqlite (dev/test), asyncpg (production)

### Frontend

**Stack**: Svelte 5, SvelteKit 2, UnoCSS (not Tailwind), bits-ui, Bun, Biome

**Layout** (`frontend/src/`):
- `lib/api/client.ts` — Type-safe API wrapper built on `openapi-fetch`; types auto-generated from backend OpenAPI spec
- `lib/components/ui/` — shadcn-svelte pattern components (bits-ui primitives)
- `lib/schemas/` — Zod validation schemas
- `lib/stores/` — Svelte stores for cross-component state
- `routes/(admin)/` — Admin pages (invitations, users, servers, wizards)
- `routes/(public)/join/[code]/` — Public invitation redemption

**Key patterns**:
- Svelte 5 runes (`$state`, `$derived`, `$effect`) for reactivity
- `sveltekit-superforms` + `formsnap` + Zod for type-safe forms
- UnoCSS with shadcn preset — uses Tailwind-compatible utility classes but is NOT Tailwind
- Biome for linting/formatting (replaces ESLint + Prettier); tabs, single quotes, no trailing commas

### Testing

**Backend**: pytest with Hypothesis property-based tests, in-memory SQLite. Tests are in `backend/tests/property/`. The `TestDB` class in `conftest.py` reuses the engine across Hypothesis examples and truncates tables between runs (massive performance gain). Hypothesis default profile: 15 examples, no deadline, no shrink phase.

**Frontend**: Vitest with `@testing-library/svelte` and `fast-check` for property-based tests.

### Pre-commit Hooks

Managed via `prek` (Node-based pre-commit). On commit: trailing whitespace, ruff, biome. On push: basedpyright, svelte-check, pytest, vitest.

## Code Style

- **Backend**: ruff (line-length 88, Python 3.14 target). Rules: E4/E7/E9, F, I, B, UP, S, C4, RUF. `S101`/`S106` allowed in tests.
- **Frontend**: Biome (line-width 100, tabs, single quotes). Svelte files have relaxed rules for unused vars/imports.
- **Type checking**: basedpyright `recommended` mode (backend), strict TypeScript (frontend).
