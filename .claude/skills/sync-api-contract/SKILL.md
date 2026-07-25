---
name: sync-api-contract
description: Regenerate and verify the frontend OpenAPI types after backend route or schema changes.
---

# Synchronize the API contract

Use this workflow after changing Litestar routes or request/response schemas.

1. Verify the changed backend behavior first:
   - `cd backend && uv run pytest`
   - `cd backend && uv run basedpyright`
2. From the repository root, start the backend document source:
   - `uv run dev_cli --backend-only`
   - The preflight applies Alembic migrations and creates the required development secret.
3. In another shell, regenerate the committed client types:
   - `bun run --cwd frontend generate:api`
   - This replaces `frontend/src/lib/api/types.d.ts`; do not patch that file manually.
4. Review the generated diff for removed or renamed operations and schemas. Update
   `frontend/src/lib/api/client.ts` wrappers and call sites to match.
5. Verify the frontend:
   - `bun run --cwd frontend check`
   - `bun run --cwd frontend test`
6. Stop the backend:
   - `uv run dev_cli stop --backend-only`
