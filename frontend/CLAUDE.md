# Frontend context

## API boundary

- `src/lib/api/client.ts` uses `PUBLIC_API_URL ?? ''` and includes cookies. An empty public URL
  means same-origin requests to SvelteKit's `src/routes/api/[...path]/+server.ts` proxy.
- Server-side auth in `src/hooks.server.ts` and the API proxy resolve the backend as
  `INTERNAL_API_URL`, then `PUBLIC_API_URL`, then `http://localhost:8000`.
- Keep `Origin` and `Referer` when changing the proxy; backend CSRF checks depend on them. Keep
  SSE responses streaming, but buffer other responses because SvelteKit SSR clones them.
- `src/lib/api/types.d.ts` is generated. Do not hand-edit it; use
  `.claude/skills/sync-api-contract/SKILL.md`.

## Authentication routing

- `src/hooks.server.ts` refreshes expired access cookies during SSR, enforces onboarding, and
  protects non-public routes. A transient backend failure leaves cookies intact; only
  authentication failures clear them.
- `DEV_SKIP_AUTH` must match the backend. Use `uv run dev_cli --skip-auth` from the repository
  root rather than starting only Vite with the variable.

## Tooling and tests

- Use Bun commands from the repository root (`bun run --cwd frontend ...`) or run them inside
  `frontend/`; the committed lockfile is `frontend/bun.lock`.
- Biome's Svelte overrides intentionally leave unused-variable/import checks to
  `svelte-check`; run both `SKIP=no-commit-to-branch bun run lint` and
  `bun run --cwd frontend check` from the repository root.
- Vitest uses jsdom and `vitest-setup.ts`, which mocks both SvelteKit dynamic env modules.
