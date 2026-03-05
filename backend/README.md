# Zondarr Backend

Unified invitation and user management system for media servers (Plex, Jellyfin).

## Development

```bash
# Install dependencies
uv sync

# Run development server
granian zondarr.app:app --interface asgi --host 0.0.0.0 --port 8000

# Type checking
basedpyright

# Linting and formatting
ruff check .
ruff format .

# Run tests
pytest
```

## Bootstrap token retrieval

When `BOOTSTRAP_TOKEN` is not set and no admin account exists yet, the backend
generates a one-time bootstrap token at startup for the first admin setup.

- Local/dev: copy it from the backend console output or read the generated
  token file on the machine running the backend. With `uv run dev_cli`, that
  file is `backend/data/.bootstrap_token`.
- `uv run dev_cli` keeps this workflow practical by setting
  `BOOTSTRAP_TOKEN_FILE` for the backend process only. `--skip-auth` still
  works for mock-auth development, but it does not make the token a frontend
  concern.
- Docker: retrieve the token out-of-band from container logs, `docker exec`,
  or the mounted config/data volume. Do not expose it through frontend SSR or
  an HTTP endpoint.
