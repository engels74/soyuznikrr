# Zondarr Tech Stack

## Architecture

Monorepo with separate backend and frontend applications.

## Backend (`backend/`)

- **Runtime**: Python 3.14+ (use deferred annotations, NOT `from __future__ import annotations`)
- **Framework**: Litestar 2.15+ with class-based controllers
- **Serialization**: msgspec Structs (NOT Pydantic) - 10-80x faster
- **Database**: SQLAlchemy 2.0 async with explicit eager loading
- **Server**: Granian (Rust-based, faster than Uvicorn)
- **Type Checking**: basedpyright in strict mode
- **Testing**: pytest + pytest-asyncio + hypothesis (property-based)

### Backend Commands

```bash
cd backend
uv sync                                    # Install dependencies
uv run granian zondarr.app:app --interface asgi --reload  # Dev server (port 8000)
uv run pytest                              # Run all tests
uv run pytest tests/api/ -k test_name      # Run specific tests
uv run ruff check . --fix                  # Lint with autofix
uv run ruff format .                       # Format
uv run basedpyright                        # Type check
```

## Frontend (`frontend/`)

- **Runtime**: Bun
- **Framework**: SvelteKit 2.50+ with Svelte 5 Runes
- **Styling**: UnoCSS with presetWind4 + presetShadcn (NOT Tailwind directly)
- **Components**: shadcn-svelte (owned code in `$lib/components/ui/`)
- **Forms**: Superforms + Formsnap + Zod
- **API Client**: openapi-fetch with generated types
- **Testing**: Vitest + Testing Library + fast-check (property-based)

### Frontend Commands

```bash
cd frontend
bun install                                # Install dependencies
bun --bun run dev                          # Dev server (port 5173) - MUST use --bun flag
bun --bun run build                        # Production build
bun run check                              # Type check (svelte-check)
bun run test                               # Run tests (Vitest)
bun run generate:api                       # Generate OpenAPI client from backend
```

## Root Commands

```bash
npm install && npm run prepare             # Install pre-commit hooks
npm run lint                               # Run all linters
```

## Database

- **Development**: SQLite (aiosqlite)
- **Production**: PostgreSQL (asyncpg)
- **Migrations**: Alembic (`backend/migrations/`)

## Pre-commit Hooks

Automatically run: trailing whitespace, YAML/JSON/TOML validation, Ruff, Biome

## Critical Anti-Patterns

- Never use lazy loading in async SQLAlchemy contexts
- Never use `$effect` to derive state (use `$derived`)
- Never run `bun run dev` without `--bun` flag
- Never share database sessions across concurrent tasks
- Never use legacy Svelte patterns (`$:`, `export let`, `<slot>`)
