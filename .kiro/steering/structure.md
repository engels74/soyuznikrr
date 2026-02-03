# Zondarr Project Structure

## Root Layout

```
zondarr/
├── backend/           # Python Litestar API
├── frontend/          # Bun + SvelteKit app
├── docs/              # Documentation
├── .kiro/             # Kiro specs and steering
└── .augment/rules/    # Detailed dev guidelines
```

## Backend Architecture

Layered: Controllers → Services → Repositories → Domain Models

```
backend/
├── src/zondarr/
│   ├── api/           # Litestar controllers (HTTP layer)
│   │   ├── errors.py
│   │   ├── health.py
│   │   ├── invitations.py
│   │   ├── join.py
│   │   ├── plex_oauth.py
│   │   ├── schemas.py
│   │   ├── servers.py
│   │   └── users.py
│   ├── core/          # Shared infrastructure
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── types.py
│   ├── media/         # Media server abstraction
│   │   ├── clients/   # Platform implementations (Plex, Jellyfin)
│   │   ├── protocol.py
│   │   ├── registry.py
│   │   └── types.py
│   ├── models/        # SQLAlchemy domain models
│   │   ├── base.py
│   │   ├── identity.py
│   │   ├── invitation.py
│   │   └── media_server.py
│   ├── repositories/  # Data access layer
│   │   ├── base.py
│   │   ├── identity.py
│   │   ├── invitation.py
│   │   ├── media_server.py
│   │   └── user.py
│   ├── services/      # Business logic
│   │   ├── invitation.py
│   │   ├── media_server.py
│   │   ├── plex_oauth.py
│   │   ├── redemption.py
│   │   ├── sync.py
│   │   └── user.py
│   ├── app.py         # Litestar app factory
│   └── config.py      # Settings
├── tests/
│   ├── property/      # Property-based tests (hypothesis)
│   └── conftest.py
├── migrations/        # Alembic migrations
└── pyproject.toml
```

## Frontend Architecture

Layered: SvelteKit routes → Page components → Feature components → API client

```
frontend/
├── src/
│   ├── lib/
│   │   ├── api/           # OpenAPI client and types
│   │   ├── components/
│   │   │   ├── ui/        # shadcn-svelte components (owned)
│   │   │   ├── invitations/
│   │   │   ├── join/
│   │   │   ├── servers/
│   │   │   └── users/
│   │   ├── schemas/       # Zod validation schemas
│   │   └── stores/        # Svelte 5 reactive state (.svelte.ts)
│   ├── routes/            # SvelteKit file-based routing
│   ├── app.css
│   ├── app.html
│   └── app.d.ts
├── static/
├── svelte.config.js
├── vite.config.ts
└── uno.config.ts
```

## Media Client Abstraction

Protocol-based interface (`MediaClient`) with platform-specific implementations. Adding new platforms (Emby, Audiobookshelf) requires no core changes.

```
media/
├── protocol.py        # MediaClient Protocol definition
├── registry.py        # Client factory/registry
├── types.py           # Shared types
└── clients/
    ├── plex.py        # Plex implementation
    └── jellyfin.py    # Jellyfin implementation
```
