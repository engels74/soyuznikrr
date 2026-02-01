# Implementation Plan: Zondarr Foundation

## Overview

This implementation plan covers the foundation phase of Zondarr - establishing core infrastructure including project scaffolding, database models, media client protocol/registry, and a basic Litestar application with health endpoints.

## Tasks

- [ ] 1. Project Setup and Configuration
  - [x] 1.1 Update pyproject.toml with dependencies and tooling configuration
    - Add all production dependencies (litestar, msgspec, granian, sqlalchemy, etc.)
    - Add dev dependencies (pytest, hypothesis, ruff, basedpyright)
    - Configure ruff, basedpyright, and pytest settings
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Create project directory structure
    - Create `src/zondarr/` with `core/`, `media/`, `models/`, `repositories/`, `services/`, `api/` modules
    - Add `__init__.py` files for all packages
    - _Requirements: 1.1, 1.2_

  - [ ] 1.3 Implement configuration module
    - Create `config.py` with Settings msgspec.Struct
    - Implement `load_settings()` with environment variable loading
    - Add validation for required settings (SECRET_KEY)
    - Raise ConfigurationError for missing required values
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [ ] 1.4 Write property tests for configuration
    - **Property 1: Configuration Loading with Defaults**
    - **Property 2: Configuration Validation Fails Fast**
    - **Validates: Requirements 1.3, 1.5, 1.6**

- [ ] 2. Core Exceptions and Types
  - [ ] 2.1 Implement exception hierarchy
    - Create `core/exceptions.py` with ZondarrError base class
    - Add ConfigurationError, RepositoryError, ValidationError, NotFoundError
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ] 2.2 Implement shared types
    - Create `core/types.py` with common type aliases
    - _Requirements: 2.7_

- [ ] 3. Database Models
  - [ ] 3.1 Implement base model and mixins
    - Create `models/base.py` with Base, TimestampMixin, UUIDPrimaryKeyMixin
    - Use timezone-aware UTC datetimes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 3.2 Implement MediaServer and Library models
    - Create `models/media_server.py` with ServerType enum, MediaServer, Library
    - Configure relationships with selectinload/joined for eager loading
    - _Requirements: 2.1, 2.2_

  - [ ] 3.3 Implement Invitation model with associations
    - Create `models/invitation.py` with Invitation model
    - Add invitation_servers and invitation_libraries association tables
    - _Requirements: 2.3, 2.6_

  - [ ] 3.4 Implement Identity and User models
    - Create `models/identity.py` with Identity and User models
    - Configure relationships between Identity, User, and MediaServer
    - _Requirements: 2.4, 2.5_

  - [ ] 3.5 Write property tests for model serialization
    - **Property 3: Model Serialization Round-Trip**
    - **Validates: Requirements 2.7**

- [ ] 4. Checkpoint - Verify models compile
  - Ensure all models import correctly and relationships are valid
  - Run `basedpyright` to check type errors

- [ ] 5. Media Client Protocol and Registry
  - [ ] 5.1 Implement media types
    - Create `media/types.py` with Capability enum, LibraryInfo, ExternalUser structs
    - _Requirements: 3.7_

  - [ ] 5.2 Implement media exceptions
    - Create `media/exceptions.py` with MediaClientError, UnknownServerTypeError
    - _Requirements: 3.9, 4.4_

  - [ ] 5.3 Implement MediaClient protocol
    - Create `media/protocol.py` with MediaClient Protocol class
    - Define all async methods with proper type hints
    - Use Self type and positional-only/keyword-only parameters
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.10_

  - [ ] 5.4 Implement ClientRegistry singleton
    - Create `media/registry.py` with ClientRegistry class
    - Implement register, get_client_class, get_capabilities, create_client methods
    - Use ClassVar for singleton pattern
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 5.5 Implement Jellyfin client stub
    - Create `media/clients/jellyfin.py` with JellyfinClient class
    - Implement capabilities() and stub methods with NotImplementedError
    - _Requirements: 4.6_

  - [ ] 5.6 Implement Plex client stub
    - Create `media/clients/plex.py` with PlexClient class
    - Implement capabilities() and stub methods with NotImplementedError
    - _Requirements: 4.6_

  - [ ] 5.7 Write property tests for registry
    - **Property 5: Registry Returns Correct Client**
    - **Property 6: Registry Raises Error for Unknown Types**
    - **Property 7: Registry Singleton Behavior**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

- [ ] 6. Repository Layer
  - [ ] 6.1 Implement base repository
    - Create `repositories/base.py` with generic Repository[T] class
    - Implement get_by_id, get_all, create, delete with error wrapping
    - Use PEP 695 type parameter syntax
    - _Requirements: 5.1, 5.6_

  - [ ] 6.2 Implement MediaServerRepository
    - Create `repositories/media_server.py`
    - Add get_enabled method
    - _Requirements: 5.2_

  - [ ] 6.3 Implement InvitationRepository
    - Create `repositories/invitation.py`
    - Add get_by_code, get_active, increment_use_count, disable methods
    - _Requirements: 5.3_

  - [ ] 6.4 Implement IdentityRepository
    - Create `repositories/identity.py`
    - Add update method
    - _Requirements: 5.4_

  - [ ] 6.5 Implement UserRepository
    - Create `repositories/user.py`
    - Add get_by_identity, get_by_server, update methods
    - _Requirements: 5.5_

  - [ ] 6.6 Write property tests for repositories
    - **Property 8: Repository CRUD Round-Trip**
    - **Property 9: Repository Wraps Database Errors**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6**

- [ ] 7. Checkpoint - Verify repository layer
  - Ensure all repositories compile and type check
  - Run `basedpyright` to check type errors

- [ ] 8. Service Layer
  - [ ] 8.1 Implement MediaServerService
    - Create `services/media_server.py`
    - Implement add, update, remove, test_connection methods
    - Validate connection before persisting
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 8.2 Implement InvitationService
    - Create `services/invitation.py`
    - Implement create, validate, redeem methods
    - Check expiration, use count, enabled status on redemption
    - Return specific error reasons for validation failures
    - _Requirements: 6.4, 6.5, 6.6_

  - [ ] 8.3 Write property tests for services
    - **Property 10: Service Validates Before Persisting**
    - **Property 11: Invitation Validation Checks All Conditions**
    - **Validates: Requirements 6.3, 6.5, 6.6**

- [ ] 9. API Layer
  - [ ] 9.1 Implement API schemas
    - Create `api/schemas.py` with msgspec Structs
    - Define ErrorResponse, MediaServerCreate, MediaServerResponse, etc.
    - Use Meta annotations for validation constraints
    - _Requirements: 7.3, 9.1_

  - [ ] 9.2 Implement error handlers
    - Create `api/errors.py` with exception handlers
    - Handle ValidationError, NotFoundError, and generic exceptions
    - Include correlation IDs in responses and logs
    - Never expose internal details
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ] 9.3 Implement health controller
    - Create `api/health.py` with HealthController
    - Implement /health, /health/live, /health/ready endpoints
    - Check database connectivity for health status
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ] 9.4 Write property tests for health endpoints
    - **Property 12: Health Endpoints Return Correct Status**
    - **Validates: Requirements 8.4, 8.5, 8.6, 8.7**

  - [ ] 9.5 Write property tests for error handling
    - **Property 13: Error Responses Are Safe and Traceable**
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**

- [ ] 10. Application Factory
  - [ ] 10.1 Implement database module
    - Create `core/database.py` with engine creation and session factory
    - Implement lifespan context manager for connection pool
    - Implement session provider with commit/rollback
    - _Requirements: 7.5_

  - [ ] 10.2 Implement application factory
    - Create `app.py` with create_app() function
    - Configure dependency injection with Provide
    - Register media clients in registry
    - Configure OpenAPI with Swagger/Scalar plugins
    - Configure structlog plugin
    - Register exception handlers
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6, 7.7_

- [ ] 11. Database Migrations
  - [ ] 11.1 Initialize Alembic
    - Create `alembic.ini` and `migrations/env.py`
    - Configure for async SQLAlchemy
    - Support both SQLite and PostgreSQL
    - _Requirements: 10.1, 10.2_

  - [ ] 11.2 Create initial migration
    - Generate migration for all foundation tables
    - Include media_servers, libraries, invitations, identities, users
    - Include association tables
    - _Requirements: 10.3, 10.4_

  - [ ] 11.3 Write tests for migrations
    - **Property 14: Migrations Preserve Data**
    - Test migration and rollback
    - **Validates: Requirements 10.4, 10.5**

- [ ] 12. Final Checkpoint
  - Ensure all tests pass
  - Run `ruff check` and `ruff format`
  - Run `basedpyright` for type checking
  - Verify application starts with `granian zondarr.app:app --interface asgi`
  - Test health endpoints manually

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
