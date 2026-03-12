# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for media servers (Plex and Jellyfin). It's a monorepo with a Python backend, Svelte 5 frontend, and a Python dev CLI.

## Essential Commands

### Development

```bash
# Start both servers (recommended for local dev)
uv run dev_cli start

# Start with options
uv run dev_cli start --skip-auth --backend-only --frontend-only --open-browser

# Stop dev servers
uv run dev_cli stop
```

### Backend (from `/backend`)

```bash
uv sync                              # Install dependencies
uv run pytest                        # Run all tests (parallel by default via -n auto)
uv run pytest tests/test_foo.py      # Run single test file
uv run pytest -k "test_name"         # Run test by name
uv run basedpyright                  # Type checking
```

### Frontend (from `/frontend`)

```bash
bun install                          # Install dependencies
bun run dev                          # Dev server on :5173
bun run build                        # Production build
bun run test                         # Run tests (Vitest)
bun run test -- tests/foo.test.ts    # Run single test file
bun run check                        # svelte-check (TypeScript)
bun run generate:api                 # Regenerate OpenAPI types from running backend
```

### Linting (from root)

```bash
prek run --all-files                 # Lint everything (Ruff + Biome)
prek run                             # Lint staged files only
```

## Architecture

### Backend (`/backend/src/zondarr/`)

Python 3.14+ / Litestar / Granian / msgspec / SQLAlchemy 2.0 async

**Request flow:** Controller → Service → Repository → SQLAlchemy Model

- **`api/`** — Litestar controllers (class-based, one per domain: auth, users, invitations, servers, wizards, settings, etc.)
- **`services/`** — Business logic layer (18 services), injected into controllers via Litestar DI
- **`repositories/`** — Data access layer (12 repos), async SQLAlchemy 2.0 patterns
- **`models/`** — SQLAlchemy ORM models with `TimestampMixin` and `UUIDPrimaryKeyMixin`
- **`media/`** — Media server providers (Plex, Jellyfin) using a registry pattern with protocol-based abstraction
- **`core/`** — Infrastructure: JWT auth, CSRF middleware, async database sessions, background tasks, exception hierarchy
- **`app.py`** — Litestar application factory
- **`config.py`** — Settings from environment variables

**Key patterns:**
- Serialization uses **msgspec** (not Pydantic) — Pydantic is only a transitive dep from jellyfin-sdk
- Auth: JWT tokens + HttpOnly refresh cookies + optional TOTP 2FA
- Database: SQLite (dev) / PostgreSQL (prod) via async drivers
- Migrations: Alembic in `/backend/migrations/`
- Tests: pytest with `asyncio_mode = "auto"` — all async tests auto-detected

### Frontend (`/frontend/src/`)

Svelte 5 (Runes) / SvelteKit 2 / Bun / Vite / UnoCSS / shadcn-svelte

- **`routes/`** — File-based routing with layout groups:
  - `(admin)/` — Authenticated admin pages (dashboard, users, invitations, servers, wizards, settings, logs)
  - `(auth)/` — Login and initial setup
  - `(public)/` — Public join flow (`/join/[code]`)
  - `api/[...path]/` — SvelteKit proxy to backend (avoids CORS in production)
- **`lib/components/`** — Svelte components organized by domain, plus `ui/` for shadcn-svelte primitives
- **`lib/api/`** — Generated OpenAPI client (`types.d.ts` from `bun run generate:api`) + `client.ts` factory using openapi-fetch
- **`lib/schemas/`** — Zod validation schemas
- **`lib/stores/`** — Svelte 5 reactive stores using Runes
- **`lib/server/`** — Server-side utilities
- **`hooks.server.ts`** — Auth middleware and request handling

**Key patterns:**
- Svelte 5 Runes only (`$state`, `$derived`, `$effect`, `$props`) — no legacy Svelte 4 reactivity
- Forms use sveltekit-superforms with Zod validation
- Styling: UnoCSS with presetWind4 + presetShadcn, custom CSS variables (`--cr-*`)
- Icons: @lucide/svelte

### Dev CLI (`/dev_cli/`)

Python CLI that orchestrates both servers for local development. Auto-generates `SECRET_KEY`, sets `CORS_ORIGINS`, manages `BOOTSTRAP_TOKEN_FILE`, and runs preflight checks.

## Code Quality

- **Pre-commit hooks** (via prek): Ruff format/lint (Python), Biome format/lint (frontend)
- **Pre-push hooks**: Type checking (basedpyright + svelte-check) and tests (pytest + vitest)
- **CI** (`.github/workflows/code-quality.yml`): Runs prek hooks, type checking, and full test suite
- **No direct commits to `main`** — enforced by pre-commit hook

## Project Rules

The `.augment/rules/` directory contains detailed coding guidelines that must be followed:
- **`backend-dev-pro.md`** — Python 3.14, Litestar, msgspec, Granian patterns and anti-patterns
- **`frontend-dev-pro.md`** — Svelte 5 Runes, SvelteKit, Bun, UnoCSS patterns and anti-patterns

Read these before making significant changes to either side of the codebase.
