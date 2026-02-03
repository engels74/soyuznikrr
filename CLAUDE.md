# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zondarr is a unified invitation and user management system for media servers (Plex, Jellyfin). It enables administrators to create invitation codes that grant users access to media libraries with configurable permissions, library restrictions, and expiration policies.

## Architecture

**Monorepo Structure:**
- `backend/` - Python 3.14+ Litestar API with msgspec serialization
- `frontend/` - Bun + SvelteKit 2 + Svelte 5 (Runes-only)

**Backend Layering:** Controllers → Services → Repositories → Domain Models (SQLAlchemy)

**Frontend Layering:** SvelteKit routes → Page components → Feature components → Generated API client

**Media Client Abstraction:** Protocol-based interface (`MediaClient`) with platform-specific implementations. Adding new platforms (Emby, Audiobookshelf) requires no core changes.

## Commands

### Backend (from `backend/`)

```bash
uv sync                                    # Install dependencies
uv run granian zondarr.app:app --interface asgi --reload  # Dev server (port 8000)
uv run pytest                              # Run all tests
uv run pytest tests/api/ -k test_name      # Run specific tests
uv run ruff check . --fix                  # Lint with autofix
uv run ruff format .                       # Format
uv run basedpyright                        # Type check
```

### Frontend (from `frontend/`)

```bash
bun install                                # Install dependencies
bun --bun run dev                          # Dev server (port 5173) - MUST use --bun flag
bun --bun run build                        # Production build
bun run check                              # Type check (svelte-check)
bun run test                               # Run tests (Vitest)
bun run generate:api                       # Generate OpenAPI client from backend
```

### Root

```bash
npm install && npm run prepare             # Install pre-commit hooks
npm run lint                               # Run all linters
```

## Tech Stack Details

**Backend:**
- Python 3.14+ with deferred annotations (no `from __future__ import annotations`)
- Litestar 2.15+ framework with class-based controllers
- msgspec Structs for serialization (NOT Pydantic) - 10-80x faster
- SQLAlchemy 2.0 async with explicit eager loading
- Granian server (Rust-based, faster than Uvicorn)
- basedpyright in strict mode

**Frontend:**
- Svelte 5 Runes (`$state`, `$derived`, `$effect`, `$props`) - no legacy `$:` or `export let`
- SvelteKit 2.50+ with file-based routing and route groups
- UnoCSS with presetWind4 + presetShadcn (NOT Tailwind directly)
- shadcn-svelte components (owned code in `$lib/components/ui/`)
- Superforms + Formsnap + Zod for type-safe forms
- openapi-fetch with generated types for API calls

## Key Patterns

**msgspec validation:** Use `Meta` annotations for constraints, validation only occurs during decode:
```python
Email = Annotated[str, Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")]
```

**Svelte 5 reactivity:** Always use Runes, never legacy patterns:
```svelte
let count = $state(0);
let doubled = $derived(count * 2);
let { name }: Props = $props();
```

**API client usage:** Fully typed, no generics needed:
```typescript
const { data, error } = await api.GET('/posts/{id}', { params: { path: { id } } });
```

**Type parameter syntax (Python 3.14):**
```python
class Repository[T, ID = int]:
    async def get(self, id: ID) -> T | None: ...
```

## Database

- **Development:** SQLite (aiosqlite)
- **Production:** PostgreSQL (asyncpg)
- **Migrations:** Alembic (`backend/migrations/`)

## Pre-commit Hooks

Automatically run on commit:
- Trailing whitespace, YAML/JSON/TOML validation
- Ruff (Python lint/format)
- Biome (Frontend lint/format)

Run on push (optional):
- Type checking (basedpyright, svelte-check)
- Tests (pytest, vitest)

## Development Guidelines

Detailed guidelines are in `.augment/rules/`:
- `backend-dev-pro.md` - Python/Litestar/msgspec patterns
- `frontend-dev-pro.md` - Svelte 5/SvelteKit/UnoCSS patterns

Key anti-patterns to avoid:
- Never use lazy loading in async SQLAlchemy contexts
- Never use `$effect` to derive state (use `$derived`)
- Never run `bun run dev` without `--bun` flag (still uses Node.js)
- Never share database sessions across concurrent tasks
