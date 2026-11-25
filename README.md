# Maison Grader — Tech Pack & Size Grading

A web application that helps a small independent fashion label manage garment measurement specs and check factory samples against them.

## The problem

A small independent label (one designer and one production manager, about 40 styles per season, working with two overseas factories) tracks garment measurements in scattered spreadsheets. When a factory sends a sample, there is no quick way to tell which measurements are out of tolerance or in which sizes.

## Feature domains

The application is a single-process monolith with two feature domains, designed so each could later become its own service.

### 1. Specs & grading

Stores each style's points of measure at a base size, with a tolerance and a grade rule for each, and generates the full size run (XS–XL) from them.

### 2. Sample fit review

Records the measurements taken from factory samples in each sample round (proto, fit, pre-production) and produces an out-of-tolerance report by comparing them against the graded spec.

### Where the seam is

Each domain owns its own tables. Sample fit review reads specs only through a single "get graded spec for style and size" function and never queries the specs tables directly. That function is where the split into separate services would happen in a later assignment.

## Glossary

| Term | Meaning |
|---|---|
| Tech pack | The document a brand sends a factory describing how to make a garment, including its measurement spec |
| Style | One garment design, identified by a style code (e.g. a specific shirt) |
| Point of measure (POM) | A defined place where a garment is measured, e.g. half chest or body length |
| Base size | The size the spec is designed in (here, M); other sizes are calculated from it |
| Grade rule | How much a point of measure changes from one size to the next |
| Size run | The full range of sizes a style is made in (here, XS–XL) |
| Graded spec | The measurements for every size, calculated from the base size using the grade rules |
| Tolerance | How far a measurement may deviate from the spec and still pass |
| Sample round | A stage of factory samples: proto, fit, then pre-production |

## Running locally

Assignment 2 splits the app into two services, `services/specs` (port 8000) and `services/samples` (port 8001), each with its own SQL Server database, its own Dockerfile and a JSON API, plus a static UI in `ui/` that calls both from the browser.

Requires Docker Desktop (on Apple Silicon, turn on "Use Rosetta for x86_64/amd64 emulation"). Python 3.10+ only to run a service or its tests outside Docker.

### The whole system, one command

```bash
docker compose up --build
```

Then open http://localhost:8080 (use `localhost`, not `127.0.0.1`: CORS allows exactly `UI_ORIGIN`). Compose starts SQL Server, runs `db/init.sql` once it is healthy, then starts both services (each applies its pending migrations before gunicorn starts) and nginx serving `ui/`.

`db/init.sql` creates `specs`, `samples` and a `_test` database for each, plus one login per service that can only reach its own databases. Data lives in the `mssql-data` volume and survives `docker compose down`; `docker compose down -v` deletes it.

To see the designed partial failure: `docker compose stop specs`, then record a sample round. The UI shows "Nothing was saved"; recorded rounds still list and open. `docker compose start specs` brings it back.

### One service outside Docker

Same for `samples`, with `samples_user`, `LocalOnly_samples_2026`, `/samples` and `PORT=8001`:

```bash
docker compose up -d mssql db-init ui
cd services/specs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL='mssql://specs_user:LocalOnly_specs_2026@localhost:1433/specs'
python app.py                      # applies pending migrations, then serves on :8000
```

The passwords are local-only defaults from `docker-compose.yml`; override them in a git-ignored `.env` file. `ui/config.js` holds the two service URLs; the deploy workflow overwrites it with the Azure ones.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | none (required) | `mssql://user:password@host:1433/database` of this service's own database |
| `PORT` | `8000` specs, `8001` samples | Port the server listens on |
| `SPECS_URL` | `http://localhost:8000` | samples only: where the specs service is |
| `SPECS_TIMEOUT_S` | `25` | samples only: how long to wait for specs before answering 503 |
| `UI_ORIGIN` | `http://localhost:8080` | The only browser origin allowed to call the service (CORS) |
| `GIT_SHA` | `dev` | Version reported by `/health` (set to the commit SHA on deploy) |
| `HEALTH_DB_TIMEOUT_S` | `5` | How long `/health` keeps retrying the database before answering 503 |
| `DB_CONNECT_TIMEOUT_S` | `90` | How long to keep retrying while the database is starting or resuming |
| `APP_DEBUG` | `0` | Set to `1` for Flask debug mode (local development only) |

### Migrations

Each service's schema is defined by `services/<name>/migrations/NNN_name.sql`. `python migrate.py` (also run by `python app.py` before it starts) applies the pending files in order, each once and in its own transaction, and records them in `schema_migrations` with a checksum. Applied files are never edited: a change goes in a new numbered file.

## Tests and coverage

Tests that need a database run against the `_test` databases, which they wipe; without `TEST_DATABASE_URL` they are skipped.

```bash
cd services/specs
export TEST_DATABASE_URL='mssql://specs_user:LocalOnly_specs_2026@localhost:1433/specs_test'
python -m pytest --cov --cov-fail-under=70
ruff check .
```

### CI

`.github/workflows/ci.yml` runs on every push and pull request: it validates `system.yaml` against `system.schema.json` and both `openapi.yaml` files, then for each service runs ruff and the tests with coverage (failing under 70%) against a throwaway SQL Server started from this compose file with random passwords, and builds the image. CI never connects to Azure SQL.

## Project documents

- [`ADR.md`](ADR.md): architecture decision records
- [`AI_USAGE.md`](AI_USAGE.md): log of AI assistance used in this project
