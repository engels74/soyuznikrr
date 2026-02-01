# Implementation Plan: Zondarr Foundation

## Overview

This implementation plan covers the foundation phase of Zondarr - establishing core infrastructure including project scaffolding, database models, media client protocol/registry, and a basic Litestar application with health endpoints.

## Tasks

- [x] 1. Project Setup and Configuration
  - [x] 1.1 Update pyproject.toml with dependencies and tooling configuration
    - Add all production dependencies (litestar, msgspec, granian, sqlalchemy, etc.)
    - Add dev dependencies (pytest, hypothesis, ruff, basedpyright)
    - Configure ruff, basedpyright, and pytest settings
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Create project directory structure
    - Create `src/zondarr/` with `core/`, `media/`, `models/`, `repositories/`, `services/`, `api/` modules
    - Add `__init__.py` files for all packages
    - _Requirements: 1.1, 1.2_

  - [x] 1.3 Implement configuration module
    - Create `config.py` with Settings msgspec.Struct
    - Implement `load_settings()` with environment variable loading
    - Add validation for required settings (SECRET_KEY)
    - Raise ConfigurationError for missing required values
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [x] 1.4 Write property tests for configuration
    - **Property 1: Configuration Loading with Defaults**
    - **Property 2: Configuration Validation Fails Fast**
    - **Validates: Requirements 1.3, 1.5, 1.6**
    - [x] 1.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 1.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 2. Core Exceptions and Types
  - [x] 2.1 Implement exception hierarchy
    - Create `core/exceptions.py` with ZondarrError base class
    - Add ConfigurationError, RepositoryError, ValidationError, NotFoundError
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
    - [x] 2.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 2.2 Implement shared types
    - Create `core/types.py` with common type aliases
    - _Requirements: 2.7_
    - [x] 2.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 2.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 3. Database Models
  - [x] 3.1 Implement base model and mixins
    - Create `models/base.py` with Base, TimestampMixin, UUIDPrimaryKeyMixin
    - Use timezone-aware UTC datetimes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
    - [x] 3.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.2 Implement MediaServer and Library models
    - Create `models/media_server.py` with ServerType enum, MediaServer, Library
    - Configure relationships with selectinload/joined for eager loading
    - _Requirements: 2.1, 2.2_
    - [x] 3.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.3 Implement Invitation model with associations
    - Create `models/invitation.py` with Invitation model
    - Add invitation_servers and invitation_libraries association tables
    - _Requirements: 2.3, 2.6_
    - [x] 3.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.4 Implement Identity and User models
    - Create `models/identity.py` with Identity and User models
    - Configure relationships between Identity, User, and MediaServer
    - _Requirements: 2.4, 2.5_
    - [x] 3.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 3.5 Write property tests for model serialization
    - **Property 3: Model Serialization Round-Trip**
    - **Validates: Requirements 2.7**
    - [x] 3.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 3.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 4. Checkpoint - Verify models compile
  - Ensure all models import correctly and relationships are valid
  - Run `basedpyright` to check type errors
  - [x] 4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
  - [x] 4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [x] 5. Media Client Protocol and Registry
  - [x] 5.1 Implement media types
    - Create `media/types.py` with Capability enum, LibraryInfo, ExternalUser structs
    - _Requirements: 3.7_
    - [x] 5.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.2 Implement media exceptions
    - Create `media/exceptions.py` with MediaClientError, UnknownServerTypeError
    - _Requirements: 3.9, 4.4_
    - [x] 5.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.3 Implement MediaClient protocol
    - Create `media/protocol.py` with MediaClient Protocol class
    - Define all async methods with proper type hints
    - Use Self type and positional-only/keyword-only parameters
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.10_
    - [x] 5.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.4 Implement ClientRegistry singleton
    - Create `media/registry.py` with ClientRegistry class
    - Implement register, get_client_class, get_capabilities, create_client methods
    - Use ClassVar for singleton pattern
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
    - [x] 5.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.5 Implement Jellyfin client stub
    - Create `media/clients/jellyfin.py` with JellyfinClient class
    - Implement capabilities() and stub methods with NotImplementedError
    - _Requirements: 4.6_
    - [x] 5.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.6 Implement Plex client stub
    - Create `media/clients/plex.py` with PlexClient class
    - Implement capabilities() and stub methods with NotImplementedError
    - _Requirements: 4.6_
    - [x] 5.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 5.7 Write property tests for registry
    - **Property 5: Registry Returns Correct Client**
    - **Property 6: Registry Raises Error for Unknown Types**
    - **Property 7: Registry Singleton Behavior**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
    - [x] 5.7.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 5.7.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 6. Repository Layer
  - [x] 6.1 Implement base repository
    - Create `repositories/base.py` with generic Repository[T] class
    - Implement get_by_id, get_all, create, delete with error wrapping
    - Use PEP 695 type parameter syntax
    - _Requirements: 5.1, 5.6_
    - [x] 6.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [x] 6.2 Implement MediaServerRepository
    - Create `repositories/media_server.py`
    - Add get_enabled method
    - _Requirements: 5.2_
    - [x] 6.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [x] 6.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 6.3 Implement InvitationRepository
    - Create `repositories/invitation.py`
    - Add get_by_code, get_active, increment_use_count, disable methods
    - _Requirements: 5.3_
    - [ ] 6.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 6.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 6.4 Implement IdentityRepository
    - Create `repositories/identity.py`
    - Add update method
    - _Requirements: 5.4_
    - [ ] 6.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 6.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 6.5 Implement UserRepository
    - Create `repositories/user.py`
    - Add get_by_identity, get_by_server, update methods
    - _Requirements: 5.5_
    - [ ] 6.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 6.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 6.6 Write property tests for repositories
    - **Property 8: Repository CRUD Round-Trip**
    - **Property 9: Repository Wraps Database Errors**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**
    - [ ] 6.6.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 6.6.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 7. Checkpoint - Verify repository layer
  - Ensure all repositories compile and type check
  - Run `basedpyright` to check type errors
  - [ ] 7.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
  - [ ] 7.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 8. Service Layer
  - [ ] 8.1 Implement MediaServerService
    - Create `services/media_server.py`
    - Implement add, update, remove, test_connection methods
    - Validate connection before persisting
    - _Requirements: 6.1, 6.2, 6.3_
    - [ ] 8.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 8.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 8.2 Implement InvitationService
    - Create `services/invitation.py`
    - Implement create, validate, redeem methods
    - Check expiration, use count, enabled status on redemption
    - Return specific error reasons for validation failures
    - _Requirements: 6.4, 6.5, 6.6_
    - [ ] 8.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 8.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 8.3 Write property tests for services
    - **Property 10: Service Validates Before Persisting**
    - **Property 11: Invitation Validation Checks All Conditions**
    - **Validates: Requirements 6.3, 6.5, 6.6**
    - [ ] 8.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 8.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 9. API Layer
  - [ ] 9.1 Implement API schemas
    - Create `api/schemas.py` with msgspec Structs
    - Define ErrorResponse, MediaServerCreate, MediaServerResponse, etc.
    - Use Meta annotations for validation constraints
    - _Requirements: 7.3, 9.1_
    - [ ] 9.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.2 Implement error handlers
    - Create `api/errors.py` with exception handlers
    - Handle ValidationError, NotFoundError, and generic exceptions
    - Include correlation IDs in responses and logs
    - Never expose internal details
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6_
    - [ ] 9.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.3 Implement health controller
    - Create `api/health.py` with HealthController
    - Implement /health, /health/live, /health/ready endpoints
    - Check database connectivity for health status
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
    - [ ] 9.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.4 Write property tests for health endpoints
    - **Property 12: Health Endpoints Return Correct Status**
    - **Validates: Requirements 8.4, 8.5, 8.6, 8.7**
    - [ ] 9.4.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.4.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 9.5 Write property tests for error handling
    - **Property 13: Error Responses Are Safe and Traceable**
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**
    - [ ] 9.5.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 9.5.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 10. Application Factory
  - [ ] 10.1 Implement database module
    - Create `core/database.py` with engine creation and session factory
    - Implement lifespan context manager for connection pool
    - Implement session provider with commit/rollback
    - _Requirements: 7.5_
    - [ ] 10.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 10.2 Implement application factory
    - Create `app.py` with create_app() function
    - Configure dependency injection with Provide
    - Register media clients in registry
    - Configure OpenAPI with Swagger/Scalar plugins
    - Configure structlog plugin
    - Register exception handlers
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6, 7.7_
    - [ ] 10.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 10.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 11. Database Migrations
  - [ ] 11.1 Initialize Alembic
    - Create `alembic.ini` and `migrations/env.py`
    - Configure for async SQLAlchemy
    - Support both SQLite and PostgreSQL
    - _Requirements: 10.1, 10.2_
    - [ ] 11.1.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.1.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 11.2 Create initial migration
    - Generate migration for all foundation tables
    - Include media_servers, libraries, invitations, identities, users
    - Include association tables
    - _Requirements: 10.3, 10.4_
    - [ ] 11.2.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.2.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

  - [ ] 11.3 Write tests for migrations
    - **Property 14: Migrations Preserve Data**
    - Test migration and rollback
    - **Validates: Requirements 10.4, 10.5**
    - [ ] 11.3.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
    - [ ] 11.3.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

- [ ] 12. Final Checkpoint
  - Ensure all tests pass
  - Run `ruff check` and `ruff format`
  - Run `basedpyright` for type checking
  - Verify application starts with `granian zondarr.app:app --interface asgi`
  - Test health endpoints manually
  - [ ] 12.1 Verify implementation adheres to coding guidelines in `.augment/rules/backend-dev-pro.md`
  - [ ] 12.2 Run `uvx basedpyright@latest` and fix all type errors following Type Safety Guidelines

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases

## Verification Guidelines

### General Code Quality Verification (*.1 subtasks)

Verify the task implementation adheres to all coding guidelines specified in `.augment/rules/backend-dev-pro.md`.

### Type Safety Verification (*.2 subtasks)

Run `uvx basedpyright@latest` in the project directory to perform static type checking on the Python codebase. After the command completes, analyze all reported errors and warnings, then systematically fix each issue by:

1. Running the type checker and capturing the full output
2. Categorizing the errors and warnings by type and severity
3. Creating a task list to track progress on fixing each category of issues
4. For each error/warning:
   - Always rely on the "Type Safety Guidelines" described below
   - Locate the relevant code using the file path and line number from the error message
   - Understand the root cause by examining the code context
   - Implement the appropriate fix (type annotations, imports, logic corrections, etc.)
   - Verify the fix resolves the specific error
5. Re-run `uvx basedpyright@latest` after fixes to confirm all issues are resolved
6. Ensure all fixes maintain code functionality and follow existing code patterns in the repository

Focus on fixing actual errors first, then warnings. Check for any downstream changes needed when fixing type-related issues (such as updating function signatures, return types, or parameter types that may affect callers).

#### Type Safety Guidelines

##### Core rules
- Use uvx basedpyright everywhere:
  - Local checks: `uvx basedpyright@latest`
  - CI: `uvx basedpyright@latest` (must pass with 0 errors, 0 warnings)
- Absolutely 0 errors and 0 warnings across all code, including tests. No exceptions.
- Fix issues rather than ignoring them. Ignores are only for unavoidable third‑party gaps.
- Never use global ignores or looser project-level rules to hide issues.
- Only install type stubs when basedpyright reports missing stubs (e.g., `uv add -D types-requests`).

##### Ignore policy (strict)
- Per-line, rule-scoped ignores only: `# pyright: ignore[rule-code]`
- Forbid bare `# type: ignore` (enforced via config).
- Add a brief reason only when not obvious (e.g., "third‑party lib has no stubs").
- Remove ignores as soon as the underlying issue is resolved.

Examples:
```python
# Good (explicit + scoped)
data = third_party_func()  # pyright: ignore[reportUnknownVariableType]  # lib lacks stubs

# Bad (blanket suppression)
data = third_party_func()  # type: ignore
```

##### Modern typing conventions (3.14+)

###### PEP 695 generics and type aliases
- Use inline `class Foo[T]:` and `def foo[T]:` syntax for all generic types instead of explicit `TypeVar` declarations.
- Use the `type` statement for type aliases: `type ListOrSet[T] = list[T] | set[T]`
- No need to import `TypeVar` or `Generic` for simple cases—variance is auto-inferred.

```python
# ❌ Legacy (pre-3.12)
from typing import TypeVar, Generic
_T_co = TypeVar("_T_co", covariant=True, bound=str)
class ClassA(Generic[_T_co]):
    def method1(self) -> _T_co: ...

# ✅ Modern (3.12+)
class ClassA[T: str]:  # Variance auto-inferred, bound inline
    def method1(self) -> T: ...

# Type aliases
type ListOrSet[T] = list[T] | set[T]
```

###### Deferred annotation evaluation (3.14)
- Remove string quotes from forward references—Python 3.14's deferred evaluation handles them automatically.
- Remove `from __future__ import annotations` imports (now deprecated, emits warning).
- Use `annotationlib.get_annotations()` for runtime inspection when needed.

```python
# Python 3.14: No quotes needed for forward references
class Node:
    def __init__(self, value: int, next: Node | None = None):  # Works!
        self.value = value
        self.next = next
```

###### TypeIs for intuitive type narrowing
- Prefer `TypeIs` over `TypeGuard` for type narrowing functions—it narrows both `if` and `else` branches.
- Reserve `TypeGuard` only when narrowing to a non-subtype (e.g., invariant containers).

```python
from typing import TypeIs, TypeGuard

# ✅ Preferred: TypeIs narrows both branches
def is_str(val: object) -> TypeIs[str]:
    return isinstance(val, str)

def process(val: int | str) -> None:
    if is_str(val):
        print(val.upper())  # val is str
    else:
        print(val + 1)      # val is int ← TypeIs enables this!

# Use TypeGuard only for non-subtype narrowing
def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in val)
```

###### Self type for method chaining
- Use `Self` for methods returning the instance's type, especially in method chaining and classmethods.

```python
from typing import Self

class Shape:
    def set_scale(self, scale: float) -> Self:
        self.scale = scale
        return self

    @classmethod
    def create(cls) -> Self:
        return cls()
```

###### @override decorator
- Decorate all intentional method overrides with `@override` to catch inheritance bugs.

```python
from typing import override

class Child(Parent):
    @override
    def foo(self, x: int) -> int:  # ✅ Verified override
        return x + 1
```

###### Built-in generics and union syntax
- Use built-in generics: `list[str]`, `dict[str, int]`, `set[T]`
- Use `|` union syntax: `str | None`, `int | str`
- Use abstract types from `collections.abc` for APIs: `Iterable[str]`, `Mapping[str, int]`

###### TypedDict with modern features
- Use `Required`/`NotRequired` for mixed totality.
- Use `ReadOnly` for immutable keys (3.13+).
- Use `closed=True` for strict TypedDicts that reject extra keys (3.14+).

```python
from typing import TypedDict, Required, NotRequired, ReadOnly

class Movie(TypedDict):
    title: Required[str]
    year: NotRequired[int]
    rating: ReadOnly[float]

# Closed TypedDict (3.14+) - no extra keys allowed
class StrictConfig(TypedDict, closed=True):
    host: str
    port: int
```

###### Protocol for structural subtyping
- Use `Protocol` for interfaces; prefer structural subtyping over ABCs for flexibility.

```python
from typing import Protocol

class SupportsClose(Protocol):
    def close(self) -> None: ...

def close_all(items: Iterable[SupportsClose]) -> None:
    for item in items:
        item.close()
```

###### Additional conventions
- Prefer `Final`, `Literal`, `Annotated` where they add clarity or constraints.
- Use `typing.assert_never` for exhaustiveness in match/if-else fallthroughs.
- Avoid walrus operator (`:=`), `yield`, and `await` in annotations (disallowed in 3.14).

##### Public API quality bar
- Public functions, methods, and module-level constants must be fully typed (params and return).
- Avoid `Any` at API boundaries. If unavoidable at the edge, isolate with a small, well-documented adapter and keep `Any` from leaking inward.
- Don't use `cast(...)` to silence type errors except in tiny, audited boundary helpers.
- Prefer small, composable `Protocol`s over deep inheritance to express behavior.

##### Tests are first-class
- Tests must meet the same 0-warnings standard.
- Avoid untyped fixtures; annotate fixture return types and parametrized values.
- For factories/builders, provide precise types—don't default to `dict[str, Any]` unless the data truly is open-ended.

##### basedpyright configuration
Use `typeCheckingMode = "recommended"` for strictest checking:

```toml
[tool.basedpyright]
typeCheckingMode = "recommended"
pythonVersion = "3.14"
```

| Mode | Missing returns | Missing params | Unknown types |
|------|-----------------|----------------|---------------|
| basic | none | none | none |
| standard | none | none | warning |
| strict | error | error | error |
| recommended | error | error | error + extras |
| all | error (every rule) | error | error |

##### Migration from older patterns
When fixing issues, prefer modern replacements:

| Legacy Pattern | Modern Replacement |
|---------------|-------------------|
| `"ClassName"` forward refs | Direct references (deferred evaluation) |
| `from __future__ import annotations` | Remove (default behavior in 3.14) |
| `TypeVar("T")` boilerplate | `class Foo[T]:` syntax |
| `TypeGuard` for narrowing | `TypeIs` for intuitive narrowing |
| `typing.List`, `typing.Dict` | `list`, `dict` builtins |
| `Optional[X]` | `X \| None` |
| `Union[A, B]` | `A \| B` |
| `TypeAlias` annotation | `type` statement |

##### Workflow
- Local: `uvx basedpyright@latest` (run before commits)
- Add stubs only on demand (when missing-stub diagnostics appear)
- Use `autopep695` to auto-convert old TypeVar syntax to PEP 695
- Use `ruff --select=UP` to upgrade deprecated patterns
