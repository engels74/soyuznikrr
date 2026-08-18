---
type: "agent_requested"
description: "Svelte 5 + SvelteKit + Bun coding guidelines"
---

# Authoritative Coding Guidelines for Bun + Svelte 5 + SvelteKit (2025/2026)

**Svelte 5's Runes represent the most significant paradigm shift in frontend reactivity since React hooks**, moving from implicit compiler magic to explicit, fine-grained signals. This guide provides comprehensive, bleeding-edge patterns for greenfield projects using Bun, Svelte 5 (Runes-only), SvelteKit 2, UnoCSS with presetWind4/presetShadcn, and shadcn-svelte. All patterns assume the latest stable versions with no legacy compatibility concerns.

---

## Svelte 5 Runes: The new reactivity paradigm

Runes are function-like symbols prefixed with `$` that provide explicit compiler instructions for reactivity. Unlike Svelte 4's implicit reactivity, Runes work universally in `.svelte` components and `.svelte.ts` files, enabling truly portable reactive logic.

### `$state` — Reactive state declaration

```svelte
<script lang="ts">
  // Basic reactive state
  let count = $state(0);
  let user = $state<User | null>(null);

  // Deep reactivity (default) — mutations are tracked granularly
  let todos = $state([
    { done: false, text: 'learn runes' }
  ]);
  todos[0].done = true; // ✅ Triggers updates
  todos.push({ done: false, text: 'new item' }); // ✅ Works
</script>
```

**`$state.raw()`** disables deep reactivity for performance with large, immutable data:

```typescript
let data = $state.raw(largeDataset); // Requires full reassignment to trigger updates
data = [...data, newItem]; // ✅ Triggers update
```

**`$state.snapshot()`** extracts plain objects from reactive proxies for serialization or external libraries:

```typescript
console.log($state.snapshot(todos)); // Plain array, not Proxy
```

**Class-based state** enables encapsulated reactive logic:

```typescript
// counter.svelte.ts
export class Counter {
  count = $state(0);
  doubled = $derived(this.count * 2);
  increment = () => this.count++;
}
```

### `$derived` — Computed values with automatic memoization

```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2);

  // Complex derivations with $derived.by()
  let total = $derived.by(() => {
    let sum = 0;
    for (const item of items) sum += item.price;
    return sum;
  });
</script>
```

**Critical insight**: Derived values use push-pull reactivity—dependencies are notified immediately, but recalculation happens only when the value is read. This prevents wasteful computation.

### `$effect` — Side effects done right

```svelte
<script lang="ts">
  let canvas: HTMLCanvasElement;
  let size = $state(50);

  $effect(() => {
    const ctx = canvas.getContext('2d');
    ctx.fillRect(0, 0, size, size);

    // Cleanup function runs before re-execution and on destroy
    return () => ctx.clearRect(0, 0, canvas.width, canvas.height);
  });
</script>
```

**When to use `$effect`**: localStorage persistence, API calls on dependency changes, DOM interactions not handled by Svelte, third-party library integration. **Never use `$effect` to derive state**—use `$derived` instead.

### `$props` — Type-safe component props

```svelte
<script lang="ts">
  interface Props {
    name: string;
    count?: number;
    onClick: (e: MouseEvent) => void;
  }

  let { name, count = 0, onClick }: Props = $props();
</script>
```

**Generic components** use the `generics` attribute:

```svelte
<script lang="ts" generics="T extends { id: string }">
  let { items, onSelect }: { items: T[]; onSelect: (item: T) => void } = $props();
</script>
```

### `$bindable` — Explicit two-way binding

```svelte
<!-- Child.svelte -->
<script lang="ts">
  let { value = $bindable(0) }: { value: number } = $props();
</script>

<!-- Parent.svelte -->
<Child bind:value={count} />
```

Props are **not bindable by default** in Svelte 5—you must explicitly declare bindability.

---

## SvelteKit routing and data loading architecture

### File-based routing conventions

| File | Purpose | Execution |
|------|---------|-----------|
| `+page.svelte` | Page component | Server (SSR) + Client |
| `+page.ts` | Universal load | Server + Client |
| `+page.server.ts` | Server-only load + actions | Server only |
| `+layout.svelte` | Shared wrapper | Server + Client |
| `+server.ts` | REST endpoints | Server only |

**Route parameters**: `[param]` (required), `[[optional]]` (optional), `[...rest]` (catch-all)

**Route groups** with `(groupname)` organize layouts without affecting URLs:

```
src/routes/
├── (marketing)/
│   ├── +layout.svelte    → Marketing layout
│   └── about/+page.svelte → /about
├── (app)/
│   ├── +layout.svelte    → App layout
│   └── dashboard/+page.svelte → /dashboard
```

### Data loading patterns

**Universal load** (runs on server and client during navigation):

```typescript
// +page.ts
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch, depends }) => {
  depends('app:posts'); // Register for invalidation
  const posts = await fetch(`/api/posts/${params.slug}`).then(r => r.json());
  return { posts };
};
```

**Server-only load** (database access, secrets, cookies):

```typescript
// +page.server.ts
import type { PageServerLoad } from './$types';
import { error, redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ params, locals, cookies }) => {
  if (!locals.user) redirect(303, '/login');
  const post = await db.post.findUnique({ where: { slug: params.slug } });
  if (!post) error(404, 'Not found');
  return { post };
};
```

**Streaming** for non-essential data:

```typescript
export const load: PageServerLoad = async ({ params }) => {
  return {
    post: await db.post.findUnique({ where: { id: params.id } }), // Blocks render
    comments: db.comment.findMany({ where: { postId: params.id } }) // Streams in
  };
};
```

Consume with `{#await data.comments}` in the component.

### Form actions with progressive enhancement

```typescript
// +page.server.ts
import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
  create: async ({ request }) => {
    const formData = await request.formData();
    const title = formData.get('title');

    if (!title) return fail(400, { title, missing: true });

    await db.post.create({ data: { title } });
    redirect(303, '/posts');
  }
} satisfies Actions;
```

```svelte
<!-- +page.svelte -->
<script lang="ts">
  import { enhance } from '$app/forms';
  let { form } = $props();
  let submitting = $state(false);
</script>

<form method="POST" action="?/create" use:enhance={() => {
  submitting = true;
  return async ({ update }) => {
    await update();
    submitting = false;
  };
}}>
  <input name="title" value={form?.title ?? ''} />
  {#if form?.missing}<p class="error">Title required</p>{/if}
  <button disabled={submitting}>{submitting ? 'Saving...' : 'Create'}</button>
</form>
```

---

## Component patterns in Svelte 5

### Snippets replace slots entirely

```svelte
<!-- Table.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props<T> {
    data: T[];
    header: Snippet;
    row: Snippet<[T]>;
  }

  let { data, header, row }: Props<any> = $props();
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

**Usage with inline snippets**:

```svelte
<Table {data}>
  {#snippet header()}
    <th>Name</th><th>Price</th>
  {/snippet}

  {#snippet row(item)}
    <td>{item.name}</td><td>{item.price}</td>
  {/snippet}
</Table>
```

### Children content pattern

```svelte
<!-- Button.svelte -->
<script lang="ts">
  import type { Snippet } from 'svelte';
  let { children }: { children: Snippet } = $props();
</script>

<button>{@render children()}</button>

<!-- Usage -->
<Button>Click me</Button>
```

### Context API with reactive state

```typescript
// Parent.svelte
import { setContext } from 'svelte';
let counter = $state({ count: 0 });
setContext('counter', counter);

// Child.svelte
import { getContext } from 'svelte';
const counter = getContext<{ count: number }>('counter');
// counter.count is reactive!
```

---

## TypeScript integration

### tsconfig.json for strict Svelte 5

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "strict": true,
    "target": "ES2022",
    "moduleResolution": "bundler",
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "noUncheckedIndexedAccess": true
  }
}
```

### Typing load functions

```typescript
import type { PageLoad, PageServerLoad, LayoutLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ params }) => {
  return { post: await getPost(params.id) };
};

export const actions = {
  create: async ({ request }) => { /* ... */ }
} satisfies Actions;
```

### ComponentProps utility

```typescript
import type { ComponentProps } from 'svelte';
import Button from './Button.svelte';

type ButtonProps = ComponentProps<typeof Button>;
```

---

## Bun runtime integration

### Running SvelteKit with Bun

```bash
# Development (--bun forces Bun runtime instead of Node.js)
bun --bun run dev

# Production build
bun --bun run build
```

**Critical**: Without `--bun`, Vite's dev server uses Node.js even when invoked via `bun run`.

### svelte-adapter-bun for production

```javascript
// svelte.config.js
import adapter from 'svelte-adapter-bun';

export default {
  kit: {
    adapter: adapter({
      out: 'build',
      precompress: true
    })
  }
};
```

### Bun-native APIs worth using

| API | Use Case | Advantage |
|-----|----------|-----------|
| `Bun.file()` / `Bun.write()` | File operations | 3-6x faster, simpler API |
| `Bun.password` | Password hashing | Zero deps, auto worker threads |
| `bun:sqlite` | Embedded database | 3-6x faster than better-sqlite3 |
| `Bun.env` | Environment vars | Auto .env loading, no dotenv |

```typescript
// Password hashing
const hash = await Bun.password.hash('my-password'); // argon2id default
const valid = await Bun.password.verify('my-password', hash);

// SQLite
import { Database } from 'bun:sqlite';
const db = new Database('app.db');
db.exec('PRAGMA journal_mode = WAL');
```

### bunfig.toml configuration

```toml
[install]
exact = true
prefer = "offline"

[test]
preload = ["./tests/setup.ts"]
coverage = true
timeout = 5000
```

---

## UnoCSS with presetWind4 and presetShadcn

### Complete uno.config.ts

```typescript
import { defineConfig, presetWind4 } from 'unocss';
import presetIcons from '@unocss/preset-icons';
import presetAnimations from 'unocss-preset-animations';
import { presetShadcn } from 'unocss-preset-shadcn';
import transformerVariantGroup from '@unocss/transformer-variant-group';

export default defineConfig({
  presets: [
    presetWind4({ preflights: { reset: true } }),
    presetAnimations(),
    presetShadcn({ color: 'neutral', darkSelector: '.dark' }),
    presetIcons({ scale: 1.2 })
  ],
  transformers: [transformerVariantGroup()],
  content: {
    pipeline: {
      include: [
        /\.(vue|svelte|[jt]sx|html)($|\?)/,
        '(components|src)/**/*.{js,ts}' // Required for shadcn-svelte
      ]
    }
  }
});
```

### Vite integration

```typescript
// vite.config.ts
import { sveltekit } from '@sveltejs/kit/vite';
import UnoCSS from 'unocss/vite';

export default defineConfig({
  plugins: [UnoCSS(), sveltekit()]
});
```

### Dark mode with mode-watcher

```svelte
<!-- +layout.svelte -->
<script>
  import "../app.css";
  import { ModeWatcher } from "mode-watcher";
  let { children } = $props();
</script>

<ModeWatcher />
{@render children?.()}
```

---

## shadcn-svelte component library

### Installation and setup

```bash
pnpm dlx shadcn-svelte@latest init
pnpm dlx shadcn-svelte@latest add button dialog form
```

Components install to `$lib/components/ui/`—**you own the code**, not a dependency.

### Form components with Superforms + Formsnap

```svelte
<script lang="ts">
  import * as Form from "$lib/components/ui/form";
  import { superForm } from 'sveltekit-superforms';
  import { zodClient } from 'sveltekit-superforms/adapters';
  import { schema } from './schema';

  let { data } = $props();
  const form = superForm(data.form, { validators: zodClient(schema) });
  const { form: formData, enhance } = form;
</script>

<form method="POST" use:enhance>
  <Form.Field {form} name="email">
    <Form.Control>
      {#snippet children({ props })}
        <Form.Label>Email</Form.Label>
        <input {...props} bind:value={$formData.email} />
      {/snippet}
    </Form.Control>
    <Form.FieldErrors />
  </Form.Field>
</form>
```

### Key dependencies for Svelte 5 compatibility

```json
{
  "bits-ui": "latest",
  "mode-watcher": "latest",
  "@lucide/svelte": "latest",
  "svelte-sonner": "latest",
  "sveltekit-superforms": "latest"
}
```

---

## API integration with end-to-end type safety

### openapi-typescript + openapi-fetch

```bash
npx openapi-typescript ./api/openapi.yaml -o ./src/lib/api/types.d.ts
npm i openapi-fetch
```

```typescript
// src/lib/api/client.ts
import createClient from 'openapi-fetch';
import type { paths } from './types';

export const api = createClient<paths>({ baseUrl: 'https://api.example.com' });

// Usage — fully typed, zero generics
const { data, error } = await api.GET('/posts/{id}', {
  params: { path: { id: '123' } }
});
```

### Authentication with HttpOnly cookies

```typescript
// hooks.server.ts
export const handle: Handle = async ({ event, resolve }) => {
  const session = event.cookies.get('auth-token');
  if (session) {
    event.locals.user = await validateSession(session);
  }
  return resolve(event);
};
```

---

## Testing strategy

### Vitest configuration for SvelteKit

```typescript
// vite.config.ts
import { svelteTesting } from '@testing-library/svelte/vite';

export default defineConfig({
  plugins: [sveltekit(), svelteTesting()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest-setup.ts'],
    include: ['src/**/*.{test,spec}.{js,ts}']
  }
});
```

### Component testing with Svelte 5 Runes

```typescript
// Counter.svelte.test.ts
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import Counter from './Counter.svelte';

test('Counter increments', async () => {
  const user = userEvent.setup();
  render(Counter);

  await user.click(screen.getByRole('button'));
  expect(screen.getByRole('button')).toHaveTextContent('1');
});
```

**Important**: Files using Runes in tests must have `.svelte.test.ts` extension. Use `flushSync()` when testing `$derived` values.

### E2E with Playwright

```typescript
// tests/auth.test.ts
import { expect, test } from '@playwright/test';

test('user can login', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[name="email"]', 'user@test.com');
  await page.fill('input[name="password"]', 'password');
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL('/dashboard');
});
```

---

## Performance optimization

### Svelte 5 delivers significant improvements

Svelte 5 achieves **up to 50% smaller bundle sizes** through its signals runtime architecture. Components compile to plain JavaScript functions, enabling better tree-shaking.

### Image optimization with @sveltejs/enhanced-img

```svelte
<enhanced:img
  src="$lib/assets/hero.jpg"
  alt="Hero"
  fetchpriority="high"
  sizes="(min-width:1920px) 1280px, 640px"
/>
```

Benefits include automatic AVIF/WebP conversion, generated width/height (prevents CLS), and responsive srcsets.

### Preloading strategies

```html
<!-- app.html -->
<body data-sveltekit-preload-data="hover">
```

Use `data-sveltekit-preload-data="tap"` for slower pages, `data-sveltekit-preload-code` for code-only preloading.

### Streaming for slow data

```typescript
export const load: PageServerLoad = async () => ({
  fast: await getFastData(),
  slow: getSlowData() // Not awaited — streams in after initial HTML
});
```

---

## Development workflow and tooling

### Recommended project structure

```
src/
├── lib/
│   ├── components/ui/       # shadcn-svelte components
│   ├── server/              # Server-only (db, auth)
│   ├── stores/              # .svelte.ts files with Runes
│   └── utils/
├── routes/
│   ├── (app)/               # Authenticated routes
│   ├── (auth)/              # Login/register
│   └── api/                 # API routes
├── app.html
├── app.css
└── hooks.server.ts
```

### Linting and formatting

**Biome** is the single linter and formatter. Install it alone:

```bash
bun add -D --exact @biomejs/biome
```

```json
// biome.json
{
  "formatter": { "indentStyle": "tab" },
  "linter": { "rules": { "recommended": true } }
}
```

Biome does not type-check. Keep `svelte-check` in the toolchain for template markup.

### Environment variables

```bash
# Private (server only)
DATABASE_URL="postgresql://..."

# Public (available everywhere, baked into client)
PUBLIC_API_URL="https://api.example.com"
```

```typescript
import { DATABASE_URL } from '$env/static/private';
import { PUBLIC_API_URL } from '$env/static/public';
```

---

## State management decision tree

1. **Single component** → `$state()` / `$derived()`
2. **Parent-child** → `$props()` with `$bindable()` if needed
3. **Component subtree** → Context API with `setContext`/`getContext`
4. **Global client-only** → `.svelte.ts` module state
5. **Global with SSR** → Context API initialized in `+layout.svelte`
6. **Persist across refreshes** → localStorage (client) or cookies (SSR)
7. **URL-shareable** → `$page.url.searchParams`
8. **Server data with caching** → TanStack Query

**SSR Warning**: Module-level `$state` is shared between all users on the server. Use context for per-request state.

---

## Anti-patterns to avoid

### Svelte 5 migration failures
- ❌ Using `$:` reactive statements → Use `$derived()`
- ❌ Using `export let` → Use `let { prop } = $props()`
- ❌ Using `<slot>` → Use `{@render children?.()}`
- ❌ Using `writable`/`readable` stores → Use `.svelte.ts` with `$state`

### Performance killers
- ❌ Using `$effect` to derive state (use `$derived`)
- ❌ Destructuring reactive proxies (breaks reactivity)
- ❌ Awaiting all data in load functions (kills streaming)
- ❌ `ssr = false` globally without good reason

### Common mistakes
- ❌ `bun run dev` without `--bun` (still uses Node.js)
- ❌ Module-level `$state` with SSR (shared between users)
- ❌ Accessing `localStorage` during SSR (guard with `browser` check)

---

## Version requirements summary

| Feature | Minimum Version |
|---------|-----------------|
| Core Runes (`$state`, `$derived`, `$effect`, `$props`) | Svelte 5.0 |
| `$inspect.trace()` | Svelte 5.14 |
| `$props.id()` | Svelte 5.20 |
| Overridable `$derived` | Svelte 5.25 |
| `$app/state` (replaces `$app/stores`) | SvelteKit 2.12 |
| `PageProps` / `LayoutProps` types | SvelteKit 2.16 |

---

## Conclusion: The cleanest path forward

For 2025/2026 greenfield projects, **embrace Svelte 5 Runes fully**—they provide clearer mental models, better TypeScript integration, and improved performance over Svelte 4 patterns. Use **UnoCSS with presetWind4** (not Tailwind directly) for styling, **shadcn-svelte** for accessible UI components, and **Bun** where it provides clear benefits (package management, password hashing, SQLite, production runtime).

The combination of explicit reactivity through Runes, file-based routing with powerful data loading patterns, and a modern CSS-in-JS approach creates an exceptionally productive development experience. When in doubt, choose the newer approach—Svelte 5's design decisions are intentional improvements over previous patterns.
