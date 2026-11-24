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

Assignment 2 splits the app into two services, `services/specs` (port 8000) and `services/samples` (port 8001), each with its own SQL Server database and a JSON API, plus a static UI in `ui/` that calls both from the browser. Full `docker compose up` of the whole system arrives with the Dockerfiles; for now compose runs the database and the UI, and each service runs with Python.

Requires Docker Desktop (on Apple Silicon, turn on "Use Rosetta for x86_64/amd64 emulation") and Python 3.10+.

**1. Start SQL Server and create the databases and logins**

```bash
docker compose up -d mssql db-init ui
docker compose logs db-init        # ends with "databases and logins ready"
```

`db/init.sql` creates `specs`, `samples` and a `_test` database for each, plus one login per service that can only reach its own databases. Data lives in the `mssql-data` volume and survives `docker compose down`; `docker compose down -v` deletes it.

**2. Run a service** (same for `samples`, with `samples_user`, `LocalOnly_samples_2026`, `/samples` and `PORT=8001`)

```bash
cd services/specs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='mssql://specs_user:LocalOnly_specs_2026@localhost:1433/specs'
python app.py                      # applies pending migrations, then serves on :8000
```

The passwords are local-only defaults from `docker-compose.yml`; override them in a git-ignored `.env` file.

**3. Open the UI** at http://localhost:8080 (use `localhost`, not `127.0.0.1`: CORS allows exactly `UI_ORIGIN`). `ui/config.js` holds the two service URLs; the deploy workflow overwrites it with the Azure ones.

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
python -m pytest --cov
```

## Project documents

- [`ADR.md`](ADR.md): architecture decision records
- [`AI_USAGE.md`](AI_USAGE.md): log of AI assistance used in this project
