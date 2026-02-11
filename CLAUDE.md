# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for Plex and Jellyfin media servers. It's a monorepo with a Python async backend and a Svelte 5 frontend.

## Development Commands

### Dev Server

```bash
# Start both backend and frontend (from repo root)
uv run python -m dev_cli start

# Start with options
uv run python -m dev_cli start --backend-only --backend-port 8000
uv run python -m dev_cli start --frontend-only --frontend-port 5173
uv run python -m dev_cli stop
```

### Backend (from `backend/`)

```bash
# Run all tests (parallel by default via -n auto in pyproject.toml)
uv run pytest

# Run a single test file
uv run pytest tests/property/test_invitation_props.py

# Run a single test by name
uv run pytest -k "test_invitation_code_length"

# Run with timing info
uv run pytest --durations=20

# Hypothesis profiles: default (15 examples), fast (5), ci (15), debug (100)
uv run pytest --hypothesis-profile=fast

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run basedpyright

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

### Frontend (from `frontend/`)

```bash
npm run dev              # Vite dev server
npm run build            # Production build (Bun adapter)
npm run check            # svelte-check TypeScript validation
npm run test             # Vitest (single run)
npm run test:watch       # Vitest (watch mode)
npm run generate:api     # Regenerate API types from backend OpenAPI spec (backend must be running)
```

### Pre-commit Hooks

The root package.json uses `prek` for pre-commit hooks. Run `npm run lint` from root to execute all hooks manually.

## Architecture

### Backend (`backend/src/zondarr/`)

**Stack:** Litestar, SQLAlchemy 2.0 async, msgspec (not Pydantic), Python 3.14

**Layered architecture:**
- `api/` — Litestar controllers. Handle HTTP, parameter validation, response transformation. Dependencies injected per-handler via `Provide()`.
- `services/` — Business logic and orchestration. Atomicity rule: external media server operations happen before local DB writes (if external fails, local stays unchanged).
- `repositories/` — Generic `Repository[T]` base (PEP 695 type params). Repositories flush, never commit. Session auto-commits/rollbacks via the DI generator in `core/database.py`.
- `models/` — SQLAlchemy 2.0 mapped classes. `UUIDPrimaryKeyMixin` generates UUIDs at flush time (not construction). To batch-insert without flushes, pass explicit `id=uuid4()`.
- `media/` — Protocol-based media clients (`MediaClient` protocol). `ClientRegistry` singleton resolves credentials with env-var-overrides-DB-value per field.
- `core/` — Auth (JWT cookies with a Litestar cookie-parsing fix), background tasks (expiration, sync, token cleanup), exception hierarchy, database lifespan.
- `config.py` — Settings as `msgspec.Struct` with `Meta` constraints. Loaded from env vars.

**Key patterns:**
- Eager loading strategy: `selectinload` for collections, `joined` for single relations (avoids N+1 in async)
- All domain exceptions carry context dicts; error handlers add correlation IDs
- `expire_on_commit=False` on all session factories (required for async SQLAlchemy)
- Alembic migrations in `backend/migrations/`, auto-formatted by ruff via post-write hook

### Frontend (`frontend/src/`)

**Stack:** Svelte 5 (runes, snippets), SvelteKit, UnoCSS (not Tailwind directly), bits-ui, Vite 7

**Structure:**
- `routes/(admin)/` — Authenticated admin pages (dashboard, invitations, users, servers, wizards) with sidebar layout
- `routes/(auth)/` — Login/setup pages with centered card layout
- `routes/(public)/` — Join flow (invitation redemption)
- `lib/api/client.ts` — Type-safe API client via `openapi-fetch`. `createScopedClient(fetch)` for SSR load functions. Types auto-generated from backend OpenAPI spec.
- `lib/api/auth.ts` — Auth endpoints (raw fetch, not OpenAPI-generated)
- `lib/components/ui/` — shadcn-style components built on bits-ui
- `lib/schemas/` — Zod validation schemas for forms
- `hooks.server.ts` — Auth middleware: validates JWT cookie on each request, redirects based on auth state

**Key patterns:**
- Svelte 5 runes (`$state`, `$derived`, `$effect`) instead of stores
- Component composition via snippets, not children props
- UnoCSS with `presetWind4` + `presetShadcn` + custom "Control Room" color tokens (`cr-bg`, `cr-surface`, `cr-accent`, etc.) defined in `app.css`
- Dark mode default, managed by `mode-watcher`
- `withErrorHandling()` wrapper for user-facing API calls with toast notifications
- `VITE_API_URL` env var for backend URL (defaults to same-origin)

### Database Models

```
AdminAccount (auth) → RefreshToken
Identity (user account) → User (per media server)
MediaServer → Library
Invitation → (M2M) MediaServer, Library; → (FK) Wizard (pre/post)
Wizard → WizardStep (ordered, interaction types: click, timer, tos, text_input, quiz)
```

### Test Infrastructure (`backend/tests/`)

- Property-based tests via Hypothesis in `tests/property/`
- `TestDB` class in `conftest.py` reuses engine across Hypothesis examples (truncates tables instead of recreating schema)
- `_TRUNCATE_ORDER` respects FK constraints (children before parents)
- pytest-asyncio with `asyncio_mode = "auto"` — all async tests auto-detected
- pytest-xdist runs tests in parallel by default (`-n auto`)

## Tooling Configuration

- **Backend linting:** ruff (line-length 88, target py314). Rule sets: E4/E7/E9, F, I, B, UP, S, C4, RUF
- **Backend types:** basedpyright in recommended mode
- **Frontend linting:** Biome (configured at repo root `biome.json`, scoped to `frontend/**`)
- **Frontend types:** svelte-check with TypeScript
