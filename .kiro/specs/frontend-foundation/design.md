# Design Document: Frontend Foundation & Core UI

## Overview

This design document describes the technical architecture for Phase 4 of Zondarr: the SvelteKit frontend foundation and core UI. The frontend provides an admin dashboard for managing invitations, users, and media servers, plus a public join flow for invitation redemption.

The design follows Svelte 5 Runes-only patterns, uses shadcn-svelte for UI components, and integrates with the existing Litestar backend via a type-safe API client generated from OpenAPI.

### Design Goals

1. **Type Safety**: Full TypeScript coverage with generated API types
2. **Performance**: Svelte 5's fine-grained reactivity and efficient rendering
3. **Accessibility**: WCAG 2.1 AA compliance via shadcn-svelte components
4. **Distinctive Aesthetics**: "Control Room" theme avoiding generic AI aesthetics
5. **Developer Experience**: Clear patterns, minimal boilerplate, testable components

### Aesthetic Direction: "Control Room"

The frontend adopts a **Control Room** aesthetic—inspired by mission control centers, server monitoring dashboards, and industrial control panels. This creates a distinctive, professional feel appropriate for media server administration.

**Typography**:
- Display/Headers: JetBrains Mono or IBM Plex Mono for technical authority
- Body: IBM Plex Sans for readability with technical character
- Data elements (codes, IDs, timestamps): Monospace with slightly reduced opacity

**Color Palette** (Dark-first):
- Background: Near-black (`#0a0a0b`) with subtle blue undertone
- Surface: Dark gray (`#141416`) for cards and elevated elements
- Border: Muted gray (`#27272a`) for subtle separation
- Primary accent: Electric cyan (`#22d3ee`) for interactive elements
- Status colors:
  - Active/Enabled: Emerald green (`#10b981`)
  - Pending/Limited: Amber (`#f59e0b`)
  - Disabled/Expired: Rose red (`#f43f5e`)
- Text: High contrast white (`#fafafa`) on dark backgrounds

**Visual Elements**:
- Card-based layouts with subtle borders and shadows
- Status indicator dots with subtle glow effects
- Monospace code displays with syntax-highlighting-inspired styling
- Subtle grid patterns or scan lines for background texture (optional)
- Smooth transitions (150-200ms) for state changes
- Skeleton loaders with subtle shimmer animation

**Anti-patterns to Avoid**:
- Inter, Roboto, or system fonts
- Purple/violet gradients
- Rounded "friendly" aesthetics
- Generic card shadows without purpose
- Overly colorful or playful elements

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SvelteKit Frontend                        │
├─────────────────────────────────────────────────────────────────┤
│  Routes                                                          │
│  ├── (admin)/          # Authenticated admin routes              │
│  │   ├── dashboard/    # Overview dashboard                      │
│  │   ├── invitations/  # Invitation CRUD                         │
│  │   ├── users/        # User management                         │
│  │   └── servers/      # Server management                       │
│  └── (public)/         # Public routes                           │
│      └── join/[code]/  # Invitation redemption flow              │
├─────────────────────────────────────────────────────────────────┤
│  $lib/                                                           │
│  ├── api/              # Generated types + client                │
│  ├── components/ui/    # shadcn-svelte components                │
│  ├── components/       # Feature components                      │
│  ├── stores/           # Reactive state (.svelte.ts)             │
│  └── utils/            # Utilities and helpers                   │
├─────────────────────────────────────────────────────────────────┤
│  UnoCSS + shadcn-svelte + mode-watcher                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Litestar Backend API                         │
│  /api/v1/invitations, /api/v1/users, /api/v1/servers, /api/v1/join │
└─────────────────────────────────────────────────────────────────┘
```

### Route Groups

The application uses SvelteKit route groups to separate authenticated and public areas:

- `(admin)`: Protected routes requiring authentication, share admin layout
- `(public)`: Public routes for invitation redemption, minimal layout

### State Management Strategy

Following Svelte 5 patterns:

1. **Component State**: `$state()` for local reactive state
2. **Derived Values**: `$derived()` for computed values
3. **Props**: `$props()` for component inputs
4. **Context**: `setContext`/`getContext` for shared state within route trees
5. **URL State**: `$page.url.searchParams` for shareable filter/sort state

## Components and Interfaces

### API Client Architecture

```typescript
// $lib/api/client.ts
import createClient from 'openapi-fetch';
import type { paths } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const api = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Typed wrapper functions for common operations
export async function getInvitations(params: {
  page?: number;
  page_size?: number;
  enabled?: boolean;
  expired?: boolean;
  sort_by?: string;
  sort_order?: string;
}) {
  return api.GET('/api/v1/invitations', { params: { query: params } });
}

export async function createInvitation(data: paths['/api/v1/invitations']['post']['requestBody']['content']['application/json']) {
  return api.POST('/api/v1/invitations', { body: data });
}

// ... additional typed wrappers
```

### Component Hierarchy

```
App
├── ModeWatcher (dark mode)
├── Toaster (svelte-sonner)
└── Routes
    ├── (admin)/+layout.svelte
    │   ├── Sidebar
    │   │   ├── NavItem (Dashboard)
    │   │   ├── NavItem (Invitations)
    │   │   ├── NavItem (Users)
    │   │   └── NavItem (Servers)
    │   ├── Header
    │   │   ├── PageTitle
    │   │   └── ThemeToggle
    │   └── Main Content Area
    │       └── {children}
    │
    ├── (admin)/invitations/+page.svelte
    │   ├── InvitationFilters
    │   ├── InvitationTable
    │   │   └── InvitationRow (per item)
    │   │       └── StatusBadge
    │   ├── Pagination
    │   └── CreateInvitationDialog
    │       └── InvitationForm
    │
    ├── (admin)/users/+page.svelte
    │   ├── UserFilters
    │   ├── UserTable
    │   │   └── UserRow (per item)
    │   │       └── StatusBadge
    │   └── Pagination
    │
    ├── (admin)/servers/+page.svelte
    │   ├── ServerCard (per server)
    │   │   ├── ServerInfo
    │   │   ├── LibraryList
    │   │   └── SyncButton
    │   └── SyncResultsDialog
    │
    └── (public)/join/[code]/+page.svelte
        ├── CodeValidation
        ├── ServerInfo
        ├── JellyfinRegistrationForm
        ├── PlexOAuthFlow
        └── SuccessPage
```

### Key Component Interfaces

```typescript
// StatusBadge.svelte
interface StatusBadgeProps {
  status: 'active' | 'pending' | 'disabled' | 'expired';
  label?: string;
}

// InvitationRow.svelte
interface InvitationRowProps {
  invitation: InvitationResponse;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

// UserRow.svelte
interface UserRowProps {
  user: UserDetailResponse;
  onEnable: (id: string) => void;
  onDisable: (id: string) => void;
  onDelete: (id: string) => void;
}

// Pagination.svelte
interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}
```

### Form Handling Pattern

Using Superforms + Formsnap with Zod validation:

```typescript
// $lib/schemas/invitation.ts
import { z } from 'zod';

export const createInvitationSchema = z.object({
  server_ids: z.array(z.string().uuid()).min(1, 'Select at least one server'),
  code: z.string().min(1).max(20).optional(),
  expires_at: z.string().datetime().optional(),
  max_uses: z.number().int().positive().optional(),
  duration_days: z.number().int().positive().optional(),
  library_ids: z.array(z.string().uuid()).optional(),
});

export type CreateInvitationInput = z.infer<typeof createInvitationSchema>;
```

```svelte
<!-- InvitationForm.svelte -->
<script lang="ts">
  import * as Form from "$lib/components/ui/form";
  import { superForm } from 'sveltekit-superforms';
  import { zodClient } from 'sveltekit-superforms/adapters';
  import { createInvitationSchema } from '$lib/schemas/invitation';

  let { data, onSuccess } = $props<{ data: any; onSuccess: () => void }>();

  const form = superForm(data.form, {
    validators: zodClient(createInvitationSchema),
    onResult: ({ result }) => {
      if (result.type === 'success') onSuccess();
    },
  });
  const { form: formData, enhance, errors } = form;
</script>

<form method="POST" use:enhance>
  <Form.Field {form} name="server_ids">
    <Form.Control>
      {#snippet children({ props })}
        <Form.Label>Target Servers</Form.Label>
        <ServerMultiSelect {...props} bind:value={$formData.server_ids} />
      {/snippet}
    </Form.Control>
    <Form.FieldErrors />
  </Form.Field>
  <!-- Additional fields... -->
</form>
```

## Data Models

### API Response Types (Generated)

The following types are generated from the backend OpenAPI spec:

```typescript
// Generated from openapi-typescript
interface InvitationResponse {
  id: string;
  code: string;
  use_count: number;
  enabled: boolean;
  created_at: string;
  expires_at?: string;
  max_uses?: number;
  duration_days?: number;
  created_by?: string;
  updated_at?: string;
  is_active: boolean;
  remaining_uses?: number;
}

interface InvitationDetailResponse extends InvitationResponse {
  target_servers: MediaServerResponse[];
  allowed_libraries: LibraryResponse[];
}

interface InvitationListResponse {
  items: InvitationResponse[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

interface UserDetailResponse {
  id: string;
  identity_id: string;
  media_server_id: string;
  external_user_id: string;
  username: string;
  enabled: boolean;
  created_at: string;
  identity: IdentityResponse;
  media_server: MediaServerResponse;
  expires_at?: string;
  updated_at?: string;
  invitation_id?: string;
  invitation?: InvitationResponse;
}

interface UserListResponse {
  items: UserDetailResponse[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

interface MediaServerResponse {
  id: string;
  name: string;
  server_type: 'jellyfin' | 'plex';
  url: string;
  enabled: boolean;
  created_at: string;
  updated_at?: string;
}

interface LibraryResponse {
  id: string;
  name: string;
  library_type: string;
  external_id: string;
  created_at: string;
  updated_at?: string;
}

interface InvitationValidationResponse {
  valid: boolean;
  failure_reason?: string;
  target_servers?: MediaServerResponse[];
  allowed_libraries?: LibraryResponse[];
  duration_days?: number;
}

interface RedeemInvitationRequest {
  username: string;
  password: string;
  email?: string;
}

interface RedemptionResponse {
  success: boolean;
  identity_id: string;
  users_created: UserResponse[];
  message?: string;
}

interface PlexOAuthPinResponse {
  pin_id: number;
  code: string;
  auth_url: string;
  expires_at: string;
}

interface PlexOAuthCheckResponse {
  authenticated: boolean;
  email?: string;
  error?: string;
}

interface SyncResult {
  server_id: string;
  server_name: string;
  synced_at: string;
  orphaned_users: string[];
  stale_users: string[];
  matched_users: number;
}
```

### Frontend State Types

```typescript
// $lib/stores/filters.svelte.ts
interface InvitationFilters {
  enabled?: boolean;
  expired?: boolean;
  sort_by: 'created_at' | 'expires_at' | 'use_count';
  sort_order: 'asc' | 'desc';
  page: number;
  page_size: number;
}

interface UserFilters {
  server_id?: string;
  invitation_id?: string;
  enabled?: boolean;
  expired?: boolean;
  sort_by: 'created_at' | 'username' | 'expires_at';
  sort_order: 'asc' | 'desc';
  page: number;
  page_size: number;
}

// $lib/stores/join-flow.svelte.ts
interface JoinFlowState {
  step: 'validating' | 'validated' | 'registering' | 'oauth' | 'success' | 'error';
  validation?: InvitationValidationResponse;
  error?: string;
  plexPin?: PlexOAuthPinResponse;
  plexEmail?: string;
}
```

### Zod Validation Schemas

```typescript
// $lib/schemas/invitation.ts
import { z } from 'zod';

export const createInvitationSchema = z.object({
  server_ids: z.array(z.string().uuid()).min(1, 'Select at least one server'),
  code: z.string().min(1).max(20).regex(/^[a-zA-Z0-9]+$/, 'Code must be alphanumeric').optional().or(z.literal('')),
  expires_at: z.string().datetime().optional().or(z.literal('')),
  max_uses: z.coerce.number().int().positive().optional().or(z.literal('')),
  duration_days: z.coerce.number().int().positive().optional().or(z.literal('')),
  library_ids: z.array(z.string().uuid()).optional(),
});

export const updateInvitationSchema = z.object({
  expires_at: z.string().datetime().optional().nullable(),
  max_uses: z.coerce.number().int().positive().optional().nullable(),
  duration_days: z.coerce.number().int().positive().optional().nullable(),
  enabled: z.boolean().optional(),
  server_ids: z.array(z.string().uuid()).min(1).optional(),
  library_ids: z.array(z.string().uuid()).optional(),
});

// $lib/schemas/join.ts
export const jellyfinRegistrationSchema = z.object({
  username: z.string()
    .min(3, 'Username must be at least 3 characters')
    .max(32, 'Username must be at most 32 characters')
    .regex(/^[a-z][a-z0-9_]*$/, 'Username must start with a letter and contain only lowercase letters, numbers, and underscores'),
  password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .max(128, 'Password must be at most 128 characters'),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
});
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following properties have been identified for property-based testing:

### Property 1: API Client Type Coverage

*For any* endpoint defined in the OpenAPI specification, the generated TypeScript types SHALL provide typed request and response objects that match the specification schema.

**Validates: Requirements 2.2**

### Property 2: API Client Authentication Headers

*For any* API request to a protected endpoint, the API client SHALL automatically include authentication headers in the request.

**Validates: Requirements 2.3**

### Property 3: API Error Transformation

*For any* API error response with an error_code and detail field, the API client SHALL transform it into a structured error object containing both fields.

**Validates: Requirements 2.4, 2.5**

### Property 4: Pagination Parameter Passing

*For any* list endpoint call with page and page_size parameters, the API client SHALL correctly pass these parameters to the backend and the page_size SHALL be capped at 100.

**Validates: Requirements 2.6, 4.7, 7.6**

### Property 5: Filter Parameter Passing

*For any* filter parameter (enabled, expired, server_id, invitation_id) passed to list endpoints, the API client SHALL correctly include the parameter in the request query string.

**Validates: Requirements 2.7**

### Property 6: Route Title Display

*For any* admin route (dashboard, invitations, users, servers), the header SHALL display the correct section title corresponding to the current route.

**Validates: Requirements 3.2**

### Property 7: Dark Mode Persistence

*For any* dark mode preference set by the user, the preference SHALL be persisted to localStorage and restored on subsequent page loads.

**Validates: Requirements 3.4**

### Property 8: Responsive Sidebar Collapse

*For any* viewport width below the mobile breakpoint (768px), the sidebar navigation SHALL collapse into a mobile-friendly menu.

**Validates: Requirements 3.5**

### Property 9: Invitation Field Display

*For any* invitation in the list view, the rendered output SHALL contain the code, use_count, max_uses (if set), expires_at (if set), enabled status, and is_active computed status.

**Validates: Requirements 4.2**

### Property 10: Invitation Filter Application

*For any* combination of enabled and expired filter values, the invitation list SHALL only display invitations matching the filter criteria.

**Validates: Requirements 4.3**

### Property 11: Invitation Sort Application

*For any* sort_by value (created_at, expires_at, use_count) and sort_order (asc, desc), the invitation list SHALL be ordered according to the specified sort parameters.

**Validates: Requirements 4.4**

### Property 12: Status Badge Color Mapping

*For any* status value (active/enabled → green, pending/limited → amber, disabled/expired → red), the StatusBadge component SHALL apply the correct color class.

**Validates: Requirements 4.5, 7.5, 13.4**

### Property 13: Remaining Uses Display

*For any* invitation with a non-null remaining_uses value, the invitation display SHALL show the remaining count.

**Validates: Requirements 4.6**

### Property 14: Form Validation Error Display

*For any* form field with a validation error, the form SHALL display the error message inline below the field.

**Validates: Requirements 5.9, 14.3**

### Property 15: Invitation Detail Field Display

*For any* invitation in the detail view, the rendered output SHALL contain all fields including target_servers array and allowed_libraries array.

**Validates: Requirements 6.2**

### Property 16: Immutable Field Protection

*For any* immutable invitation field (code, use_count, created_at, created_by), the detail view form SHALL render the field as read-only and not include it in the update payload.

**Validates: Requirements 6.4**

### Property 17: User Field Display

*For any* user in the list view, the rendered output SHALL contain username, media_server name, enabled status, expires_at (if set), and created_at.

**Validates: Requirements 7.2**

### Property 18: User Filter Application

*For any* combination of server_id, invitation_id, enabled, and expired filter values, the user list SHALL only display users matching all specified filter criteria.

**Validates: Requirements 7.3**

### Property 19: User Sort Application

*For any* sort_by value (created_at, username, expires_at) and sort_order (asc, desc), the user list SHALL be ordered according to the specified sort parameters.

**Validates: Requirements 7.4**

### Property 20: User Invitation Code Display

*For any* user with a non-null invitation relationship, the user display SHALL show the source invitation code.

**Validates: Requirements 7.7**

### Property 21: User Detail Relationship Display

*For any* user in the detail view, the rendered output SHALL contain the identity information, media_server information, and source invitation (if available).

**Validates: Requirements 8.2**

### Property 22: Linked Users Display

*For any* user detail view, the parent identity section SHALL display all users linked to that identity across all servers.

**Validates: Requirements 8.3**

### Property 23: Enable Button Visibility

*For any* user with enabled=false, the detail view SHALL display an Enable button and NOT display a Disable button.

**Validates: Requirements 8.4**

### Property 24: Disable Button Visibility

*For any* user with enabled=true, the detail view SHALL display a Disable button and NOT display an Enable button.

**Validates: Requirements 8.5**

### Property 25: Server Field Display

*For any* server in the list view, the rendered output SHALL contain name, server_type, url, enabled status, and library count.

**Validates: Requirements 9.2**

### Property 26: Sync Result Display

*For any* sync result, the rendered output SHALL contain orphaned_users array, stale_users array, and matched_users count.

**Validates: Requirements 9.6**

### Property 27: Valid Code Display

*For any* valid invitation code, the validation page SHALL display the target_servers and allowed_libraries from the validation response.

**Validates: Requirements 10.2**

### Property 28: Invalid Code Error Display

*For any* invalid invitation code with a failure_reason (not_found, disabled, expired, max_uses_reached), the validation page SHALL display a user-friendly error message corresponding to the failure reason.

**Validates: Requirements 10.3**

### Property 29: Duration Display

*For any* valid invitation with a non-null duration_days value, the validation page SHALL display the duration indicating how long access will last.

**Validates: Requirements 10.4**

### Property 30: Username Validation

*For any* username string, the Zod schema SHALL reject usernames that are less than 3 characters, more than 32 characters, don't start with a lowercase letter, or contain characters other than lowercase letters, numbers, and underscores.

**Validates: Requirements 11.2**

### Property 31: Password Validation

*For any* password string shorter than 8 characters, the Zod schema SHALL reject it with an appropriate error message.

**Validates: Requirements 11.3**

### Property 32: Plex OAuth Polling

*For any* Plex OAuth flow, the frontend SHALL poll the PIN status endpoint at regular intervals until either authenticated=true is returned or the PIN expires_at time is reached.

**Validates: Requirements 12.4**

### Property 33: Monospace Font Application

*For any* data element displaying codes, IDs, or timestamps, the element SHALL have a monospace font-family applied.

**Validates: Requirements 13.3**

### Property 34: Accessibility Compliance

*For any* interactive element, the element SHALL have appropriate ARIA attributes and keyboard navigation support to meet WCAG 2.1 AA compliance.

**Validates: Requirements 13.8**

### Property 35: Loading State Display

*For any* data fetching operation, the UI SHALL display a skeleton loader or loading spinner while the request is pending.

**Validates: Requirements 14.1**

### Property 36: API Error Toast Display

*For any* failed API request, the UI SHALL display a toast notification containing the error message from the response.

**Validates: Requirements 14.2**

### Property 37: Confirmation Dialog Display

*For any* destructive action (delete invitation, delete user), the UI SHALL display a confirmation dialog before executing the action.

**Validates: Requirements 14.4**

### Property 38: Empty State Display

*For any* list view with zero items, the UI SHALL display an empty state message with helpful guidance.

**Validates: Requirements 14.6**

## Error Handling

### API Error Handling Strategy

```typescript
// $lib/api/errors.ts
import type { ErrorResponse } from './types';

export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly errorCode: string,
    public readonly detail: string,
    public readonly correlationId?: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }

  static fromResponse(status: number, body: ErrorResponse): ApiError {
    return new ApiError(
      status,
      body.error_code,
      body.detail,
      body.correlation_id,
    );
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}

export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError && error.message.includes('fetch');
}
```

### Error Handling in Components

```svelte
<!-- Example: InvitationList.svelte -->
<script lang="ts">
  import { toast } from 'svelte-sonner';
  import { getErrorMessage, isNetworkError } from '$lib/api/errors';

  let loading = $state(true);
  let error = $state<string | null>(null);
  let invitations = $state<InvitationResponse[]>([]);

  async function loadInvitations() {
    loading = true;
    error = null;

    try {
      const { data, error: apiError } = await getInvitations(filters);
      if (apiError) {
        throw ApiError.fromResponse(apiError.status, apiError.body);
      }
      invitations = data.items;
    } catch (e) {
      error = getErrorMessage(e);
      if (isNetworkError(e)) {
        toast.error('Network error. Please check your connection.');
      } else {
        toast.error(error);
      }
    } finally {
      loading = false;
    }
  }
</script>

{#if loading}
  <InvitationListSkeleton />
{:else if error}
  <ErrorState message={error} onRetry={loadInvitations} />
{:else if invitations.length === 0}
  <EmptyState
    title="No invitations yet"
    description="Create your first invitation to start onboarding users."
    action={{ label: 'Create Invitation', onClick: openCreateDialog }}
  />
{:else}
  <InvitationTable {invitations} />
{/if}
```

### Form Error Handling

```svelte
<!-- Form with Superforms error handling -->
<script lang="ts">
  import { superForm } from 'sveltekit-superforms';
  import { zodClient } from 'sveltekit-superforms/adapters';
  import { toast } from 'svelte-sonner';

  const form = superForm(data.form, {
    validators: zodClient(schema),
    onError: ({ result }) => {
      // Server-side validation errors
      if (result.type === 'failure') {
        toast.error('Please fix the errors below');
      }
    },
    onResult: ({ result }) => {
      if (result.type === 'success') {
        toast.success('Invitation created successfully');
      }
    },
  });
</script>
```

### Validation Error Codes

| Error Code | User Message | Context |
|------------|--------------|---------|
| `VALIDATION_ERROR` | "Please fix the errors below" | Form validation failed |
| `NOT_FOUND` | "The requested resource was not found" | 404 response |
| `USERNAME_TAKEN` | "This username is already taken. Please choose another." | Redemption |
| `SERVER_ERROR` | "Failed to connect to {server_name}" | Media server operation |
| `SERVER_UNREACHABLE` | "Media server is unreachable" | Sync operation |
| `INVALID_INVITATION` | "This invitation is no longer valid" | Redemption |

## Testing Strategy

### Dual Testing Approach

The frontend uses both unit tests and property-based tests for comprehensive coverage:

1. **Unit Tests (Vitest + Testing Library)**: Specific examples, edge cases, integration points
2. **Property Tests (fast-check)**: Universal properties across generated inputs

### Testing Framework Configuration

```typescript
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import UnoCSS from 'unocss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [UnoCSS(), sveltekit(), svelteTesting()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest-setup.ts'],
    include: ['src/**/*.{test,spec}.{js,ts}', 'src/**/*.svelte.{test,spec}.ts'],
  },
});
```

### Property-Based Testing with fast-check

```typescript
// src/lib/components/StatusBadge.svelte.test.ts
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/svelte';
import StatusBadge from './StatusBadge.svelte';

describe('StatusBadge', () => {
  // Feature: frontend-foundation, Property 12: Status Badge Color Mapping
  it('should apply correct color class for any status value', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant('active'),
          fc.constant('enabled'),
          fc.constant('pending'),
          fc.constant('limited'),
          fc.constant('disabled'),
          fc.constant('expired'),
        ),
        (status) => {
          const { container } = render(StatusBadge, { props: { status } });
          const badge = container.querySelector('[data-status-badge]');

          if (status === 'active' || status === 'enabled') {
            expect(badge?.classList.contains('bg-green-500')).toBe(true);
          } else if (status === 'pending' || status === 'limited') {
            expect(badge?.classList.contains('bg-amber-500')).toBe(true);
          } else {
            expect(badge?.classList.contains('bg-red-500')).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
```

### Unit Test Examples

```typescript
// src/lib/schemas/join.test.ts
import { describe, it, expect } from 'vitest';
import { jellyfinRegistrationSchema } from './join';

describe('jellyfinRegistrationSchema', () => {
  it('should accept valid username', () => {
    const result = jellyfinRegistrationSchema.safeParse({
      username: 'john_doe',
      password: 'securepass123',
    });
    expect(result.success).toBe(true);
  });

  it('should reject username starting with number', () => {
    const result = jellyfinRegistrationSchema.safeParse({
      username: '1john',
      password: 'securepass123',
    });
    expect(result.success).toBe(false);
  });

  it('should reject password shorter than 8 characters', () => {
    const result = jellyfinRegistrationSchema.safeParse({
      username: 'john',
      password: 'short',
    });
    expect(result.success).toBe(false);
  });
});
```

### Component Testing Pattern

```typescript
// src/routes/(admin)/invitations/+page.svelte.test.ts
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import InvitationsPage from './+page.svelte';

describe('Invitations Page', () => {
  it('should display loading skeleton while fetching', async () => {
    render(InvitationsPage, { props: { data: { invitations: null } } });
    expect(screen.getByTestId('invitation-skeleton')).toBeInTheDocument();
  });

  it('should display empty state when no invitations', async () => {
    render(InvitationsPage, {
      props: { data: { invitations: { items: [], total: 0 } } }
    });
    expect(screen.getByText(/no invitations yet/i)).toBeInTheDocument();
  });

  it('should open create dialog on button click', async () => {
    const user = userEvent.setup();
    render(InvitationsPage, {
      props: { data: { invitations: { items: [], total: 0 } } }
    });

    await user.click(screen.getByRole('button', { name: /create invitation/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
```

### Test Configuration Requirements

- Minimum 100 iterations per property test
- Each property test references its design document property number
- Tag format: `Feature: frontend-foundation, Property {number}: {property_text}`

### Test File Organization

```
frontend/src/
├── lib/
│   ├── api/
│   │   └── client.test.ts           # API client unit tests
│   ├── components/
│   │   └── StatusBadge.svelte.test.ts  # Component property tests
│   ├── schemas/
│   │   └── join.test.ts             # Schema validation tests
│   └── stores/
│       └── filters.svelte.test.ts   # Store tests
└── routes/
    ├── (admin)/
    │   ├── invitations/
    │   │   └── +page.svelte.test.ts
    │   └── users/
    │       └── +page.svelte.test.ts
    └── (public)/
        └── join/
            └── [code]/
                └── +page.svelte.test.ts
```
