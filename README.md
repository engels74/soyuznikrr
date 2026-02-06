# Zondarr

Unified invitation and user management for Plex and Jellyfin media servers.

## Quick Start

### Backend

```bash
cd backend
uv sync
uv run granian zondarr.app:app --interface asgi --reload
```

### Frontend

```bash
cd frontend
bun install
bun --bun run dev
```

## Tech Stack

**Backend**: Python 3.14+, Litestar, SQLAlchemy, Granian, msgspec

**Frontend**: Bun, SvelteKit, Svelte 5, UnoCSS, shadcn-svelte

**Database**: SQLite (dev) / PostgreSQL (prod)

## Development

```bash
# Backend
cd backend && uv run pytest           # Tests
cd backend && uv run basedpyright     # Type check

# Frontend
cd frontend && bun run test           # Tests
cd frontend && bun run check          # Type check
```

## License

MIT
