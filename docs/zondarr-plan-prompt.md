# zondarr — Media Server User Management System

## Overview

zondarr is a unified invitation and user management system for media servers. It enables server administrators to create invitation codes that grant users access to their Plex and Jellyfin libraries with configurable permissions, library restrictions, and expiration policies.

The application consists of a **Litestar API backend** served by **Granian** and a **SvelteKit frontend** running on **Bun**.

---

## Core Functionality

### Invitation System

The invitation system generates secure, time-limited codes that users redeem to gain access to configured media servers. Each invitation defines:

- **Code**: Cryptographically secure, 6-10 character alphanumeric string
- **Expiration**: When the invitation code itself expires (day/week/month/never)
- **Usage limits**: Single-use or unlimited redemptions
- **Duration**: How long the created user account remains active
- **Server targets**: Which media servers the invitation grants access to (supports multi-server)
- **Library restrictions**: Specific libraries the user can access, or all libraries
- **Permissions**: Downloads, live TV, camera upload, concurrent session limits

### User Management

Once users redeem invitations, administrators can:

- View all users across all connected servers with sync status
- Enable/disable user accounts (where supported by the platform)
- Revoke access (delete users from media servers)
- Modify permissions and library access post-creation
- Track invitation usage (which code created which user)
- Handle automatic expiration (disable or delete based on policy)

### Invitation Wizard System

Administrators can configure multi-step wizard flows that users must complete before and/or after account creation. Each invitation can optionally reference a pre-invite wizard and a post-invite wizard. Wizards are reusable—multiple invitations can share the same wizard configuration.

**Wizard structure:** A wizard is an ordered sequence of steps. Each step has a title, markdown body content (rendered from admin-authored markdown), and an interaction requirement that the user must satisfy before proceeding.

**Interaction types (modular, extensible):**

- **Click**: User must click designated elements within the rendered step content
- **Timer**: User must wait a configured duration before the "Next" button enables
- **Terms of Service**: User must check a checkbox to accept terms; the terms content is the step's markdown body
- **Text Input**: User must type a specific phrase (e.g., "I understand") into an input field; configurable target text and case sensitivity
- **Quiz**: User must answer one or more questions (multiple choice or true/false) and meet a configurable pass threshold (e.g., 80% correct)

Each interaction type is implemented as its own module on both backend (validation logic, schema) and frontend (Svelte component). New interaction types can be added by creating a new module without modifying the wizard engine.

**Markdown editor:** The admin UI includes a rich markdown editor for authoring step content. The editor supports live preview, common formatting toolbar, and renders identically to what users see during the join flow.

### Multi-Server Support

A single zondarr instance manages multiple media servers of different types. Invitations can target one or many servers, and users are tracked with their relationships to servers, invitations, and unified identities.

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend runtime | Bun |
| Frontend framework | Svelte 5 (Runes-only) + SvelteKit |
| Frontend language | TypeScript (strict mode) |
| Styling | UnoCSS (presetWind4 + presetShadcn + presetIcons + presetAnimations) |
| UI components | shadcn-svelte |
| Form handling | Superforms + Formsnap |
| Backend framework | Litestar |
| Backend server | Granian |
| Backend language | Python 3.14+ |
| Serialization | msgspec |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async |
| API contract | OpenAPI 3.1 with generated TypeScript client |

### Frontend Dependencies

| Package | Purpose |
|---------|---------|
| bits-ui | Headless UI primitives (used by shadcn-svelte) |
| mode-watcher | Dark mode management |
| @lucide/svelte | Icon library |
| svelte-sonner | Toast notifications |
| sveltekit-superforms | Form validation and handling |
| openapi-fetch | Type-safe API client |
| milkdown (or similar) | Markdown editor for admin wizard step authoring |
| markdown-it (or similar) | Markdown rendering in join flow |

---

## Architectural Principles

### Modularity as the Core Design Principle

Every layer of the application must be modular with clear separation of concerns:

- **One responsibility per file**: Each file handles a single concern
- **Feature-based organization**: Group by domain feature, not by technical layer
- **Explicit dependencies**: No implicit imports or global state
- **Interface-first design**: Define contracts (protocols/interfaces) before implementations

### Media Client Abstraction Layer

The media server integration layer is the most critical abstraction. It must support adding new media server platforms (Emby, Audiobookshelf, etc.) without modifying core business logic.

**Design requirements:**

1. **Protocol-based interface**: Define a `MediaClient` protocol specifying all operations (create user, delete user, list users, update permissions, set library access, enable/disable user)

2. **Platform-specific implementations**: Each media server type gets its own module directory containing:
   - Client implementation conforming to the protocol
   - Platform-specific data structures and mappings
   - API interaction logic
   - Permission translation layer (maps universal permissions to platform-specific)

3. **Registry pattern**: Media clients register themselves, allowing runtime discovery and instantiation based on server type configuration

4. **Capability declaration**: Each client declares what operations it supports (e.g., Plex cannot enable/disable users, only delete)

5. **Unified error handling**: Platform-specific errors translate to domain errors

**Directory structure for media clients:**

```
backend/src/zondarr/
├── media/
│   ├── __init__.py
│   ├── protocol.py          # MediaClient protocol definition
│   ├── registry.py          # Client registration and factory
│   ├── errors.py            # Domain-specific errors
│   ├── permissions.py       # Universal permission model
│   │
│   ├── plex/
│   │   ├── __init__.py
│   │   ├── client.py        # PlexClient implementation
│   │   ├── api.py           # Plex API interactions
│   │   ├── auth.py          # OAuth flow handling
│   │   ├── permissions.py   # Plex permission mapping
│   │   └── models.py        # Plex-specific data structures
│   │
│   ├── jellyfin/
│   │   ├── __init__.py
│   │   ├── client.py        # JellyfinClient implementation
│   │   ├── api.py           # Jellyfin API interactions
│   │   ├── permissions.py   # Jellyfin permission mapping
│   │   └── models.py        # Jellyfin-specific data structures
│   │
│   └── _template/           # Template for adding new platforms
│       └── ...
```

### Backend Architecture

**Layered structure with clear boundaries:**

1. **Controllers**: HTTP request/response handling, input validation, OpenAPI documentation
2. **Services**: Business logic, orchestration, transaction boundaries
3. **Repositories**: Data access abstraction, query building
4. **Domain models**: Core entities (msgspec Structs for DTOs, SQLAlchemy models for persistence)
5. **Media layer**: External media server integrations (as described above)

**Directory structure:**

```
backend/
├── src/
│   └── zondarr/
│       ├── __init__.py
│       ├── app.py               # Litestar application factory
│       ├── config.py            # Configuration management
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── invitations/
│       │   │   ├── __init__.py
│       │   │   ├── controller.py
│       │   │   ├── schemas.py   # Request/response DTOs
│       │   │   └── service.py
│       │   ├── users/
│       │   │   └── ...
│       │   ├── servers/
│       │   │   └── ...
│       │   ├── wizards/
│       │   │   ├── __init__.py
│       │   │   ├── controller.py
│       │   │   ├── schemas.py
│       │   │   └── service.py
│       │   └── auth/
│       │       └── ...
│       │
│       ├── wizard/
│       │   ├── __init__.py
│       │   ├── engine.py            # Wizard execution and step sequencing
│       │   ├── validation.py        # Server-side interaction validation
│       │   ├── interactions/
│       │   │   ├── __init__.py
│       │   │   ├── protocol.py      # InteractionValidator protocol
│       │   │   ├── registry.py      # Interaction type registration
│       │   │   ├── click.py
│       │   │   ├── timer.py
│       │   │   ├── tos.py
│       │   │   ├── text_input.py
│       │   │   └── quiz.py
│       │   └── _template/           # Template for adding new interaction types
│       │
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py        # SQLAlchemy models
│       │   └── repositories.py  # Data access layer
│       │
│       ├── media/
│       │   └── ... (as described above)
│       │
│       └── core/
│           ├── __init__.py
│           ├── database.py      # Database connection management
│           ├── security.py      # Password hashing, token generation
│           └── tasks.py         # Background task definitions
│
├── tests/
│   ├── conftest.py
│   ├── api/
│   ├── media/
│   └── domain/
│
├── pyproject.toml
└── .python-version
```

### Frontend Architecture

**Feature-based route organization with shared components:**

1. **Routes**: SvelteKit file-based routing with route groups for authenticated vs public areas
2. **Components**: shadcn-svelte UI components in `$lib/components/ui`, feature components alongside
3. **API client**: Generated from OpenAPI spec via openapi-typescript, consumed via openapi-fetch
4. **State**: Runes-based reactive state in `.svelte.ts` files, context for shared state within route trees
5. **Forms**: Superforms with Zod validation, Formsnap for shadcn-svelte integration

**Directory structure:**

```
frontend/
├── src/
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ui/              # shadcn-svelte components (owned, not dependency)
│   │   │   ├── markdown/        # Markdown editor and renderer components
│   │   │   ├── wizard/
│   │   │   │   ├── WizardShell.svelte       # Step sequencer, progress, navigation
│   │   │   │   ├── StepRenderer.svelte      # Renders markdown + delegates to interaction
│   │   │   │   └── interactions/
│   │   │   │       ├── ClickInteraction.svelte
│   │   │   │       ├── TimerInteraction.svelte
│   │   │   │       ├── TosInteraction.svelte
│   │   │   │       ├── TextInputInteraction.svelte
│   │   │   │       └── QuizInteraction.svelte
│   │   │   ├── invitations/     # Invitation-specific components
│   │   │   ├── users/           # User management components
│   │   │   └── servers/         # Server configuration components
│   │   │
│   │   ├── api/
│   │   │   ├── client.ts        # openapi-fetch client instance
│   │   │   ├── types.d.ts       # Generated from OpenAPI spec
│   │   │   └── index.ts         # Typed wrappers and utilities
│   │   │
│   │   ├── stores/              # Shared reactive state (.svelte.ts)
│   │   │
│   │   └── utils/
│   │
│   ├── routes/
│   │   ├── (public)/
│   │   │   ├── join/
│   │   │   │   └── [code]/      # Invitation redemption flow
│   │   │   └── +layout.svelte
│   │   │
│   │   ├── (admin)/
│   │   │   ├── +layout.svelte   # Auth guard, admin layout
│   │   │   ├── dashboard/
│   │   │   ├── invitations/
│   │   │   ├── users/
│   │   │   ├── servers/
│   │   │   └── wizards/         # Wizard builder (step editor, markdown editor, interaction config)
│   │   │
│   │   ├── api/                 # API proxy routes if needed
│   │   └── +layout.svelte       # Root layout with ModeWatcher
│   │
│   ├── app.css                  # UnoCSS entry point
│   ├── app.d.ts
│   └── hooks.server.ts
│
├── static/
├── uno.config.ts                # UnoCSS configuration
├── package.json
├── svelte.config.js
└── vite.config.ts
```

---

## Data Model

### Core Entities

**MediaServer**: Configured media server connection (type, URL, API credentials)

**Library**: Media library belonging to a server (synced from media server)

**Invitation**: Invitation code with configuration (expiry, permissions, target servers, target libraries, optional pre-invite wizard, optional post-invite wizard)

**User**: User account created via invitation (linked to media server user, tracks permissions)

**Identity**: Groups users across servers for unified management

**Wizard**: Reusable wizard configuration with a name, description, and ordered list of steps. Can be shared across invitations.

**WizardStep**: A single step within a wizard. Has a position/order, title, markdown body content, and an interaction configuration (type + type-specific settings stored as JSON).

### Relationships

- MediaServer has many Libraries
- MediaServer has many Users
- Invitation has many target MediaServers (many-to-many with usage tracking per server)
- Invitation has many allowed Libraries (many-to-many)
- Invitation has many Users (tracks which invitation created which user)
- Invitation optionally references one pre-invite Wizard and one post-invite Wizard
- Wizard has many ordered WizardSteps
- Identity has many Users (one user per server)

---

## Key User Flows

### Invitation Redemption (Jellyfin)

1. User navigates to `/join/{code}`
2. Frontend validates code via API (receives invitation config including wizard references)
3. If pre-invite wizard is configured: user completes all wizard steps in order, each step's interaction validated client-side and server-side before advancing
4. User fills registration form (username, password, email) using Superforms
5. Backend validates invitation, creates Jellyfin user via API
6. Backend applies library restrictions and permissions
7. Backend creates local User record linked to invitation
8. If post-invite wizard is configured: user completes post-invite wizard steps
9. User redirected to success page with server access instructions

### Invitation Redemption (Plex)

1. User navigates to `/join/{code}`
2. Frontend validates code via API (receives invitation config including wizard references)
3. If pre-invite wizard is configured: user completes all pre-invite wizard steps
4. User initiates Plex OAuth flow
5. After OAuth callback, backend retrieves user's Plex email
6. Backend invites user via `inviteFriend()` or `createExistingUser()` based on `plex_home` flag
7. Backend creates local User record
8. Background process handles invite acceptance and post-setup (view state sync, opt-out online sources)
9. If post-invite wizard is configured: user completes post-invite wizard steps

### User Expiration

1. Scheduled task runs periodically
2. Queries users past their expiration date
3. For each expired user:
   - If policy is "disable": Call media client disable (falls back to delete if unsupported)
   - If policy is "delete": Call media client delete
4. Update local database state

---

## API Design

RESTful JSON API with OpenAPI 3.1 documentation.

### Resource Structure

```
/api/v1/
├── auth/
│   ├── POST /login
│   └── POST /logout
│
├── invitations/
│   ├── GET /                    # List all
│   ├── POST /                   # Create
│   ├── GET /{id}                # Get details
│   ├── DELETE /{id}             # Delete
│   └── GET /validate/{code}     # Public: validate code
│
├── users/
│   ├── GET /                    # List all (with filters)
│   ├── GET /{id}                # Get details
│   ├── DELETE /{id}             # Delete from all servers
│   ├── POST /{id}/enable        # Enable
│   ├── POST /{id}/disable       # Disable
│   └── PATCH /{id}/permissions  # Update permissions
│
├── servers/
│   ├── GET /                    # List configured servers
│   ├── POST /                   # Add server
│   ├── DELETE /{id}             # Remove server
│   ├── POST /{id}/sync          # Sync users/libraries
│   └── GET /{id}/libraries      # List libraries
│
├── wizards/
│   ├── GET /                    # List all wizards
│   ├── POST /                   # Create wizard
│   ├── GET /{id}                # Get wizard with steps
│   ├── PUT /{id}                # Update wizard (full replacement of steps)
│   ├── DELETE /{id}             # Delete wizard
│   ├── POST /{id}/steps         # Add step to wizard
│   ├── PUT /{id}/steps/reorder  # Reorder steps
│   ├── PUT /{id}/steps/{stepId} # Update step (content, interaction config)
│   ├── DELETE /{id}/steps/{stepId} # Remove step
│   └── GET /interaction-types   # List available interaction types and their config schemas
│
└── join/
    ├── POST /{code}             # Public: redeem invitation
    └── POST /{code}/wizard/{wizardId}/steps/{stepId}/validate  # Public: validate step interaction
```

---

## Coding Guidelines

### Backend

Follow all patterns and conventions defined in `.augment/rules/backend-dev-pro.md`:

- Python 3.14+ features (deferred annotations, type parameter syntax, template strings where applicable)
- Litestar controller-based organization with dependency injection
- msgspec Structs for all DTOs with validation via Meta annotations
- SQLAlchemy 2.0 async patterns with explicit eager loading
- Granian deployment configuration
- basedpyright strict type checking
- ruff for linting and formatting

### Frontend

Follow all patterns and conventions defined in `.augment/rules/frontend-dev-pro.md`:

- Svelte 5 Runes-only (no legacy stores, `$:` statements, `export let`, or `<slot>`)
- SvelteKit with typed load functions and form actions
- TypeScript strict mode throughout
- Bun as runtime and package manager (use `bun --bun run dev` to ensure Bun runtime)
- UnoCSS with presetWind4, presetShadcn, presetIcons, and presetAnimations
- shadcn-svelte for UI components (components are owned code in `$lib/components/ui/`)
- Superforms + Formsnap for all form handling with Zod validation
- mode-watcher for dark mode support
- Generated API client from OpenAPI spec via openapi-typescript + openapi-fetch
- Biome for linting/formatting (or ESLint + Prettier if Biome's Svelte support is insufficient)

---

## Development Environment

### Prerequisites

- Python 3.14+
- Bun 1.2+
- uv (Python package manager)

### Running Locally

```bash
# Terminal 1: Backend
cd backend
uv run granian zondarr.app:app --reload

# Terminal 2: Frontend
cd frontend
bun --bun run dev
```

### Configuration Files

**Frontend uno.config.ts:**
- presetWind4 with reset preflight
- presetShadcn with neutral color scheme and `.dark` selector
- presetIcons for icon support
- presetAnimations for shadcn-svelte animations
- transformerVariantGroup for cleaner class syntax

**Frontend vite.config.ts:**
- UnoCSS plugin before sveltekit plugin
- svelteTesting plugin for Vitest

**Frontend svelte.config.js:**
- svelte-adapter-bun for production deployment

---

## Implementation Priority

### Phase 1: Foundation

1. Project scaffolding (monorepo structure, tooling configuration)
2. Database models and migrations
3. Media client protocol and registry
4. Basic Litestar app with health endpoint

### Phase 2: Jellyfin Integration

1. Jellyfin client implementation
2. Invitation CRUD API
3. Invitation redemption flow (Jellyfin)
4. User listing and sync

### Phase 3: Plex Integration

1. Plex client implementation with OAuth
2. Plex-specific invitation flow
3. Friend vs Home user handling

### Phase 4: Frontend Foundation & Core UI

1. SvelteKit project setup with shadcn-svelte, UnoCSS, and mode-watcher
2. API client generation pipeline (openapi-typescript + openapi-fetch)
3. Admin dashboard layout with dark mode and navigation
4. Invitation management UI (list, create, delete)
5. User management UI (list, permissions, enable/disable, delete)
6. Server management UI (add, remove, sync, library listing)
7. Public join flow with Superforms (Jellyfin registration, Plex OAuth)

### Phase 5: Wizard System

1. Backend wizard models, CRUD API, and step management
2. Interaction type protocol, registry, and built-in implementations (click, timer, tos, text input, quiz)
3. Server-side step validation endpoint
4. Markdown editor component for admin step authoring (toolbar, live preview, identical rendering to user-facing flow)
5. Frontend wizard shell component (step sequencer, progress indicator, navigation)
6. Frontend interaction components (one per type, modular)
7. Admin wizard builder UI (create wizard, drag-reorder steps, configure interactions per step)
8. Integration with invitation creation/editing (select pre-invite and post-invite wizards)
9. Wire wizard steps into public join flow (pre-invite and post-invite)

### Phase 6: Polish

1. Background tasks (expiration, sync)
2. Error handling and toast notifications (svelte-sonner)
3. Testing coverage
4. Documentation

---

## Non-Functional Requirements

- **Security**: All API endpoints (except public join/validate) require authentication
- **Performance**: User listing should handle 1000+ users with pagination
- **Reliability**: Media server sync should be idempotent and handle partial failures
- **Extensibility**: Adding a new media server type should require only adding a new module directory without touching core code
- **Accessibility**: shadcn-svelte components provide accessible defaults; maintain WCAG 2.1 AA compliance
