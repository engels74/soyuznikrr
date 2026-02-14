# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management application for Plex and Jellyfin media servers. It's a full-stack app with a Python backend and Svelte frontend. License: AGPL-3.0.

## Development Commands

### Unified Dev Server (recommended)
```bash
uv run dev_cli                     # Start both backend + frontend
uv run dev_cli --skip-auth         # Skip authentication (requires DEBUG=true)
uv run dev_cli --backend-only      # Backend only
uv run dev_cli --frontend-only     # Frontend only
uv run dev_cli stop                # Stop all running servers
```

### Backend (from `backend/`)
```bash
uv sync                            # Install dependencies
uv run granian zondarr.app:app --interface asgi --reload  # Dev server
uv run pytest                      # Run all tests (parallel by default via -n auto)
uv run pytest tests/test_foo.py    # Run single test file
uv run pytest -k "test_name"       # Run tests matching pattern
uv run ruff check .                # Lint
uv run ruff format .               # Format
uv run basedpyright                # Type check
uv run alembic upgrade head        # Run migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
```

### Frontend (from `frontend/`)
```bash
bun install                        # Install dependencies
bun run dev                        # Vite dev server
bun run build                      # Production build
bun run check                      # svelte-check type checking
bun test                           # Run Vitest tests
bun run test:watch                 # Tests in watch mode
bun run generate:api               # Regenerate TypeScript types from OpenAPI spec
```

### Root Workspace
```bash
bun run lint                       # Run all pre-commit hooks (prek) on all files
bun run lint:staged                # Lint staged files only
```

## Architecture

### Backend (`backend/src/zondarr/`)

**Stack**: Python 3.14, Litestar (ASGI), Granian (Rust server), msgspec (serialization), SQLAlchemy 2.0 (async ORM), structlog

**Layered architecture**: API Controllers → Services → Repositories → Models

- `api/` — Litestar controllers (REST endpoints). Each controller maps to a domain: `auth`, `invitations`, `users`, `servers`, `join`, `oauth`, `wizards`, `health`, `providers`
- `services/` — Business logic layer
- `repositories/` — Data access layer (repository pattern over SQLAlchemy)
- `models/` — SQLAlchemy ORM models
- `core/` — Cross-cutting concerns: `auth.py` (JWT cookie auth), `database.py` (session lifecycle), `tasks.py` (background periodic tasks), `exceptions.py` (domain errors)
- `media/` — Provider abstraction layer for media servers
  - `protocol.py` — Protocol defining the media server interface
  - `registry.py` — Registry for discovering/managing providers
  - `providers/` — Concrete implementations (Plex, Jellyfin)
- `config.py` — Settings via `msgspec.Struct`, loaded from environment variables
- `app.py` — Application factory (`create_app()`) used by both production and tests

**Key patterns**:
- App factory pattern: `create_app(settings=...)` for test overrides
- DI via Litestar's `Provide` with async generator cleanup for DB sessions
- Provider pattern: pluggable media server implementations registered in a registry; providers can contribute route handlers dynamically
- JWT cookie-based auth with optional `--skip-auth` dev mode
- Background lifespan tasks for invitation expiration checks and media server sync
- All models use msgspec Structs for request/response (not Pydantic). Validation constraints via `msgspec.Meta` annotations
- Database: SQLite (dev) / PostgreSQL (prod), migrations via Alembic

### Frontend (`frontend/src/`)

**Stack**: Svelte 5 (Runes), SvelteKit 2, Bun, Vite, UnoCSS (presetWind4 + presetShadcn), shadcn-svelte, openapi-fetch

- `routes/` — File-based routing with route groups:
  - `(admin)/` — Protected admin routes (dashboard, invitations, users, servers, wizards)
  - `(auth)/` — Login and initial setup
  - `(public)/` — Public invitation redemption (`/join`)
- `lib/api/` — Type-safe API client using `openapi-fetch` with auto-generated types from backend's OpenAPI spec
  - `client.ts` — API client instance + typed wrapper functions for all endpoints
  - `types.d.ts` — Auto-generated from `bun run generate:api` (requires backend running)
- `lib/components/` — Reusable components; `ui/` contains shadcn-svelte components
- `lib/schemas/` — Zod validation schemas (used with sveltekit-superforms)
- `lib/stores/` — Reactive stores using `.svelte.ts` files with Runes
- `lib/utils/` — Helper functions

**Key patterns**:
- Svelte 5 Runes exclusively (`$state`, `$derived`, `$effect`, `$props`, `$bindable`) — no legacy `$:` or `export let`
- Snippets instead of slots for component composition
- Forms: sveltekit-superforms + Zod + formsnap for validation
- End-to-end type safety: OpenAPI spec → `openapi-typescript` → `openapi-fetch` client
- `createScopedClient(fetch)` for SvelteKit load functions (passes SvelteKit's fetch for SSR)
- Styling: UnoCSS with Tailwind Wind4 preset + shadcn design system
- Icons: `@lucide/svelte` and UnoCSS icons preset

### Dev CLI (`dev_cli/`)

Custom Python CLI that orchestrates both backend and frontend dev servers. Auto-generates `SECRET_KEY`, sets `CORS_ORIGINS`, manages PID files, and configures environment variables.

## Tech Decisions

- **msgspec over Pydantic**: Zondarr uses msgspec exclusively for serialization. Pydantic is only present as a transitive dependency of jellyfin-sdk.
- **Granian over Uvicorn**: Rust-based ASGI server for better throughput.
- **UnoCSS over Tailwind CSS directly**: Atomic CSS with presetWind4 for Tailwind compatibility plus shadcn and animation presets.
- **Biome for frontend linting/formatting**, Ruff for Python.
- **prek** (modern pre-commit tool) manages git hooks at the root level.
- **basedpyright** for Python type checking (stricter fork of pyright).

## Coding Guidelines

**Before making any changes**, read and follow the coding patterns established in:
- Backend: `.augment/rules/backend-dev-pro.md`
- Frontend: `.augment/rules/frontend-dev-pro.md`

Review these files to ensure consistency with project standards.

## Pre-commit Hooks

On commit: trailing whitespace, EOF fixer, YAML/JSON/TOML checks, Ruff (lint+format), Biome (frontend).
On push: basedpyright, svelte-check, pytest, vitest.

Direct commits to `main` are blocked by pre-commit hook.

## Environment Setup

Copy `.env.example` to `.env`. The `dev_cli` auto-generates `SECRET_KEY` and sets `CORS_ORIGINS` if not present. Key variables: `SECRET_KEY` (required), `DATABASE_URL`, `DEBUG`, `CORS_ORIGINS`, `VITE_API_URL`.
