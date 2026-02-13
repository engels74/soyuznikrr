# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for Plex and Jellyfin media servers. It's a monorepo with a Python backend and SvelteKit frontend.

## Repository Structure

```
backend/           Python backend (Litestar + SQLAlchemy)
frontend/          SvelteKit frontend (Svelte 5 + UnoCSS)
dev_cli/           Dev server launcher (starts both backend + frontend)
biome.json         Root Biome config (delegates to frontend/)
package.json       Root workspace (prek for git hooks/linting)
```

## Development Commands

### Dev CLI (run from repo root)

```bash
uv run dev_cli                      # Start both backend + frontend
uv run dev_cli --backend-only       # Backend only
uv run dev_cli --frontend-only      # Frontend only
uv run dev_cli --backend-port 9000  # Custom backend port
uv run dev_cli --skip-checks        # Skip pre-flight checks
uv run dev_cli stop                 # Stop all running servers
uv run dev_cli stop --force         # Send SIGKILL immediately
```

### Backend (run from `backend/`)

```bash
# Install dependencies (uses uv)
uv sync --dev

# Run dev server with hot reload
uv run granian zondarr.app:app --interface asgi --host 0.0.0.0 --port 8000 --reload

# Run tests (uses pytest-xdist, runs in parallel by default)
uv run pytest

# Run a single test file
uv run pytest tests/property/test_invitation_flow_props.py

# Run tests matching a keyword
uv run pytest -k "test_name_pattern"

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run basedpyright

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

### Frontend (run from `frontend/`)

```bash
# Install dependencies (uses bun)
bun install

# Dev server
bun run dev

# Build
bun run build

# Run tests
bun run test

# Run tests in watch mode
bun run test:watch

# Type check
bun run check

# Regenerate API types from running backend
bun run generate:api
```

### Root-level linting (prek — runs Biome for frontend, ruff for backend)

```bash
bun run lint          # All files
bun run lint:staged   # Staged files only
```

## Backend Architecture

**Framework:** Litestar (async Python web framework) with Granian ASGI server
**Python version:** 3.14+
**Serialization:** msgspec (not Pydantic — Pydantic is only a transitive dep from jellyfin-sdk)

### Layered architecture

```
api/controllers/     → HTTP handlers (Litestar controllers)
services/            → Business logic orchestration
repositories/        → Data access (generic Repository[T] base)
models/              → SQLAlchemy 2.0 ORM models
core/                → Auth (JWT cookies), DB setup, exceptions, middleware
media/               → Provider registry + Plex/Jellyfin clients
config.py            → Settings loaded from env vars (msgspec.Struct)
app.py               → Application factory (create_app)
```

### Key patterns

- **Provider registry:** Media server providers (Plex, Jellyfin) register via `ClientRegistry` and `ProviderDescriptor` protocol. Adding a new provider requires implementing the protocol — routes are collected dynamically.
- **Interaction registry:** Wizard step types (click, timer, tos, text_input, quiz) register handlers for config validation and response validation.
- **Repository pattern:** Generic `Repository[T]` base class using PEP 695 type parameters. Specialized repos add domain-specific queries.
- **JWT auth:** Cookie-based with access/refresh token rotation. Custom `FixedJWTCookieMiddleware` handles both header and cookie extraction.
- **Background tasks:** `BackgroundTaskManager` runs periodic expiration checks and server syncs.
- **Exception handling:** Domain exceptions (`NotFoundError`, `ValidationError`, `ExternalServiceError`, etc.) map to HTTP status codes via global exception handlers. All error responses include correlation IDs.

### Database

- SQLAlchemy 2.0 async with aiosqlite (dev) or asyncpg (prod)
- Alembic for migrations (`backend/migrations/`)
- Default dev DB: `backend/zondarr.db` (SQLite)

### Environment variables

`SECRET_KEY` (required, 32+ chars), `DATABASE_URL`, `HOST`, `PORT`, `DEBUG`, `CORS_ORIGINS`, `SECURE_COOKIES`, `EXPIRATION_CHECK_INTERVAL_SECONDS`, `SYNC_INTERVAL_SECONDS`

## Frontend Architecture

**Framework:** SvelteKit with Svelte 5, deployed via `svelte-adapter-bun`
**Styling:** UnoCSS with shadcn preset (using `bits-ui` components)
**Forms:** sveltekit-superforms + zod validation
**API client:** openapi-fetch with auto-generated types from backend OpenAPI spec

### Route groups

```
(auth)/    → login, setup (unauthenticated)
(admin)/   → dashboard, servers, invitations, users, wizards (authenticated)
(public)/  → join flow (invitation redemption, public-facing)
```

### Key frontend patterns

- **API types:** Generated from backend OpenAPI spec via `bun run generate:api`. Type aliases and wrapper functions live in `$lib/api/client.ts`.
- **Scoped API clients:** SvelteKit load functions use `createScopedClient(fetch)` to pass SvelteKit's fetch for proper cookie forwarding.
- **Error handling:** `withErrorHandling()` wrapper provides consistent toast notifications for API errors.
- **UI components:** shadcn-svelte style in `$lib/components/ui/`, app components alongside their routes or in `$lib/components/`.

## Testing

### Backend tests

Located in `backend/tests/property/`. Primarily property-based tests using Hypothesis. Uses in-memory SQLite with async fixtures. pytest-xdist runs tests in parallel (`-n auto` is in default addopts).

Hypothesis profiles: `default` (15 examples), `ci` (15), `fast` (5), `debug` (100).

### Frontend tests

Co-located with source (`.svelte.test.ts` / `.test.ts`). Uses Vitest + Testing Library + jsdom. Property-based tests use fast-check.

## Code Style

- **Backend:** ruff (line-length 88, double quotes). basedpyright `recommended` mode.
- **Frontend:** Biome (tabs, single quotes, no trailing commas, line-width 100). TypeScript strict mode with `noUncheckedIndexedAccess`.
- Follow the coding guidelines in `.augment/rules/backend-dev-pro.md` (Litestar + msgspec + SQLAlchemy async patterns, Python 3.14 idioms) and `.augment/rules/frontend-dev-pro.md` (Svelte 5 Runes, SvelteKit routing/loading, UnoCSS + shadcn-svelte patterns).
