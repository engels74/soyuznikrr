# AGENTS.md

This file provides guidance to AI coding agents when working with code in this
repository.

Zondarr is invitation and user management for Plex/Jellyfin. Two apps in one repo:
`backend/` (Python 3.14, Litestar + msgspec + async SQLAlchemy, served by Granian) and
`frontend/` (Bun, SvelteKit 2 + Svelte 5 runes + UnoCSS). `dev_cli/` is a local dev launcher.

## Commands

`uv run dev_cli` starts both servers (`:8000` / `:5173`). It installs deps, runs Alembic
migrations, generates `SECRET_KEY`, and wires `CORS_ORIGINS` / `PUBLIC_API_URL` /
`BOOTSTRAP_TOKEN_FILE`. `uv run dev_cli stop` stops them.

|  | Backend (from `backend/`) | Frontend (from repo root) |
| --- | --- | --- |
| Test | `uv run pytest` | `bun run --cwd frontend test` |
| One file | `uv run pytest tests/test_totp.py -n0` | `bun run --cwd frontend test src/lib/api/client.test.ts` |
| One case | `uv run pytest tests/test_totp.py::test_name -n0` | `bun run --cwd frontend test -t "test name"` |
| Typecheck | `uv run basedpyright` | `bun run --cwd frontend check` |
| Lint/format | `uv run ruff check --fix . && uv run ruff format .` | `frontend/node_modules/.bin/biome check --write frontend/` |

`-n0` disables the `-n auto` xdist workers baked into `addopts`; omit it for full runs.
`bun run lint` (= `prek run --all-files`) runs every hook across both sides.

## Repo-wide gotchas

- **`main` is commit-blocked** by the `no-commit-to-branch` prek hook. Branch and open a PR.
- prek's **pre-push** stage runs basedpyright, svelte-check, pytest and vitest; the commit stage
  runs ruff, biome, gitleaks, and conventional-commit message linting. A failing `git push` is
  usually these hooks, not the remote.
- `dev_cli/` sits outside every automated gate: ruff is scoped to `^backend/(src|tests)/`,
  CI runs basedpyright only in `backend/`, and pytest's `testpaths = ["tests"]` never reaches
  `dev_cli/tests/`. Run and type-check it by hand if you change it.
- Serialization is **msgspec**, never Pydantic. Pydantic is only a transitive dep of
  `jellyfin-sdk`; its 3.14 warning is filtered in `backend/pyproject.toml`.

## Backend (`backend/src/zondarr/`)

Layering, outermost first: `api/` (Litestar controllers) → `services/` → `repositories/` →
`models/`. Controllers are listed by hand in the `route_handlers` list in
`app.py::create_app` — a new controller is unreachable until added there.

- **New table or column**: add the model, export it from `models/__init__.py` (Alembic
  autogenerate only sees what is attached to `Base.metadata`), then
  `cd backend && uv run alembic revision --autogenerate -m "..."`. Also append the table name to
  `_TRUNCATE_ORDER` in `tests/conftest.py`, children before parents — otherwise property tests
  leak rows between Hypothesis examples instead of failing loudly.
- **New media server provider**: implement the `MediaClient` Protocol from `media/protocol.py`
  in `media/providers/<name>/`, expose a `ProviderDescriptor` (it may carry its own
  `route_handlers`), and register it in `media/providers/__init__.py::register_all_providers()`.
  Nothing auto-discovers providers.
- **New wizard interaction type**: add the `InteractionType` member in `models/wizard.py`, a
  handler in `services/interactions/handlers.py`, and a `case` in
  `services/interactions/registry.py::_create_handler`. `assert_never` there turns a missing
  case into a basedpyright error rather than a runtime one.
- basedpyright runs in `recommended` mode with `migrations/` excluded. Inline
  `# pyright: ignore[...]` on the offending line is the local convention for third-party `Any`
  leakage; do not loosen `typeCheckingMode`.

## Frontend (`frontend/`)

- `src/lib/api/types.d.ts` is **generated** from the backend OpenAPI schema — never hand-edit.
  Regenerate with the backend running on `:8000`: `bun run --cwd frontend generate:api`.
  Backend schema changes are invisible to the frontend until you do.
- Styling is **UnoCSS** (`uno.config.ts`: presetWind4 + presetShadcn + presetIcons).
  `tailwind.config.js` is a deliberately empty stub kept only for the shadcn-svelte CLI — theme
  config placed there has no effect. Design tokens (`--cr-*`) live in `src/app.css` and are
  exposed as `cr-*` utility colors through `uno.config.ts`.
- Component tests must be named `*.svelte.test.ts`; vitest's `include` in `vite.config.ts` only
  compiles runes for that pattern. Plain `*.test.ts` is for non-component modules. Components
  taking `$props` are driven through a `*-test-wrapper.svelte` (see
  `src/lib/components/error-boundary-test-wrapper.svelte`).
- Browser calls go same-origin to `/api/*` and are proxied by `src/routes/api/[...path]/+server.ts`
  to `INTERNAL_API_URL`; `Origin`/`Referer` must survive that hop because the backend's
  `core/csrf.py` validates them. Setting `PUBLIC_API_URL` bypasses the proxy and then requires
  `CORS_ORIGINS` on the backend.

## Reference rules

- `.agents/rules/backend-dev-pro.md` — Python 3.14 / Litestar / msgspec / Granian /
  async SQLAlchemy patterns. Read before adding backend controllers, structs, or DI wiring.
- `.agents/rules/frontend-dev-pro.md` — Svelte 5 runes / SvelteKit 2 / Bun / UnoCSS /
  shadcn-svelte conventions. Read before writing new components or SvelteKit boilerplate.
- `.env.example` — every environment variable, its default, and its dev-CLI/Docker behaviour.
  Read before touching config, auth, or deployment wiring.
