---
type: "agent_requested"
description: "Modern Python API Development: Litestar + Granian + msgspec"
---

# Modern Python API Development: Litestar + Granian + msgspec

Building high-performance APIs in 2025/2026 requires embracing Python 3.14's transformative features alongside Litestar's elegant architecture, msgspec's blazing serialization, and Granian's Rust-powered serving. This guide delivers bleeding-edge patterns that fully leverage this stack—**no legacy workarounds, no backwards compatibility cruft**.

The combination of these technologies delivers **10-80x faster serialization** than Pydantic, **2-3x better throughput** than Uvicorn, and enables true multi-core parallelism through free-threaded Python. Every pattern here targets production readiness with type safety and excellent OpenAPI generation.

---

## Python 3.14 features that change everything

Python 3.14 (October 2025) introduced capabilities that fundamentally reshape API development. The most impactful for web APIs are **deferred annotation evaluation**, **free-threaded builds**, **template strings**, and the **new type parameter syntax**.

### Deferred annotations eliminate forward reference pain

Before 3.14, circular type references required ugly string quotes. PEP 649/749 changed this:

```python
# Python 3.14+ - No quotes needed for forward references
class User(msgspec.Struct):
    manager: User | None = None  # Just works!
    reports: list[User] = []

class Response[T](msgspec.Struct):  # PEP 695 generic syntax
    data: T
    success: bool = True
```

The new `annotationlib` module provides introspection tools:

```python
from annotationlib import get_annotations, Format

# Runtime inspection with different formats
get_annotations(User, format=Format.VALUE)       # Resolved types
get_annotations(User, format=Format.FORWARDREF)  # Proxy objects for undefined
get_annotations(User, format=Format.STRING)      # Source text
```

**Migration:** Remove `from __future__ import annotations`—it now emits `DeprecationWarning`.

### Free-threading unlocks true parallelism

PEP 703/779 delivers **official support** for GIL-free builds in 3.14. Single-threaded performance penalty dropped to **5-10%** (from ~40% in 3.13), while CPU-bound handlers gain **2-3x speedup** across cores:

```python
import sys
# Check runtime mode
if not sys._is_gil_enabled():
    print("Running free-threaded!")
```

For API servers, this means CPU-intensive request handlers (data processing, cryptographic operations, ML inference) no longer serialize across threads. Granian's architecture pairs exceptionally well—its Rust runtime handles I/O while Python threads process requests in parallel.

**Threading guidance in the no-GIL world:**

| Task Type | GIL-Enabled | Free-Threaded |
|-----------|-------------|---------------|
| I/O-bound, many connections | asyncio (best) | asyncio (best) |
| CPU-bound | multiprocessing | **threading (preferred)** |
| Mixed I/O + CPU | multiprocessing | threading + asyncio |

**Adopt now if:** Dependencies support free-threading, CPU-bound threading benefits needed.
**Wait if:** Production stability required, dependencies incompatible. Check: https://py-free-threading.github.io/tracking/

### Type parameter syntax for cleaner generics

PEP 695 (3.12+) with PEP 696 defaults (3.13+) eliminates verbose `TypeVar` declarations:

```python
# Modern generic patterns
class Repository[T, ID = int]:  # Type parameter with default
    async def get(self, id: ID) -> T | None: ...
    async def list(self) -> list[T]: ...

class APIResponse[T](msgspec.Struct):
    data: T
    meta: dict[str, str] = {}

# Usage - type inference works naturally
async def get_users() -> APIResponse[list[User]]:
    users = await repo.list()
    return APIResponse(data=users)
```

### Template strings prevent injection attacks

PEP 750's t-strings return structured `Template` objects instead of strings—ideal for safe SQL query building:

```python
from string.templatelib import Template, Interpolation

def safe_query(template: Template) -> tuple[str, list]:
    sql_parts, params = [], []
    for item in template:
        if isinstance(item, str):
            sql_parts.append(item)
        else:  # Interpolation - parameterize it
            sql_parts.append("$" + str(len(params) + 1))
            params.append(item.value)
    return "".join(sql_parts), params

# Usage - injection-safe by construction
user_input = "Robert'); DROP TABLE users;--"
sql, params = safe_query(t"SELECT * FROM users WHERE name = {user_input}")
# sql: "SELECT * FROM users WHERE name = $1"
# params: ["Robert'); DROP TABLE users;--"]
```

Use t-strings when intercepting/validating interpolated values; use f-strings for immediate output.

### Additional 3.14 syntax improvements

**Bracketless except** (PEP 758)—omit parentheses without `as`:
```python
try:
    connect()
except TimeoutError, ConnectionRefusedError:  # Cleaner
    handle_network_error()
```

**Control flow in finally warns** (PEP 765)—avoid `return`/`break`/`continue` in finally blocks:
```python
# Anti-pattern (now warns, will become error)
def risky():
    try:
        return do_something()
    finally:
        return None  # SyntaxWarning: silently suppresses exceptions!
```

**Improved error messages** suggest typo corrections:
```python
>>> "Hello".split(max_split=1)
TypeError: split() got unexpected keyword argument 'max_split'. Did you mean 'maxsplit'?
```

### Performance improvements

**JIT compiler** (experimental): Enable with `PYTHON_JIT=1` for compute-intensive code. Currently 2-9% faster for tight loops. Not available with free-threaded builds.

**Incremental GC**: Reduced from 3 to 2 generations. Maximum pause times reduced by **an order of magnitude** for larger heaps. No action needed—automatic.

---

## Type system patterns

### TypeIs provides intuitive type narrowing

Prefer `TypeIs` over `TypeGuard`—it narrows in **both** `if` and `else` branches:

```python
from typing import TypeIs

def is_str(val: object) -> TypeIs[str]:
    return isinstance(val, str)

def process(val: int | str) -> None:
    if is_str(val):
        print(val.upper())  # val is str
    else:
        print(val + 1)      # val is int ← TypeIs enables this!
```

Reserve `TypeGuard` only for non-subtype narrowing (invariant containers).

### Self type simplifies method chaining

```python
from typing import Self

class Shape:
    def set_scale(self, scale: float) -> Self:
        self.scale = scale
        return self

    @classmethod
    def create(cls) -> Self:
        return cls()

class Circle(Shape): ...
reveal_type(Circle().set_scale(1.0))  # Circle, not Shape!
```

### @override catches inheritance bugs

```python
from typing import override

class Parent:
    def foo(self, x: int) -> int:
        return x

class Child(Parent):
    @override
    def foo(self, x: int) -> int:  # ✅ Verified
        return x + 1

    @override
    def bar(self) -> None: ...  # ❌ Error: bar doesn't exist in Parent
```

### Protocol for structural subtyping

Use `Protocol` for interfaces without inheritance requirements:

```python
from typing import Protocol

class SupportsClose(Protocol):
    def close(self) -> None: ...

class Resource:  # No inheritance needed
    def close(self) -> None:
        self.cleanup()

def close_all(items: Iterable[SupportsClose]) -> None:
    for item in items:
        item.close()
```

### TypedDict with Required/NotRequired

```python
from typing import TypedDict, Required, NotRequired, ReadOnly

class Movie(TypedDict):
    title: Required[str]
    year: NotRequired[int]
    rating: ReadOnly[float]  # 3.13+ immutable key

# Closed TypedDict (3.14+) - no extra keys allowed
class StrictConfig(TypedDict, closed=True):
    host: str
    port: int
```

---

## Litestar application architecture

Litestar promotes **class-based controllers** for organized, testable APIs while maintaining flexibility for standalone handlers. Its layered architecture—where configuration cascades from app through routers to controllers to handlers—eliminates boilerplate while preserving fine-grained control.

### Controller-based route organization

Controllers group related endpoints with shared dependencies, guards, and middleware:

```python
from litestar import Controller, Litestar, Router, get, post, patch, delete
from litestar.di import Provide
from litestar.params import Parameter
from typing import Annotated
from uuid import UUID
import msgspec

class User(msgspec.Struct):
    id: UUID
    name: str
    email: str

class UserCreate(msgspec.Struct, kw_only=True):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]
    email: Annotated[str, msgspec.Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")]

class UserController(Controller):
    path = "/users"
    tags = ["Users"]

    @get("/")
    async def list_users(self, user_service: UserService) -> list[User]:
        return await user_service.list_all()

    @post("/", status_code=201)
    async def create_user(self, data: UserCreate, user_service: UserService) -> User:
        return await user_service.create(data)

    @get("/{user_id:uuid}")
    async def get_user(
        self,
        user_id: Annotated[UUID, Parameter(description="User's unique identifier")],
        user_service: UserService,
    ) -> User:
        return await user_service.get_or_raise(user_id)

    @delete("/{user_id:uuid}", status_code=204)
    async def delete_user(self, user_id: UUID, user_service: UserService) -> None:
        await user_service.delete(user_id)
```

### Dependency injection with lifecycle management

Litestar's DI system uses `Provide` with automatic scope inference. Generator dependencies enable clean resource management:

```python
from litestar import Litestar
from litestar.di import Provide
from litestar.datastructures import State
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from contextlib import asynccontextmanager

# Lifespan context manages long-lived resources
@asynccontextmanager
async def db_lifespan(app: Litestar):
    engine = create_async_engine(settings.database_url, pool_size=20)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield
    await engine.dispose()

# Generator dependency with automatic cleanup
async def provide_db_session(state: State) -> AsyncGenerator[AsyncSession, None]:
    async with state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Services compose dependencies
async def provide_user_service(session: AsyncSession) -> UserService:
    return UserService(session)

app = Litestar(
    route_handlers=[UserController],
    lifespan=[db_lifespan],
    dependencies={
        "session": Provide(provide_db_session),
        "user_service": Provide(provide_user_service),
    },
)
```

### Sync handlers require explicit configuration

Unlike FastAPI's implicit thread pool, Litestar requires explicit `sync_to_thread` for blocking operations:

```python
from litestar import get

# Async handler - preferred for I/O operations
@get("/async")
async def async_handler() -> dict:
    result = await fetch_from_database()
    return {"data": result}

# Sync with blocking I/O - runs in thread pool
@get("/sync-io", sync_to_thread=True)
def sync_blocking_handler() -> dict:
    result = blocking_file_operation()  # Won't block event loop
    return {"data": result}

# Sync without I/O - runs directly (faster)
@get("/sync-fast", sync_to_thread=False)
def sync_computation() -> dict:
    return {"result": compute_quickly()}
```

---

## msgspec for high-performance serialization

msgspec is **10-80x faster** than Pydantic with **5-60x faster** struct creation. Litestar uses it internally, making msgspec.Struct the natural choice for request/response models.

### Struct definitions with validation constraints

```python
import msgspec
from msgspec import Struct, Meta, field, UNSET, UnsetType
from typing import Annotated
from uuid import UUID
from datetime import datetime

# Reusable constrained types
PositiveInt = Annotated[int, Meta(gt=0)]
Email = Annotated[str, Meta(pattern=r"^[\w.-]+@[\w.-]+\.\w+$", max_length=255)]
Username = Annotated[str, Meta(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_]*$")]

class UserCreate(Struct, kw_only=True, forbid_unknown_fields=True):
    """Request model with strict parsing."""
    username: Username
    email: Email
    age: Annotated[int, Meta(ge=18, le=120)]

class User(Struct, omit_defaults=True):
    """Response model with minimal serialization."""
    id: UUID
    username: str
    email: str
    created_at: datetime
    bio: str | None = None  # Omitted from JSON when None

class UserPatch(Struct, kw_only=True):
    """Partial update with UNSET distinction."""
    username: str | UnsetType = UNSET  # Distinguishes "not provided" from null
    email: str | UnsetType = UNSET
    bio: str | None | UnsetType = UNSET

# In handler - detect which fields were actually sent
@patch("/users/{user_id}")
async def update_user(user_id: UUID, data: UserPatch) -> User:
    updates = {}
    if data.username is not UNSET:
        updates["username"] = data.username
    if data.email is not UNSET:
        updates["email"] = data.email
    if data.bio is not UNSET:
        updates["bio"] = data.bio
    return await user_service.update(user_id, updates)
```

### Tagged unions for polymorphic requests

```python
from typing import Union

class TextMessage(Struct, tag="text"):
    content: str

class ImageMessage(Struct, tag="image"):
    url: str
    alt_text: str = ""

class LocationMessage(Struct, tag="location"):
    latitude: float
    longitude: float

Message = Union[TextMessage, ImageMessage, LocationMessage]

@post("/messages")
async def send_message(data: Message) -> dict:
    # Automatic dispatch based on "type" field in JSON
    match data:
        case TextMessage(content=content):
            return {"sent": "text", "length": len(content)}
        case ImageMessage(url=url):
            return {"sent": "image", "url": url}
        case LocationMessage(latitude=lat, longitude=lon):
            return {"sent": "location", "coords": [lat, lon]}
```

### Custom type handling with hooks

```python
from pathlib import Path
from decimal import Decimal
from typing import Any, Type

def enc_hook(obj: Any) -> Any:
    """Encode custom types to JSON-serializable values."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)  # Preserve precision
    raise NotImplementedError(f"Type {type(obj)} not supported")

def dec_hook(typ: Type, obj: Any) -> Any:
    """Decode JSON values to custom types."""
    if typ is Path:
        return Path(obj)
    if typ is Decimal:
        return Decimal(obj)
    raise NotImplementedError(f"Type {typ} not supported")

# Configure at app level
app = Litestar(
    route_handlers=[...],
    type_encoders={Path: str, Decimal: str},
    type_decoders=[
        (lambda t: t is Path, lambda t, v: Path(v)),
        (lambda t: t is Decimal, lambda t, v: Decimal(v)),
    ],
)
```

### Cross-field validation with __post_init__

```python
class DateRange(Struct):
    start_date: datetime
    end_date: datetime
    
    def __post_init__(self):
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")

class PriceRange(Struct):
    min_price: Decimal
    max_price: Decimal
    
    def __post_init__(self):
        if self.min_price > self.max_price:
            raise ValueError("min_price cannot exceed max_price")
```

---

## Granian production server configuration

Granian's Rust-based architecture delivers **41,000+ RPS** versus Uvicorn's **34,000** with significantly lower tail latency. Its unique design separates Rust I/O handling from Python execution with built-in backpressure.

### Worker and threading configuration

```bash
# I/O-bound ASGI (typical API)
granian app:app \
  --interface asgi \
  --host 0.0.0.0 --port 8000 \
  --workers 4 \
  --runtime-mode st \
  --loop uvloop \
  --backlog 2048 \
  --log --log-level info

# Production with lifecycle management
granian app:app \
  --interface asgi \
  --workers 3 \
  --runtime-mode st \
  --loop uvloop \
  --workers-lifetime 12h \
  --workers-max-rss 512 \
  --respawn-failed-workers \
  --respawn-interval 30 \
  --access-log

# WebSocket-heavy application
granian app:app \
  --interface asgi \
  --workers 2 \
  --runtime-threads 4 \
  --http 2 \
  --http2-max-concurrent-streams 500
```

Key parameters explained:

| Parameter | Purpose | Recommendation |
|-----------|---------|----------------|
| `--workers` | Process count | Match CPU cores (or 1 per container) |
| `--runtime-mode` | `st` (single-thread) or `mt` (multi-thread) Tokio | `st` for most cases; `mt` for high CPU count |
| `--loop` | Event loop implementation | `uvloop` on Linux for best performance |
| `--workers-lifetime` | Auto-respawn interval | `6h`-`12h` to prevent memory leaks |
| `--workers-max-rss` | Memory limit (MiB) | Set based on container limits |

### Docker deployment pattern

```dockerfile
FROM python:3.14-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["granian", "app.main:app", \
  "--host", "0.0.0.0", \
  "--port", "8000", \
  "--interface", "asgi", \
  "--workers", "1", \
  "--runtime-mode", "st", \
  "--loop", "uvloop", \
  "--workers-lifetime", "6h", \
  "--respawn-failed-workers", \
  "--log", "--log-level", "info"]
```

For Kubernetes, use **1 worker per container** and scale horizontally via replicas.

---

## OpenAPI generation and type-safe clients

Litestar generates **OpenAPI 3.1.0** schemas directly from msgspec Structs, including validation constraints from `Meta` annotations.

### Complete OpenAPI configuration

```python
from litestar import Litestar
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin, ScalarRenderPlugin
from litestar.openapi.spec import Components, SecurityScheme, Tag

openapi_config = OpenAPIConfig(
    title="My API",
    version="1.0.0",
    description="Production API with full OpenAPI documentation",
    path="/docs",
    tags=[
        Tag(name="Users", description="User management endpoints"),
        Tag(name="Auth", description="Authentication endpoints"),
    ],
    security=[{"BearerToken": []}],  # Default security for all routes
    components=Components(
        security_schemes={
            "BearerToken": SecurityScheme(
                type="http",
                scheme="bearer",
                bearer_format="JWT",
                description="JWT authentication token",
            ),
        },
    ),
    render_plugins=[
        SwaggerRenderPlugin(path="/swagger"),
        ScalarRenderPlugin(path="/scalar"),
    ],
)

app = Litestar(route_handlers=[...], openapi_config=openapi_config)
```

### Handler-level schema customization

```python
from litestar import get, post
from litestar.openapi.datastructures import ResponseSpec

class NotFoundError(msgspec.Struct):
    detail: str
    resource_id: str

@get(
    "/users/{user_id:uuid}",
    summary="Retrieve a user by ID",
    description="Fetches complete user profile including related data",
    tags=["Users"],
    operation_id="getUserById",
    responses={
        404: ResponseSpec(data_container=NotFoundError, description="User not found"),
    },
)
async def get_user(user_id: UUID) -> User:
    ...
```

Export the schema for client generation:

```bash
# Generate TypeScript client
curl http://localhost:8000/docs/openapi.json > openapi.json
npx openapi-typescript openapi.json -o ./src/api/types.ts
```

---

## Authentication and authorization patterns

Litestar provides built-in JWT backends that integrate with OpenAPI documentation automatically.

### JWT authentication with token revocation

```python
from litestar import Litestar, Request, Response, post, get
from litestar.security.jwt import JWTAuth, Token
from litestar.connection import ASGIConnection
from datetime import timedelta
import os

class User(msgspec.Struct):
    id: UUID
    email: str
    role: str

USERS_DB: dict[str, User] = {}
REVOKED_TOKENS: set[str] = set()

async def retrieve_user_handler(token: Token, connection: ASGIConnection) -> User | None:
    return USERS_DB.get(token.sub)

async def check_token_revoked(token: Token, connection: ASGIConnection) -> bool:
    return token.jti in REVOKED_TOKENS if token.jti else False

jwt_auth = JWTAuth[User](
    retrieve_user_handler=retrieve_user_handler,
    revoked_token_handler=check_token_revoked,
    token_secret=os.environ["JWT_SECRET"],
    default_token_expiration=timedelta(hours=1),
    exclude=["/auth/login", "/auth/register", "/health", "/docs"],
)

@post("/auth/login")
async def login(data: LoginRequest) -> Response[User]:
    user = await authenticate(data.email, data.password)
    return jwt_auth.login(
        identifier=str(user.id),
        token_extras={"role": user.role},
        response_body=user,
    )

@post("/auth/logout")
async def logout(request: Request[User, Token, Any]) -> dict:
    if request.auth.jti:
        REVOKED_TOKENS.add(request.auth.jti)
    return {"message": "Logged out"}

@get("/me")
async def get_current_user(request: Request[User, Token, Any]) -> User:
    return request.user

app = Litestar(
    route_handlers=[login, logout, get_current_user],
    on_app_init=[jwt_auth.on_app_init],
)
```

### Guards for role-based authorization

Guards run after authentication, receiving the connection and route handler:

```python
from litestar import Controller, get
from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler
from litestar.exceptions import NotAuthorizedException

def require_role(*roles: str):
    """Factory for role-based guards."""
    async def guard(connection: ASGIConnection, handler: BaseRouteHandler) -> None:
        if not connection.user or connection.user.role not in roles:
            raise NotAuthorizedException(f"Requires role: {', '.join(roles)}")
    return guard

def require_owner_or_admin(connection: ASGIConnection, handler: BaseRouteHandler) -> None:
    """Resource ownership guard."""
    user = connection.user
    resource_id = connection.path_params.get("user_id")
    if str(user.id) != resource_id and user.role != "admin":
        raise NotAuthorizedException("Access denied")

class AdminController(Controller):
    path = "/admin"
    guards = [require_role("admin")]  # All routes require admin

    @get("/users")
    async def list_all_users(self) -> list[User]: ...

class UserController(Controller):
    path = "/users"

    @get("/{user_id:uuid}", guards=[require_owner_or_admin])
    async def get_user(self, user_id: UUID) -> User: ...
```

### Security middleware stack

```python
from litestar.config.cors import CORSConfig
from litestar.middleware.rate_limit import RateLimitConfig

cors_config = CORSConfig(
    allow_origins=["https://myapp.com", "https://admin.myapp.com"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True,
    max_age=3600,
)

rate_limit_config = RateLimitConfig(
    rate_limit=("minute", 100),
    exclude=["/health", "/docs"],
)

app = Litestar(
    route_handlers=[...],
    cors_config=cors_config,
    middleware=[rate_limit_config.middleware],
)
```

---

## Async database patterns with SQLAlchemy 2.0

### Connection pooling and session management

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload
from sqlalchemy import select, ForeignKey
from contextlib import asynccontextmanager

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

session_factory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    # Use selectinload for collections to avoid N+1
    books: Mapped[list["Book"]] = relationship(back_populates="author", lazy="selectin")

class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    author: Mapped["Author"] = relationship(lazy="joined")  # Eager join for single relations
```

### TaskGroup for concurrent queries

Python 3.11+ `TaskGroup` provides structured concurrency with automatic cancellation:

```python
import asyncio

async def get_dashboard_data(session: AsyncSession, user_id: int) -> dict:
    """Execute independent queries concurrently."""
    async with asyncio.TaskGroup() as tg:
        user_task = tg.create_task(
            session.scalar(select(User).where(User.id == user_id))
        )
        orders_task = tg.create_task(
            session.scalars(select(Order).where(Order.user_id == user_id).limit(10))
        )
        notifications_task = tg.create_task(
            session.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read == False))
        )
    
    return {
        "user": user_task.result(),
        "recent_orders": orders_task.result().all(),
        "unread_notifications": notifications_task.result().all(),
    }
```

**Critical**: Never share sessions between concurrent tasks. Each task needs its own session:

```python
# WRONG - shared session causes race conditions
async def bad_concurrent(session: AsyncSession):
    async with asyncio.TaskGroup() as tg:
        tg.create_task(operation_1(session))  # Shared session!
        tg.create_task(operation_2(session))

# CORRECT - each task gets own session
async def good_concurrent():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(operation_with_own_session())
        tg.create_task(operation_with_own_session())

async def operation_with_own_session():
    async with session_factory() as session:
        # Safe - dedicated session
        await do_work(session)
```

### Exception groups for concurrent error handling

Use `except*` to handle specific exception types from TaskGroups:

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_user_data())
        tg.create_task(fetch_orders())
except* ValueError as eg:
    for exc in eg.exceptions:
        log.error(f"Validation error: {exc}")
except* OSError as eg:
    handle_io_errors(eg)
# Unhandled types automatically propagate
```

---

## Testing patterns

### Test client with dependency overrides

Litestar promotes the **app factory pattern** over runtime dependency overrides:

```python
from litestar.testing import create_test_client
from litestar.di import Provide
import pytest

def create_app(session_factory=None):
    if session_factory is None:
        session_factory = production_session_factory
    
    async def provide_session():
        async with session_factory() as session:
            yield session
    
    return Litestar(
        route_handlers=[UserController],
        dependencies={"session": Provide(provide_session)},
    )

@pytest.fixture
def test_session():
    # Use in-memory SQLite or test database
    return test_session_factory()

@pytest.fixture
def client(test_session):
    app = create_app(session_factory=lambda: test_session)
    with create_test_client(app) as client:
        yield client

def test_create_user(client):
    response = client.post("/users", json={"name": "Test", "email": "test@test.com"})
    assert response.status_code == 201
    assert response.json()["name"] == "Test"
```

### Async test client for coroutine tests

```python
from litestar.testing import AsyncTestClient
import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    async with AsyncTestClient(app) as client:
        yield client

async def test_async_endpoint(async_client):
    response = await async_client.get("/async-data")
    assert response.status_code == 200
```

### pytest-asyncio configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

---

## Observability and production readiness

### Structured logging with structlog

```python
from litestar import Litestar
from litestar.plugins.structlog import StructlogPlugin, StructlogConfig
from litestar.logging import StructLoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig

logging_config = StructlogConfig(
    structlog_logging_config=StructLoggingConfig(
        log_exceptions="always",
        traceback_line_limit=4,
    ),
    middleware_logging_config=LoggingMiddlewareConfig(
        request_log_fields=["method", "path", "query"],
        response_log_fields=["status_code"],
    ),
)

app = Litestar(
    route_handlers=[...],
    plugins=[StructlogPlugin(config=logging_config)],
)
```

### Health check endpoints

```python
@get("/health", include_in_schema=False, cache=False)
async def health_check(state: State) -> Response:
    checks = {
        "database": await check_database(state),
        "redis": await check_redis(state),
    }
    all_healthy = all(checks.values())
    return Response(
        {"status": "healthy" if all_healthy else "degraded", "checks": checks},
        status_code=200 if all_healthy else 503,
    )

@get("/health/live", include_in_schema=False)
async def liveness() -> dict:
    return {"status": "alive"}

@get("/health/ready", include_in_schema=False)
async def readiness(state: State) -> dict:
    # Check if app is ready to receive traffic
    return {"status": "ready"}
```

### Response caching with Redis

```python
from litestar import Litestar, get
from litestar.config.response_cache import ResponseCacheConfig
from litestar.stores.redis import RedisStore

redis_store = RedisStore.with_client(url="redis://localhost:6379/0")

@get("/expensive-query", cache=300)  # Cache for 5 minutes
async def expensive_query() -> dict:
    return await compute_expensive_result()

app = Litestar(
    route_handlers=[expensive_query],
    stores={"response_cache": redis_store},
    response_cache_config=ResponseCacheConfig(store="response_cache"),
)
```

---

## Modern idioms

### Pattern matching for request dispatch

Use structural pattern matching for complex handler logic:

```python
@post("/webhook")
async def handle_webhook(data: WebhookPayload) -> dict:
    match data:
        case {"event": "user.created", "data": {"id": user_id}}:
            await send_welcome_email(user_id)
            return {"processed": "welcome_email"}
        case {"event": "order.completed", "data": {"total": total}} if total > 1000:
            await flag_large_order(data)
            return {"processed": "large_order_flag"}
        case {"event": event_type}:
            log.info(f"Unhandled event: {event_type}")
            return {"processed": "logged"}
        case _:
            raise HTTPException(400, "Invalid webhook payload")
```

### Walrus operator reduces redundancy

```python
# In validation logic
if (user := await get_user(user_id)) is None:
    raise NotFoundException(f"User {user_id} not found")
return user

# List comprehensions with expensive computation
valid_items = [processed for item in items if (processed := validate(item))]
```

### f-string debug specifier

```python
# Quick debugging
user_id, action = "abc123", "login"
log.debug(f"{user_id=}, {action=}")  # user_id='abc123', action='login'
```

### Positional-only and keyword-only parameters

```python
def fetch(url, /, *, timeout=30, headers=None):
    """url is positional-only, others are keyword-only."""
    pass

fetch("https://api.example.com", timeout=60)  # ✓
# fetch(url="...", timeout=60)  # TypeError
```

---

## Tooling configuration

### ruff as unified linter and formatter

```toml
[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",  # pycodestyle errors
    "F",               # Pyflakes
    "I",               # isort
    "B",               # flake8-bugbear
    "UP",              # pyupgrade
    "S",               # flake8-bandit (security)
    "C4",              # flake8-comprehensions
    "RUF",             # Ruff-specific
]
ignore = ["E501"]  # Let formatter handle line length
fixable = ["ALL"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**" = ["S101"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```

### uv as package manager

```bash
# Project setup
uv init myproject && cd myproject
uv add litestar msgspec granian
uv add --dev pytest ruff basedpyright
uv run granian app:app

# Python version management
uv python install 3.14
uv python pin 3.14
```

### basedpyright strict configuration

```toml
[tool.basedpyright]
typeCheckingMode = "recommended"
pythonVersion = "3.14"
```

### Complete pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "myapi"
version = "1.0.0"
description = "Modern Python 3.14 API"
readme = "README.md"
license = "MIT"
requires-python = ">=3.14"
dependencies = [
    "litestar>=2.14",
    "msgspec>=0.18",
    "granian>=2.6",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=4.1",
    "ruff>=0.4",
    "basedpyright>=1.18",
]

[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "B", "UP", "S", "C4", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
"__init__.py" = ["F401"]

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true

[tool.basedpyright]
typeCheckingMode = "recommended"
pythonVersion = "3.14"

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = ["-ra", "-q", "--strict-markers", "--import-mode=importlib"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"

[tool.hatch.build.targets.wheel]
packages = ["src/myapi"]
```

---

## Anti-patterns to avoid

**Never block the event loop with sync I/O**:
```python
# WRONG
@get("/data")
async def bad_handler():
    time.sleep(5)  # Blocks everything!
    return data

# CORRECT
@get("/data", sync_to_thread=True)
def correct_handler():
    time.sleep(5)  # Runs in thread pool
    return data
```

**Never use lazy loading in async contexts**:
```python
# WRONG - implicit I/O in async
user = await session.get(User, 1)
for post in user.posts:  # Triggers lazy load - breaks!
    print(post.title)

# CORRECT - explicit eager loading
stmt = select(User).options(selectinload(User.posts)).where(User.id == 1)
user = (await session.scalars(stmt)).first()
```

**Never validate msgspec Structs at runtime init**—validation only occurs during decode:
```python
# This won't raise - msgspec doesn't validate on init
user = User(name=123, email="invalid")  # No error!

# Validation happens here
user = msgspec.json.decode(data, type=User)  # ValidationError if invalid
```

**Never share database sessions across concurrent tasks**—always create per-task sessions.

---

## Useful standard library additions

**pathlib gains copy/move** (3.14):
```python
from pathlib import Path
source = Path("source.txt")
source.copy(Path("dest") / "copied.txt")
source.move(Path("dest") / "moved.txt")
```

**itertools.batched for chunking** (3.12+):
```python
from itertools import batched
for batch in batched(user_ids, 50):  # API limit: 50/request
    await api.fetch_users(batch)
```

**tomllib for config parsing** (3.11+):
```python
import tomllib
with open("config.toml", "rb") as f:
    config = tomllib.load(f)
```

**zoneinfo for timezones** (3.9+):
```python
from datetime import datetime
from zoneinfo import ZoneInfo
utc_now = datetime.now(ZoneInfo("UTC"))
local = utc_now.astimezone(ZoneInfo("America/New_York"))
```

---

## Migration checklist: 3.12 → 3.14

| Feature | Change | Action |
|---------|--------|--------|
| Forward references | Deferred evaluation default | Remove string quotes from type hints |
| `from __future__ import annotations` | Deprecated | Remove import |
| `typing.List`, `Dict`, etc. | Deprecated aliases | Use `list`, `dict` builtins |
| TypeVar declarations | Verbose | Migrate to `class Foo[T]:` syntax |
| `except (A, B):` | Optional parens | Remove parentheses when not using `as` |
| `return` in `finally` | Now warns | Refactor to avoid control flow in finally |
| Exception handling | Groups available | Consider `except*` for concurrent code |

**Tooling:**
- `autopep695` — Auto-converts old TypeVar syntax to PEP 695
- `pyupgrade` — Modernizes type annotations  
- `ruff --select=UP` — Upgrades deprecated patterns

**Free-threaded adoption checklist:**
1. Verify dependencies support free-threading (check py-free-threading.github.io)
2. Test with `python3.14t` in CI
3. Add explicit `threading.Lock` for compound operations
4. Monitor single-threaded performance (5-10% overhead)
5. Use `PYTHON_GIL=1` fallback for incompatible code paths

---

## Technology versions and compatibility

| Technology | Version | Python Requirement |
|------------|---------|-------------------|
| Python | 3.14+ | - |
| Litestar | 2.14+ | 3.8+ (3.13+ recommended) |
| msgspec | 0.18+ | 3.8+ |
| Granian | 2.6+ | 3.10+ |
| SQLAlchemy | 2.0+ | 3.7+ |

This stack delivers the performance, type safety, and developer experience needed for production APIs in 2025/2026. The combination of Litestar's elegant architecture, msgspec's speed, Granian's throughput, and Python 3.14's new capabilities creates a foundation for high-performance, maintainable services.