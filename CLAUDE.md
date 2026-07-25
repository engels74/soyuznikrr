# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Workspace

- This repository contains independent `backend/` (Python 3.14/uv/Litestar) and
  `frontend/` (Bun/SvelteKit) projects. Run package commands with the working directory shown;
  the backend's default SQLite URL is relative to `backend/`.
- Install the CI-equivalent dependencies from the repository root:
  `bun install`, `bun install --cwd frontend`, and `uv sync --project backend --all-extras`.
- Start the local stack with `uv run dev_cli`. It installs missing package dependencies, runs
  Alembic migrations, creates a development `SECRET_KEY`, and starts both servers. Use
  `uv run dev_cli stop` to stop detached/stale processes.

## Verification

- All configured formatting/lint hooks:
  `SKIP=no-commit-to-branch bun run lint` (the skipped hook rejects commits on `main`).
- Backend typecheck: `cd backend && uv run basedpyright`.
- Backend suite: `cd backend && uv run pytest`.
- One backend case: `cd backend && uv run pytest
  tests/test_url_validation.py::TestPrivateIPBlocking::test_loopback_ipv4_blocked -n 0`.
- Frontend typecheck: `bun run --cwd frontend check`.
- Frontend suite: `bun run --cwd frontend test`.
- One frontend file: `bun run --cwd frontend test -- src/lib/api/client.test.ts`.
- One frontend case: `bun run --cwd frontend test -- src/lib/api/client.test.ts -t
  'should transform validation error responses with field_errors'`.
- CI runs the same backend/frontend checks separately in `.github/workflows/code-quality.yml`.
  Pre-push hooks run only for files in their matching subtree.

## Cross-cutting invariants

- Do not edit `frontend/src/lib/api/types.d.ts`; it is generated from the running backend's
  OpenAPI document. Follow `.claude/skills/sync-api-contract/SKILL.md` after API schema changes.
- With SQLite, keep the backend at one Granian worker; `dev_cli/runner.py` deliberately enforces
  this to avoid write-lock contention.
- `DEV_SKIP_AUTH` is effective only with backend `DEBUG=true`, and both applications must receive
  it. `uv run dev_cli --skip-auth` wires both sides correctly.
- Browser API calls use `PUBLIC_API_URL` when set; otherwise they stay same-origin and pass
  through SvelteKit's `/api/[...path]` proxy. The proxy must preserve `Origin`/`Referer` because
  backend CSRF validation uses them.

## Scoped references

- `backend/CLAUDE.md` — database, migrations, startup, and backend test invariants. Read before
  changing backend models, lifecycle code, authentication, or tests.
- `frontend/CLAUDE.md` — API routing, generated types, SSR authentication, and frontend tooling.
  Read before changing API integration, hooks, routes, or Svelte components.
- `.claude/skills/sync-api-contract/SKILL.md` — regenerate and verify the typed frontend client.
  Use after changing backend request/response schemas or routes.
