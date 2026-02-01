# Implementation Plan: Plex Integration

## Overview

This implementation plan covers Phase 3 of the Zondarr project: Plex media server integration. The tasks are organized to build incrementally, starting with core types and the PlexClient implementation, then adding OAuth support, and finally integrating with the existing redemption flow.

## Tasks

- [ ] 1. Add plexapi dependency and extend media types
  - [ ] 1.1 Add plexapi package to project dependencies
    - Run `uv add plexapi` in the backend directory
    - Verify plexapi version >= 4.18.0
    - _Requirements: 18.1_

  - [ ] 1.2 Add PlexUserType enum to media/types.py
    - Add `PlexUserType` StrEnum with FRIEND and HOME values
    - Follow existing Capability enum pattern
    - _Requirements: 6.1_

- [ ] 2. Implement PlexClient core functionality
  - [ ] 2.1 Implement PlexClient connection management
    - Implement `__init__` with url and api_key parameters
    - Implement `__aenter__` using asyncio.to_thread() to create PlexServer and MyPlexAccount
    - Implement `__aexit__` to clean up resources
    - Implement `capabilities()` returning CREATE_USER, DELETE_USER, LIBRARY_ACCESS
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 2.2 Write property test for context manager round-trip
    - **Property 1: Context Manager Round-Trip**
    - **Validates: Requirements 1.1, 1.2**

  - [ ] 2.3 Implement test_connection method
    - Use asyncio.to_thread() to query server info
    - Return True on success, False on any exception
    - Do not raise exceptions for connection failures
    - _Requirements: 1.3, 1.4, 1.5_

  - [ ] 2.4 Write property test for test_connection return values
    - **Property 2: Connection Test Return Value Correctness**
    - **Validates: Requirements 1.3, 1.4, 1.5**

  - [ ] 2.5 Implement get_libraries method
    - Use asyncio.to_thread() to call server.library.sections()
    - Map each section to LibraryInfo with key as external_id, title as name, type as library_type
    - Raise MediaClientError if client not initialized or on API failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 2.6 Write property test for get_libraries
    - **Property 3: Library Retrieval Produces Valid Structs**
    - **Validates: Requirements 3.1, 3.2**

- [ ] 3. Checkpoint - Verify core PlexClient functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement PlexClient user creation
  - [ ] 4.1 Implement Friend user creation via inviteFriend
    - Use asyncio.to_thread() to call account.inviteFriend()
    - Return ExternalUser with email as identifier
    - Raise MediaClientError with USER_ALREADY_EXISTS on duplicate
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 4.2 Write property test for Friend creation
    - **Property 4: Friend Creation Returns Valid ExternalUser**
    - **Validates: Requirements 4.1, 4.2**

  - [ ] 4.3 Implement Home User creation via createHomeUser
    - Use asyncio.to_thread() to call account.createHomeUser()
    - Return ExternalUser with Plex user ID as identifier
    - Raise MediaClientError with USERNAME_TAKEN on duplicate
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ] 4.4 Write property test for Home User creation
    - **Property 5: Home User Creation Returns Valid ExternalUser**
    - **Validates: Requirements 5.1, 5.2**

  - [ ] 4.5 Implement create_user method with user type routing
    - Accept plex_user_type parameter (default FRIEND)
    - Route to _create_friend if FRIEND and email provided
    - Route to _create_home_user if HOME
    - Raise MediaClientError with EMAIL_REQUIRED if FRIEND without email
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 4.6 Write property test for user type routing
    - **Property 6: User Type Routing Correctness**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ] 5. Implement PlexClient user management
  - [ ] 5.1 Implement delete_user method
    - Determine user type (Friend vs Home) from identifier
    - Use removeFriend() for Friends, appropriate method for Home Users
    - Return True on success, False if not found
    - Raise MediaClientError on other failures
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 5.2 Write property test for delete_user
    - **Property 7: Delete User Return Value Correctness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

  - [ ] 5.3 Implement set_library_access method
    - Use updateFriend() for Friends with section list
    - Handle Home User library access configuration
    - Return True on success, False if user not found
    - Handle empty library list as revoke all access
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4_

  - [ ] 5.4 Write property test for set_library_access
    - **Property 8: Library Access Update Return Value Correctness**
    - **Validates: Requirements 8.1, 8.2, 8.3, 9.1, 9.2, 9.3**

  - [ ] 5.5 Implement set_user_enabled method
    - Return False always (Plex doesn't support enable/disable)
    - Log warning about unsupported operation
    - Do not raise exception
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ] 5.6 Implement update_permissions method
    - Map can_download to allowSync setting
    - Return True on success, False if user not found
    - Raise MediaClientError on failure
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ] 5.7 Write property test for update_permissions
    - **Property 9: Permission Update Mapping and Return Value**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.5**

  - [ ] 5.8 Implement list_users method
    - Retrieve all Friends via account.users()
    - Retrieve all Home Users
    - Map each to ExternalUser struct
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 5.9 Write property test for list_users
    - **Property 10: List Users Returns All Users as ExternalUser Structs**
    - **Validates: Requirements 12.1, 12.2, 12.3**

- [ ] 6. Checkpoint - Verify complete PlexClient implementation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Register PlexClient in registry
  - [ ] 7.1 Register PlexClient for ServerType.PLEX
    - Import PlexClient in app.py or appropriate startup location
    - Call registry.register(ServerType.PLEX, PlexClient)
    - _Requirements: 16.1, 16.2, 16.3_

  - [ ] 7.2 Write unit tests for registry integration
    - Test create_client returns PlexClient instance
    - Test get_capabilities returns correct set
    - _Requirements: 16.1, 16.2, 16.3_

- [ ] 8. Implement Plex OAuth service
  - [ ] 8.1 Create PlexOAuthService class
    - Initialize with httpx.AsyncClient and client_id
    - Implement close() method for cleanup
    - _Requirements: 13.1_

  - [ ] 8.2 Implement create_pin method
    - POST to plex.tv/api/v2/pins with X-Plex-Client-Identifier header
    - Parse response for pin id, code, and expiration
    - Return PlexOAuthPin struct with auth_url
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ] 8.3 Write property test for create_pin
    - **Property 11: OAuth PIN Generation Returns Valid Response**
    - **Validates: Requirements 13.1, 13.2**

  - [ ] 8.4 Implement check_pin method
    - GET plex.tv/api/v2/pins/{pin_id}
    - Check if authToken is present in response
    - If authenticated, call get_user_email to retrieve email
    - Return PlexOAuthResult with authenticated status and email
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ] 8.5 Write property test for check_pin
    - **Property 12: OAuth PIN Verification Retrieves Email on Success**
    - **Validates: Requirements 14.1, 14.2, 14.3**

  - [ ] 8.6 Implement get_user_email method
    - GET plex.tv/api/v2/user with X-Plex-Token header
    - Extract email from response
    - _Requirements: 14.3_

- [ ] 9. Implement Plex OAuth controller
  - [ ] 9.1 Create PlexOAuthController with endpoints
    - POST /api/v1/join/plex/oauth/pin - create_pin endpoint
    - GET /api/v1/join/plex/oauth/pin/{pin_id} - check_pin endpoint
    - Mark endpoints as exclude_from_auth=True
    - _Requirements: 13.1, 13.2, 14.1_

  - [ ] 9.2 Create API schemas for OAuth responses
    - PlexOAuthPinResponse with pin_id, code, auth_url, expires_at
    - PlexOAuthCheckResponse with authenticated, email, error
    - _Requirements: 13.2, 14.2, 14.3_

  - [ ] 9.3 Add dependency injection for PlexOAuthService
    - Create provide_plex_oauth_service function
    - Register in controller dependencies
    - _Requirements: 13.1_

  - [ ] 9.4 Write unit tests for OAuth endpoints
    - Test PIN creation returns valid response
    - Test PIN check returns correct status
    - _Requirements: 13.1, 13.2, 14.1, 14.2_

- [ ] 10. Checkpoint - Verify OAuth flow
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Integrate Plex with redemption service
  - [ ] 11.1 Update RedemptionService for Plex user types
    - Handle plex_user_type parameter in redemption
    - Pass OAuth-retrieved email for Friend invitations
    - Pass username for Home User creation
    - _Requirements: 15.1, 15.2_

  - [ ] 11.2 Verify rollback works for Plex
    - Ensure delete_user is called on rollback
    - Test multi-server rollback with Plex
    - _Requirements: 15.5_

  - [ ] 11.3 Write property test for redemption rollback
    - **Property 13: Redemption Rollback on Failure**
    - **Validates: Requirements 15.5**

- [ ] 12. Add comprehensive error handling
  - [ ] 12.1 Implement error code mapping in PlexClient
    - Map Plex API errors to MediaClientError codes
    - Ensure all errors include operation, server_url, cause
    - _Requirements: 17.1_

  - [ ] 12.2 Write property test for error structure
    - **Property 14: Error Structure Contains Required Fields**
    - **Validates: Requirements 17.1**

  - [ ] 12.3 Add structlog logging throughout PlexClient
    - Log at info level for successful operations
    - Log at warning/error level for failures
    - Ensure no sensitive data (tokens, passwords) is logged
    - _Requirements: 17.2, 17.3, 17.4, 17.5_

- [ ] 13. Final checkpoint - Complete integration testing
  - Ensure all tests pass, ask the user if questions arise.
  - Run basedpyright for type checking
  - Run ruff check and ruff format

## Notes

- All property-based tests are required for comprehensive coverage
- All python-plexapi calls must use asyncio.to_thread() to avoid blocking the event loop
- The PlexClient follows the same patterns as JellyfinClient for consistency
- OAuth flow is optional - invitations can also specify Home User creation without OAuth
- Property tests use Hypothesis with minimum 100 iterations per test


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
