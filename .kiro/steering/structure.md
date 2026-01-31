# Project Structure

```
backend/
├── src/zondarr/
│   ├── __init__.py
│   ├── app.py                 # Litestar application factory (create_app)
│   ├── config.py              # Settings msgspec.Struct, load_settings()
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py        # Engine creation, session factory, lifespan
│   │   ├── exceptions.py      # ZondarrError hierarchy
│   │   └── types.py           # Shared type aliases
│   │
│   ├── media/
│   │   ├── __init__.py
│   │   ├── protocol.py        # MediaClient Protocol (typing.Protocol)
│   │   ├── registry.py        # ClientRegistry singleton
│   │   ├── types.py           # Capability enum, LibraryInfo, ExternalUser
│   │   ├── exceptions.py      # MediaClientError, UnknownServerTypeError
│   │   └── clients/
│   │       ├── __init__.py
│   │       ├── jellyfin.py    # JellyfinClient (jellyfin-sdk)
│   │       └── plex.py        # PlexClient (python-plexapi + asyncio.to_thread)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py            # Base, TimestampMixin, UUIDPrimaryKeyMixin
│   │   ├── media_server.py    # ServerType enum, MediaServer, Library
│   │   ├── invitation.py      # Invitation, association tables
│   │   └── identity.py        # Identity, User
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py            # Repository[T: Base] generic base
│   │   ├── media_server.py    # MediaServerRepository
│   │   ├── invitation.py      # InvitationRepository
│   │   ├── identity.py        # IdentityRepository
│   │   └── user.py            # UserRepository
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── media_server.py    # MediaServerService
│   │   └── invitation.py      # InvitationService
│   │
│   └── api/
│       ├── __init__.py
│       ├── health.py          # HealthController (/health, /live, /ready)
│       ├── schemas.py         # Request/response msgspec Structs
│       └── errors.py          # Exception handlers, ErrorResponse
│
├── migrations/
│   ├── env.py                 # Alembic async config
│   └── versions/
│       └── 001_initial.py     # Initial schema migration
│
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── unit/                  # Unit tests
│   ├── property/              # Property-based tests (Hypothesis)
│   └── integration/           # Integration tests
│
├── alembic.ini
└── pyproject.toml
```

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (Litestar Controllers)                           │
│  - HTTP request/response handling                           │
│  - Input validation (msgspec)                               │
│  - OpenAPI documentation                                    │
├─────────────────────────────────────────────────────────────┤
│  Service Layer                                              │
│  - Business logic orchestration                             │
│  - Transaction management                                   │
│  - Cross-cutting concerns                                   │
├─────────────────────────────────────────────────────────────┤
│  Repository Layer                                           │
│  - Data access abstraction                                  │
│  - Query building                                           │
│  - Error wrapping (RepositoryError)                         │
├─────────────────────────────────────────────────────────────┤
│  Media Layer                                                │
│  - Protocol-based client abstraction                        │
│  - Registry pattern for client lookup                       │
│  - External media server communication                      │
├─────────────────────────────────────────────────────────────┤
│  Data Layer (SQLAlchemy Models)                             │
│  - Entity definitions                                       │
│  - Relationships                                            │
│  - Database connection management                           │
└─────────────────────────────────────────────────────────────┘
```

Dependencies flow downward only. Upper layers depend on abstractions (protocols) of lower layers.

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Models | Singular PascalCase | `MediaServer`, `User` |
| Tables | Plural snake_case | `media_servers`, `users` |
| Repositories | `{Model}Repository` | `MediaServerRepository` |
| Services | `{Domain}Service` | `InvitationService` |
| Controllers | `{Domain}Controller` | `HealthController` |
| Enums | PascalCase with UPPER values | `ServerType.JELLYFIN` |
| Association tables | `{entity1}_{entity2}` | `invitation_servers` |

## Database Models

| Model | Table | Key Fields |
|-------|-------|------------|
| MediaServer | `media_servers` | id, name, server_type, url, api_key, enabled |
| Library | `libraries` | id, media_server_id, external_id, name, library_type |
| Invitation | `invitations` | id, code, expires_at, max_uses, use_count, enabled |
| Identity | `identities` | id, display_name, email, expires_at, enabled |
| User | `users` | id, identity_id, media_server_id, external_user_id, username |

## Testing Organization

- `tests/unit/` - Specific examples, edge cases, mocked dependencies
- `tests/property/` - Hypothesis property tests (100+ iterations per property)
- `tests/integration/` - Full stack tests, migration tests
