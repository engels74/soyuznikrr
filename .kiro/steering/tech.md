# Tech Stack

## Runtime & Language

- Python 3.14+ (required - uses deferred annotations, PEP 695 type parameter syntax)
- uv for package management and builds (`uv_build` backend)

## Backend Framework

- **Litestar** (>=2.15) - async web framework with class-based controllers
- **Granian** (>=2.6) - Rust-powered ASGI server (41k+ RPS, lower latency than Uvicorn)
- **msgspec** (>=0.19) - high-performance serialization (10-80x faster than Pydantic)
- **structlog** (>=25.0) - structured logging

## Database

- **SQLAlchemy 2.0** - async ORM with `mapped_column` and `Mapped` types
- **Alembic** (>=1.15) - database migrations
- **aiosqlite** (>=0.21) - async SQLite driver (development)
- **asyncpg** (>=0.30) - async PostgreSQL driver (production)

## Media Server SDKs

- **python-plexapi** (>=4.18) - Plex server communication (sync library, wrap with `asyncio.to_thread()`)
- **jellyfin-sdk** (>=0.3) - Modern Jellyfin SDK (Python 3.13+, native async)

## Dev Tools

- **ruff** (>=0.14) - linting and formatting (line-length 88, py314 target)
- **basedpyright** (>=1.29) - type checking (recommended mode)
- **pytest** (>=8.3) + **pytest-asyncio** (>=0.26) - testing with `asyncio_mode = "auto"`
- **hypothesis** (>=6.130) - property-based testing

## Common Commands

```bash
# Install dependencies
uv sync

# Run development server
granian zondarr.app:app --interface asgi --host 0.0.0.0 --port 8000

# Production server (single worker per container, scale via replicas)
granian zondarr.app:app --interface asgi --workers 1 --runtime-mode st --loop uvloop

# Type checking
basedpyright

# Linting and formatting
ruff check .
ruff format .

# Run tests
pytest

# Run migrations
alembic upgrade head
alembic downgrade -1
```

## Key Patterns

### Serialization (msgspec)
- Use `msgspec.Struct` for all request/response models (not Pydantic)
- Use `kw_only=True, forbid_unknown_fields=True` for request structs
- Use `omit_defaults=True` for response structs
- Use `Annotated[T, msgspec.Meta(...)]` for validation constraints

### Type System
- Use `typing.Protocol` for interfaces (structural subtyping, no inheritance)
- Use PEP 695 type parameter syntax: `class Repository[T: Base]`
- Use `Self` type for method chaining and factory methods
- Use positional-only (`/`) and keyword-only (`*`) parameters where appropriate

### Database
- Use async context managers for connection lifecycle
- Use `selectinload` for collections, `joined` for single relations
- Use `expire_on_commit=False` in session factory
- Wrap all repository operations in try/except, raise `RepositoryError`

### Dependency Injection
- Use Litestar's `Provide` system for DI
- Use generator dependencies for session management with auto commit/rollback
- Use lifespan context managers for connection pool management

### Error Handling
- All domain exceptions inherit from `ZondarrError`
- Include `error_code` and context in all exceptions
- Generate correlation IDs for all error responses
- Never expose internal details (stack traces, file paths) in responses
