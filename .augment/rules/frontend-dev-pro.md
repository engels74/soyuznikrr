---
type: "agent_requested"
description: "Svelte 5 + SvelteKit + Bun coding guidelines"
---

# Comprehensive Svelte 5 + SvelteKit + Bun coding guidelines

Modern frontend development with **Svelte 5**, **SvelteKit**, and **Bun** represents a paradigm shift toward signal-based reactivity, file-based routing, and native performance. This guide covers bleeding-edge patterns for greenfield projects in 2025/2026, focusing exclusively on **Runes-only** Svelte 5, Bun-native APIs where beneficial, and TypeScript strict mode throughout. Legacy stores, `$:` reactive statements, and `export let` are deliberately omitted—they belong to Svelte 4.

---

## The Svelte 5 Runes system fundamentally changes reactivity

Svelte 5 introduces **Runes**—a signal-based reactivity system that replaces Svelte 4's compile-time magic with explicit, composable primitives. The key insight: reactivity is now **opt-in** via function-like syntax (`$state`, `$derived`, `$effect`) rather than implicit through variable declarations.

### $state declares reactive variables with deep proxy behavior

The `$state` rune creates reactive state that automatically tracks mutations:

```svelte
<script lang="ts">
  // Basic reactive state
  let count = $state(0);
  
  // Objects and arrays become deeply reactive proxies
  let todos = $state([
    { done: false, text: 'Learn Svelte 5' }
  ]);
  
  // Mutations trigger granular updates
  function complete() {
    todos[0].done = true; // This works!
    todos.push({ done: false, text: 'New task' }); // This too!
  }
</script>
```

**Deep reactivity** means arrays and plain objects are recursively proxified. The proxy stops at class instances and `Object.create(null)` objects.

For **large, read-only data** where you don't need mutation tracking, use `$state.raw()`:

```typescript
// No proxy overhead—must reassign to trigger updates
let largeDataset = $state.raw(fetchedData);

// Update by reassignment, not mutation
largeDataset = [...largeDataset, newItem];
```

Use `$state.snapshot()` to extract a plain object from reactive state (useful for sending to external APIs that can't handle proxies):

```typescript
const plainObject = $state.snapshot(reactiveObject);
console.log(plainObject); // No Proxy wrapper
```

### $derived computes values with automatic dependency tracking

Replace Svelte 4's `$: doubled = count * 2` with:

```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2); // Memoized, lazy evaluation
  
  // For complex multi-statement derivations, use $derived.by()
  let total = $derived.by(() => {
    let sum = 0;
    for (const item of items) {
      sum += item.price * item.quantity;
    }
    return sum;
  });
</script>
```

**Key characteristics**: `$derived` values are memoized (recalculated only when dependencies change) and use **push-pull reactivity**—they're notified immediately but evaluated lazily.

**Svelte 5.25+ feature**: You can temporarily override derived values for optimistic UI:

```svelte
<script lang="ts">
  let { post, like } = $props();
  let likes = $derived(post.likes);
  
  async function onclick() {
    likes += 1; // Optimistic update
    try {
      await like();
    } catch {
      likes -= 1; // Rollback on failure
    }
  }
</script>
```

### $effect handles side effects with automatic cleanup

Effects run after the DOM updates and automatically re-run when their dependencies change:

```svelte
<script lang="ts">
  let size = $state(50);
  let canvas: HTMLCanvasElement;

  $effect(() => {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillRect(0, 0, size, size);
    
    // Return cleanup function (runs before re-run or unmount)
    return () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  });
</script>
```

**Critical rule**: Effects track values read **synchronously**. Values read after `await` or inside `setTimeout` are not tracked. Use `untrack()` to explicitly exclude dependencies.

**Effect variants**:
- `$effect.pre()` — runs before DOM updates (useful for scroll position preservation)
- `$effect.root()` — creates an untracked effect scope with manual cleanup
- `$effect.tracking()` — returns `true` if currently in a tracking context

### $props replaces export let with explicit typing

```svelte
<script lang="ts">
  interface Props {
    name: string;
    count?: number;
    onupdate: (value: number) => void;
  }
  
  let { name, count = 0, onupdate }: Props = $props();
</script>
```

**Rest props** for wrapper components:

```svelte
<script lang="ts">
  import type { HTMLButtonAttributes } from 'svelte/elements';
  
  let { children, ...rest }: HTMLButtonAttributes = $props();
</script>

<button {...rest}>
  {@render children?.()}
</button>
```

### $bindable enables two-way binding (opt-in only)

Props are **not bindable by default** in Svelte 5. Declare bindable props explicitly:

```svelte
<!-- FancyInput.svelte -->
<script lang="ts">
  let { value = $bindable(''), ...props } = $props();
</script>

<input bind:value={value} {...props} />
```

```svelte
<!-- Parent.svelte -->
<FancyInput bind:value={message} />
```

### Snippets replace slots with typed, composable templates

Svelte 5 replaces `<slot>` with **snippets**—first-class template fragments:

```svelte
<!-- Table.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props<T> {
    data: T[];
    header: Snippet;
    row: Snippet<[T]>;
  }
  
  let { data, header, row }: Props<T> = $props();
</script>

<table>
  <thead><tr>{@render header()}</tr></thead>
  <tbody>
    {#each data as item}
      <tr>{@render row(item)}</tr>
    {/each}
  </tbody>
</table>
```

```svelte
<!-- Usage -->
<Table {data}>
  {#snippet header()}
    <th>Name</th><th>Price</th>
  {/snippet}
  
  {#snippet row(item)}
    <td>{item.name}</td><td>${item.price}</td>
  {/snippet}
</Table>
```

**Implicit `children` snippet** for simple content projection:

```svelte
<!-- Button.svelte -->
<script lang="ts">
  let { children } = $props();
</script>

<button>{@render children()}</button>
```

### Creating reusable reactive primitives (composables)

Use `.svelte.ts` files to create reactive modules:

```typescript
// counter.svelte.ts
export function createCounter(initial = 0) {
  let count = $state(initial);
  
  return {
    get value() { return count; }, // Getter preserves reactivity
    increment() { count += 1; },
    reset() { count = initial; }
  };
}
```

**Class-based pattern**:

```typescript
// Counter.svelte.ts
export class Counter {
  count = $state(0);
  doubled = $derived(this.count * 2);
  
  increment() {
    this.count += 1;
  }
}
```

---

## SvelteKit routing and data loading architecture

### File-based routing with typed conventions

SvelteKit routes are defined by the filesystem inside `src/routes/`:

```
src/routes/
├── +page.svelte           # / (home page)
├── +layout.svelte         # Root layout
├── blog/
│   ├── +page.svelte       # /blog
│   └── [slug]/            # Dynamic segment
│       ├── +page.svelte   # /blog/:slug
│       └── +page.server.ts
├── [[lang]]/              # Optional parameter
│   └── +page.svelte       # / or /:lang
├── files/[...path]/       # Rest/catch-all
│   └── +page.svelte       # /files/* (any depth)
└── (marketing)/           # Route group (no URL impact)
    ├── about/+page.svelte # /about
    └── +layout.svelte     # Shared layout for group
```

**Key conventions**:
- `[param]` — required dynamic parameter
- `[[param]]` — optional parameter
- `[...rest]` — catch-all (matches multiple segments)
- `(group)` — layout group without URL impact
- `+page@.svelte` — break out of layouts (reset to root)

### Universal vs server-only load functions

**Universal load** (`+page.ts`) runs on both server and client:

```typescript
// src/routes/blog/[slug]/+page.ts
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch, depends }) => {
  depends('app:posts'); // Register for invalidation
  
  const post = await fetch(`/api/posts/${params.slug}`).then(r => r.json());
  return { post };
};
```

**Server-only load** (`+page.server.ts`) for sensitive operations:

```typescript
// src/routes/dashboard/+page.server.ts
import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { db } from '$lib/server/database';

export const load: PageServerLoad = async ({ locals, cookies }) => {
  if (!locals.user) {
    error(401, 'Unauthorized');
  }
  
  return {
    dashboard: await db.getDashboard(locals.user.id)
  };
};
```

**When to use which**:
- **Universal** (`+page.ts`): External APIs, non-serializable data (components, class instances)
- **Server-only** (`+page.server.ts`): Database access, secrets, cookies, file system

### Parallel vs waterfall data fetching

```typescript
// ❌ WATERFALL — Sequential requests
export const load: PageLoad = async ({ fetch }) => {
  const user = await fetch('/api/user').then(r => r.json());
  const posts = await fetch(`/api/posts?userId=${user.id}`).then(r => r.json());
  return { user, posts };
};

// ✅ PARALLEL — Concurrent requests
export const load: PageLoad = async ({ fetch }) => {
  const [user, posts, comments] = await Promise.all([
    fetch('/api/user').then(r => r.json()),
    fetch('/api/posts').then(r => r.json()),
    fetch('/api/comments').then(r => r.json())
  ]);
  return { user, posts, comments };
};
```

### Streaming with deferred promises

Return promises without `await` to stream non-critical data:

```typescript
// +page.server.ts
export const load: PageServerLoad = async () => {
  return {
    critical: await getCriticalData(),    // Blocks render
    slowData: getSlowData(),              // Streams when ready
    analytics: fetchAnalytics()           // Also streams
  };
};
```

```svelte
<!-- +page.svelte -->
<h1>{data.critical.title}</h1>

{#await data.slowData}
  <Spinner />
{:then slowData}
  <div>{slowData.content}</div>
{/await}
```

### Cache invalidation with depends() and invalidate()

```typescript
// +page.server.ts
export const load: PageServerLoad = async ({ depends }) => {
  depends('app:posts');
  return { posts: await getPosts() };
};
```

```svelte
<script lang="ts">
  import { invalidate, invalidateAll } from '$app/navigation';
  
  // Invalidate specific dependency
  function refresh() {
    invalidate('app:posts');
  }
  
  // Invalidate by URL pattern
  function refreshUser() {
    invalidate(url => url.pathname.startsWith('/api/user'));
  }
</script>
```

---

## SvelteKit server features and progressive enhancement

### Form actions with use:enhance

```typescript
// +page.server.ts
import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions = {
  login: async ({ request, cookies }) => {
    const data = await request.formData();
    const email = data.get('email') as string;
    const password = data.get('password') as string;
    
    if (!email) {
      return fail(400, { email, missing: true });
    }
    
    const user = await authenticate(email, password);
    if (!user) {
      return fail(401, { email, incorrect: true });
    }
    
    cookies.set('session', user.token, { path: '/', httpOnly: true });
    redirect(303, '/dashboard');
  }
} satisfies Actions;
```

```svelte
<script lang="ts">
  import { enhance } from '$app/forms';
  import type { PageProps } from './$types';
  
  let { form }: PageProps = $props();
  let submitting = $state(false);
</script>

<form 
  method="POST" 
  action="?/login"
  use:enhance={() => {
    submitting = true;
    return async ({ update }) => {
      await update();
      submitting = false;
    };
  }}
>
  <input name="email" value={form?.email ?? ''} />
  {#if form?.missing}<span class="error">Email required</span>{/if}
  
  <button disabled={submitting}>
    {submitting ? 'Logging in...' : 'Log in'}
  </button>
</form>
```

### Server hooks for authentication and middleware

```typescript
// src/hooks.server.ts
import type { Handle, HandleFetch, HandleServerError } from '@sveltejs/kit';
import { sequence } from '@sveltejs/kit/hooks';

const auth: Handle = async ({ event, resolve }) => {
  const session = event.cookies.get('session');
  if (session) {
    event.locals.user = await getUserFromSession(session);
  }
  return resolve(event);
};

const protectedRoutes: Handle = async ({ event, resolve }) => {
  if (event.url.pathname.startsWith('/dashboard')) {
    if (!event.locals.user) {
      return new Response(null, { status: 303, headers: { Location: '/login' } });
    }
  }
  return resolve(event);
};

export const handle = sequence(auth, protectedRoutes);

export const handleError: HandleServerError = async ({ error, event }) => {
  console.error(error);
  return { message: 'An unexpected error occurred', errorId: crypto.randomUUID() };
};
```

### Rendering strategy configuration

| Strategy | Config | Use Case |
|----------|--------|----------|
| **SSR** (default) | `export const ssr = true` | SEO, dynamic content |
| **SSG** | `export const prerender = true` | Static content, blogs |
| **CSR** | `export const ssr = false` | Dashboards, browser-only APIs |

```typescript
// Per-route configuration (+page.ts or +layout.ts)
export const prerender = true;  // Static generation
export const ssr = false;       // Client-only
```

---

## Bun runtime integration and native APIs

### Bun-specific APIs for SvelteKit server code

Use these in `+server.ts`, `hooks.server.ts`, or `$lib/server/`:

```typescript
// File I/O (efficient, lazy loading)
const config = await Bun.file('./config.json').json();
await Bun.write('./output.json', JSON.stringify(data));

// Password hashing (built-in argon2id/bcrypt)
const hash = await Bun.password.hash(password);
const valid = await Bun.password.verify(password, hash);

// Environment variables
const apiKey = Bun.env.API_KEY;

// Glob patterns (3x faster than micromatch)
import { Glob } from 'bun';
const glob = new Glob('**/*.svelte');
for await (const file of glob.scan('./src')) {
  console.log(file);
}
```

### Building SvelteKit with adapter-bun

```bash
bun add -D svelte-adapter-bun
```

```javascript
// svelte.config.js
import adapter from 'svelte-adapter-bun';

export default {
  kit: {
    adapter: adapter({
      out: 'build',
      precompress: { brotli: true, gzip: true }
    })
  }
};
```

```bash
# Build (use --bun for bun:sqlite support)
bun --bun run vite build

# Run production
bun ./build/index.js
```

### bunfig.toml configuration

```toml
[install]
exact = true
saveTextLockfile = true

[test]
coverage = true
preload = ["./test/setup.ts"]

[run]
bun = true
```

---

## TypeScript strict mode configuration

### Complete tsconfig.json for SvelteKit

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true
  }
}
```

### Typing generic components

```svelte
<script lang="ts" generics="T extends { id: string }">
  interface Props {
    items: T[];
    onSelect: (item: T) => void;
  }
  
  let { items, onSelect }: Props = $props();
</script>

{#each items as item (item.id)}
  <button onclick={() => onSelect(item)}>{item.id}</button>
{/each}
```

### App.d.ts for global types

```typescript
// src/app.d.ts
declare global {
  namespace App {
    interface Locals {
      user: { id: string; email: string; role: 'admin' | 'user' } | null;
    }
    interface Error {
      message: string;
      errorId: string;
    }
    interface PageData {
      theme?: 'light' | 'dark';
    }
  }
}

export {};
```

---

## Type-safe API integration with openapi-fetch

```bash
npm i openapi-fetch
npm i -D openapi-typescript
npx openapi-typescript ./api/spec.yaml -o ./src/lib/api/types.d.ts
```

```typescript
// src/lib/api/client.ts
import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './types';

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  }
};

export const api = createClient<paths>({ baseUrl: '/api' });
api.use(authMiddleware);

// Usage with full type safety
const { data, error } = await api.GET('/posts/{id}', {
  params: { path: { id: '123' } }
});
```

---

## Form validation with Superforms

```bash
npm i sveltekit-superforms zod
```

```typescript
// +page.server.ts
import { superValidate } from 'sveltekit-superforms';
import { zod } from 'sveltekit-superforms/adapters';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
});

export const load = async () => {
  const form = await superValidate(zod(schema));
  return { form };
};

export const actions = {
  default: async ({ request }) => {
    const form = await superValidate(request, zod(schema));
    if (!form.valid) return fail(400, { form });
    // Process valid form.data
    return { form };
  }
};
```

```svelte
<script lang="ts">
  import { superForm } from 'sveltekit-superforms';
  import { zodClient } from 'sveltekit-superforms/adapters';
  
  let { data } = $props();
  const { form, errors, enhance } = superForm(data.form, {
    validators: zodClient(schema)
  });
</script>

<form method="POST" use:enhance>
  <input name="email" bind:value={$form.email} />
  {#if $errors.email}<span>{$errors.email}</span>{/if}
  <button>Submit</button>
</form>
```

---

## Testing Svelte 5 components with Vitest

### Configuration

```typescript
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit(), svelteTesting()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest-setup.ts'],
    include: ['src/**/*.{test,spec}.ts']
  }
});
```

### Testing Runes-based components

```typescript
// Counter.test.ts
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import Counter from './Counter.svelte';

test('increments count on click', async () => {
  const user = userEvent.setup();
  render(Counter, { props: { initial: 0 } });

  const button = screen.getByRole('button');
  expect(button).toHaveTextContent('0');

  await user.click(button);
  expect(button).toHaveTextContent('1');
});
```

### Testing .svelte.ts modules with flushSync

```typescript
// Use .svelte.test.ts extension for runes support
import { flushSync } from 'svelte';
import { expect, test } from 'vitest';
import { createCounter } from './counter.svelte.ts';

test('counter increments', () => {
  const counter = createCounter(0);
  expect(counter.value).toBe(0);
  
  counter.increment();
  flushSync(); // Flush pending reactive updates
  expect(counter.value).toBe(1);
});
```

---

## Styling with scoped CSS and Tailwind

### Scoped styles (default behavior)

```svelte
<style>
  /* Automatically scoped to this component */
  p { color: blue; }
  
  /* Escape scoping for children */
  div :global(strong) { color: red; }
</style>
```

### Tailwind CSS 4 setup (Vite plugin)

```bash
npm i -D @tailwindcss/vite
```

```typescript
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()]
});
```

```css
/* src/app.css */
@import 'tailwindcss';
```

---

## Image optimization with enhanced-img

```bash
npm i -D @sveltejs/enhanced-img
```

```typescript
// vite.config.ts
import { enhancedImages } from '@sveltejs/enhanced-img';

export default defineConfig({
  plugins: [enhancedImages(), sveltekit()]
});
```

```svelte
<!-- Automatic WebP/AVIF generation, responsive sizes, CLS prevention -->
<enhanced:img 
  src="$lib/assets/hero.jpg" 
  alt="Hero"
  sizes="(min-width: 768px) 50vw, 100vw"
/>
```

---

## Environment variables patterns

| Module | Access | Use Case |
|--------|--------|----------|
| `$env/static/private` | Server, build-time | API keys, DB URLs |
| `$env/static/public` | Client+Server, build-time | Public config (`PUBLIC_` prefix) |
| `$env/dynamic/private` | Server, runtime | Deployment secrets |
| `$env/dynamic/public` | Client+Server, runtime | Runtime feature flags |

```typescript
// Server-side only
import { DATABASE_URL } from '$env/static/private';

// Client-safe (must have PUBLIC_ prefix)
import { PUBLIC_API_URL } from '$env/static/public';
```

---

## Recommended project structure

```
src/
├── lib/
│   ├── components/       # Reusable UI components
│   ├── server/           # Server-only code ($lib/server)
│   │   ├── db/
│   │   └── api/
│   ├── utils/            # Utility functions
│   └── types/            # Shared TypeScript types
├── routes/
│   ├── (app)/            # Authenticated routes
│   │   ├── dashboard/
│   │   └── +layout.svelte
│   ├── (marketing)/      # Public routes
│   ├── api/              # API endpoints
│   └── +layout.svelte    # Root layout
├── app.css               # Global styles
├── app.d.ts              # App-level types
└── hooks.server.ts       # Server hooks
```

---

## Critical anti-patterns to avoid

### Runes anti-patterns

```typescript
// ❌ Using $effect for derived values
$effect(() => { doubled = count * 2; });

// ✅ Use $derived
let doubled = $derived(count * 2);
```

```typescript
// ❌ Returning state directly (loses reactivity)
function createStore() {
  let value = $state(0);
  return { value }; // Returns 0, not reactive
}

// ✅ Use getters
function createStore() {
  let value = $state(0);
  return { get value() { return value; } };
}
```

```typescript
// ❌ Mutating props you don't own
let { object } = $props();
object.count += 1; // Triggers ownership warning

// ✅ Use callbacks
let { object, onUpdate } = $props();
onUpdate(object.count + 1);
```

### SvelteKit anti-patterns

```typescript
// ❌ Module-level state (shared between requests on server)
let currentUser = $state(null);

// ✅ Use event.locals
export const load = async ({ locals }) => {
  return { user: locals.user };
};
```

```typescript
// ❌ Side effects in load functions
export const load = async () => {
  userStore.set(user); // Don't do this
};

// ✅ Return data, let components handle state
export const load = async () => {
  return { user };
};
```

### Testing anti-patterns

```typescript
// ❌ Not flushing reactive updates
count = 5;
expect(doubled).toBe(10); // May fail!

// ✅ Use flushSync
count = 5;
flushSync();
expect(doubled).toBe(10);
```

---

## Version requirements summary

| Feature | Minimum Version |
|---------|-----------------|
| Core Runes ($state, $derived, $effect) | Svelte 5.0 |
| $derived overrides (optimistic UI) | Svelte 5.25 |
| createContext() | Svelte 5.40 |
| PageProps/LayoutProps types | SvelteKit 2.16 |
| $app/state module | SvelteKit 2.12 |
| Bun runtime | 1.0+ (1.2+ recommended) |
| Tailwind CSS 4 Vite plugin | Tailwind 4.0 |

---

## Conclusion: Key principles for modern Svelte development

Building with Svelte 5, SvelteKit, and Bun requires embracing **signal-based reactivity** over implicit magic. Start every reactive variable with `$state`, compute derived values with `$derived` (not effects), and reserve `$effect` for true side effects like DOM manipulation and subscriptions.

**Load functions are your data layer**—use server-only loads for sensitive operations, universal loads for cacheable API calls, and streaming for non-critical data. Forms work without JavaScript when you use actions with `use:enhance` for progressive enhancement.

**Type everything strictly**: leverage SvelteKit's generated `$types`, define your `App` interfaces in `app.d.ts`, and use tools like `openapi-fetch` for end-to-end API type safety.

**Bun accelerates development** with faster installs, native password hashing, and efficient file I/O—but use standard APIs for client code and serverless deployments. The goal isn't to replace Node.js everywhere, but to leverage Bun where it provides clear benefits.

The patterns in this guide represent the cutting edge of frontend development in 2025/2026. They prioritize correctness, type safety, and performance over backwards compatibility—exactly what a greenfield Svelte 5 project demands.