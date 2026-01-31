# Windstorm Dwarven — README (for Git)

Short README capturing how to run and understand the Windstorm Dwarven backend.

## Project

Windstorm-Dwarven is the backend API for the Windstorm service. It exposes
REST endpoints for model commits, requirements, verifications, actions (threads),
artifacts and container lookups. The codebase uses FastAPI, SQLAlchemy, and
integrates with Keycloak for OAuth2 and MinIO for artifact storage.

## Repository layout (important files)

- `src/env.py` — environment variable defaults and configuration
- `src/main.py` — primary FastAPI app and most API routes
- `src/sampleapp.py` — lightweight test app with token validation helper
- `src/database/db_model.py` — SQLAlchemy ORM models (database schema)
- `src/views/public.py` — presentation-layer helpers that build JSON views

See source for full details: [src/main.py](src/main.py)

## Quickstart (development)

1. Install dependencies (recommended in a virtualenv):

```powershell
pip install -r requirements.txt
```

2. Set required environment variables (examples):

```powershell
setx SQLHOST "localhost:5432"
setx PGUSER "postgres"
setx PGPASSWD "mysecretpassword"
setx PGDBNAME "pgdb"
setx HARBORPATH "core.harbor.domain/"
setx KCREALM "test"
setx KCADDR "https://keycloak.digitalforge.app"
setx MINIOACCESSKEY "<minio-access-key>"
setx MINIOSECRETKEY "<minio-secret-key>"
```

3. Start the FastAPI app (the project exposes a factory `main()`):

```powershell
uvicorn src.main:main --reload --factory
```

For the small sample app used in development:

```powershell
uvicorn src.sampleapp:main --reload --factory
```

Notes:
- The app expects a PostgreSQL database configured by the env vars above.
- Keycloak is used for OAuth2 token validation; adjust `KCADDR` and `KCREALM`.

## Environment variables

Primary variables read from `src/env.py` and other modules:

- `SQLHOST` — database host:port (default `localhost:5432`)
- `PGUSER`, `PGPASSWD`, `PGDBNAME` — Postgres credentials and DB name
- `HARBORPATH` — base path for container images in registry
- `KCREALM`, `KCADDR` — Keycloak realm and base URL for auth
- `MINIOACCESSKEY`, `MINIOSECRETKEY` — credentials for MinIO (used in `src/views/public.py`)

Keep these secrets out of source control and provide them via secure CI/CD
or runtime environment (Kubernetes secrets, environment variable managers, etc.).

## Database schema overview

The main ORM models live in [src/database/db_model.py](src/database/db_model.py).
Key tables include:

- `commits` — commit metadata (branch/ref, commit hash, processed flag)
- `model_repo` — repository metadata and default branch
- `models`, `elements`, `models_elements` — stored model documents and element mapping
- `requirements` (`Reqts`) — extracted requirements referencing `elements`
- `verifications` — verification entries tied to requirements/elements
- `actions` — actions (threads) that may reference containers and artifacts
- `artifacts`, `artifact_commits` — git-configured artifact records and commit refs
- `containers`, `container_commits` — registered container images and digests
- `thread_executions` — execution records for actions/threads

Refer to the file for the full column list and types: [src/database/db_model.py](src/database/db_model.py)

## API overview

The API exposes a set of endpoints for interacting with models, artifacts,
containers and executions. The main endpoints are implemented in
`src/main.py` and include, for example:

- `GET /models/commits` — list commits
- `GET /models/requirements/main` — list requirements for the main branch
- `GET /models/verifications` — list verifications
- `GET /models/threads/*` — endpoints to query actions/threads by id, dependency, branch and artifact/container
- `GET /artifacts` and `/artifacts/{id}/refs` — artifact listings and refs

There are also view helper functions under `src/views/public.py` that produce
frontend-ready JSON structures (commit views, requirements view, thread views,
and pre-signed MinIO URLs for execution artifacts).

For the full list of routes and query params, see: [src/main.py](src/main.py)

## Authentication

Several endpoints use Keycloak JWT validation. Token validation is handled by
`valid_access_token` in `src/main.py` (and a similar helper in
`src/sampleapp.py`) which fetches JWKS from Keycloak and validates tokens.
Protected endpoints use FastAPI dependencies to require a valid token.

## Storage (MinIO)

The project uses MinIO for storing execution inputs/outputs and generates
pre-signed URLs when objects exist. Provide `MINIOACCESSKEY` and
`MINIOSECRETKEY` for access; TLS and certificates are handled in
`src/views/public.py` (it writes `minio.pem` in the working directory).

## License

See the `LICENSE` file in the repository root.

## Where to look next

- API implementations: [src/main.py](src/main.py)
- Views and MinIO: [src/views/public.py](src/views/public.py)
- DB models: [src/database/db_model.py](src/database/db_model.py)

If you want, I can:
- expand the API endpoint list with every route and parameters, or
- run a quick `python -m compileall src` to check for syntax errors.
