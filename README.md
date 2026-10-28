# Location Popularity Map API

Django REST Framework backend for a location popularity map. It provides session
authentication, public location discovery, reviews and reactions, subscriptions, durable
view tracking, Redis-backed list caching, and transactional email outbox delivery.

## Stack

- Python 3.13, Django 5.2, Django REST Framework
- PostgreSQL 18
- Redis 8 (cache, view cooldown, Celery broker)
- Celery 5.6 with Celery Beat
- pandas for streaming CSV export
- drf-spectacular for OpenAPI and Swagger UI
- uv for dependency management, Ruff for linting and formatting, pytest for tests

## Quick start with Docker Compose

Requirements: Docker Desktop with Compose.

```bash
docker compose up --build
```

The `web` service applies migrations automatically and starts Django on
`http://localhost:8000`. The development stack also starts PostgreSQL, Redis, a Celery
worker, Celery Beat, and MailHog.

Useful URLs:

- Swagger UI: `http://localhost:8000/api/v1/docs/`
- OpenAPI schema: `http://localhost:8000/api/v1/schema/`
- MailHog UI: `http://localhost:8025/`
- Django admin: `http://localhost:8000/admin/`

Create an administrator after the stack is running:

```bash
docker compose exec web python manage.py createsuperuser
```

The custom user manager assigns `role=admin` and the required Django staff/superuser flags
to users created with `createsuperuser`.

Stop the stack without deleting data:

```bash
docker compose down
```

Deleting the PostgreSQL volume is a separate destructive action:

```bash
docker compose down -v
```

## Local development without Docker

Start PostgreSQL and Redis first, or run only those services with
`docker compose up -d db redis mailhog`.

```bash
cp .env.example .env
uv sync --locked
uv run python manage.py migrate
uv run python manage.py runserver
```

In separate terminals:

```bash
uv run celery -A config worker -l info
uv run celery -A config beat -l info
```

Local development sends email through MailHog SMTP on port `1025` by default. The email
backend is configurable, so business code does not depend on MailHog.

## Configuration

Configuration comes from environment variables. The defaults in `.env.example` are safe for
local development only. Production settings fail closed when required values are missing.

Important variables:

| Variable | Purpose | Local default |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Settings module | `config.settings.development` |
| `DJANGO_SECRET_KEY` | Django secret | local development placeholder |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins | empty |
| `POSTGRES_*` | PostgreSQL connection | local `popularity_map` database |
| `REDIS_CACHE_URL` | Django list cache | `redis://localhost:6379/0` |
| `REDIS_VIEW_COOLDOWN_URL` | View cooldown keys | `redis://localhost:6379/2` |
| `CELERY_BROKER_URL` | Celery broker | `redis://localhost:6379/1` |
| `LOCATION_LIST_CACHE_TTL_SECONDS` | Location list cache TTL | `60` |
| `VIEW_COOLDOWN_SECONDS` | Per-identity view cooldown | `3600` |
| `SESSION_COOKIE_AGE_SECONDS` | Session lifetime | `1209600` |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Email delivery | MailHog / console |
| `API_DOCS_ENABLED` | Swagger and schema access | enabled in development, disabled in production |

Never commit real secrets or a populated `.env` file.

## API overview

All business endpoints are under `/api/v1/`.

| Area | Endpoints |
|---|---|
| Authentication | `auth/csrf/`, `auth/register/`, `auth/email/confirm/`, `auth/email/resend/`, `auth/login/`, `auth/logout/`, `auth/me/`, `auth/password/reset/`, `auth/password/reset/confirm/` |
| Categories | `categories/`, `categories/{id}/` |
| Locations | `locations/`, `locations/{id}/`, `locations/deleted/`, `locations/{id}/restore/`, `locations/export/?format=json|csv` |
| Reviews | `locations/{location_id}/reviews/`, `reviews/{id}/` |
| Reactions | `reviews/{id}/reaction/` |
| Subscriptions | `locations/{location_id}/subscription/` |

Authentication uses Django sessions and cookies, not JWT. Unsafe session-authenticated
requests require the CSRF token from `auth/csrf/` in the `X-CSRFToken` header.

Errors use a stable envelope:

```json
{
  "error": {
    "code": "review_already_exists",
    "message": "An active review for this location already exists.",
    "details": null
  }
}
```

## Testing and quality checks

The test suite uses a real PostgreSQL database and real Redis logical databases. Start the
local services before running it:

```bash
docker compose up -d db redis
uv run pytest
```

Run all required quality gates:

```bash
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
```

Generate the OpenAPI schema locally:

```bash
uv run python manage.py spectacular --file schema.yaml
```

## Manual testing data

Load the prepared local dataset and follow the manual testing guide:

```bash
uv run python manage.py loaddata fixtures/manual_testing.json
```

See [docs/manual-testing.md](docs/manual-testing.md) for credentials, dataset
details, expected metrics, and end-to-end scenarios.

`uv.lock` is committed and CI installs with `uv sync --locked`.

## Git workflow

- Work on issue-numbered branches from `dev`: `<type>/<issue-number>-<kebab-case-description>`.
- Do not commit directly to `main`.
- Use Conventional Commits, for example `feat(locations): add soft delete`.
- Allowed types: `feat`, `fix`, `refactor`, `perf`, `style`, `test`, `docs`, `build`, `ops`, `chore`.
- Install local hooks once:

```bash
sh scripts/install-git-hooks.sh
```

The commit-msg hook validates the Conventional Commit header. The pre-commit hook runs
Ruff linting and formatting. Tests are intentionally not run by the pre-commit hook so a
red TDD commit is possible locally; CI blocks merging unless the full suite passes.

## Production template

`compose.production.yaml` is a template, not a ready-to-deploy configuration. It uses
Gunicorn, requires explicit environment values, disables API docs by default, and does not
include MailHog. Supply production secrets through the deployment environment or a secret
manager. PostgreSQL and Redis are not published outside the Compose network.

Run migrations as a controlled deployment step before starting the new application version:

```bash
docker compose -f compose.production.yaml run --rm web python manage.py migrate
docker compose -f compose.production.yaml up -d
```

## Design notes

- Location list responses are cached with a generation/version key. Location, category, and
  review writes invalidate the generation only after a successful commit. View events and
  reactions do not invalidate the list cache.
- View events are stored in PostgreSQL. Redis provides a fast cooldown pre-check, while a
  database row lock and unique constraint protect correctness when Redis is unavailable.
- Review edits create a replacement active row and soft delete the previous row in one
  transaction. Reactions stay attached to the historical row.
- Email delivery uses a PostgreSQL transactional outbox, one row per unique
  review/recipient pair, with Celery retries and a periodic Beat sweep.
- Soft-deleted locations remain available in the deleted list for their author or an
  administrator and can be restored without losing related data.

## Known assumptions

- The feature branch uses issue number `1` because no GitHub issue number was provided.
- The OpenAPI schema covers the public API. Swagger and schema routes are hidden when
  `API_DOCS_ENABLED` is false.
