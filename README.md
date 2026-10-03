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

Requires Python 3.10+ (the pinned pytest 9 needs it) whose bundled SQLite is 3.37 or newer, because the tables are `STRICT`. Check with `python -c "import sqlite3; print(sqlite3.sqlite_version)"`.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python app.py
```

The app starts on http://localhost:8000. Check it with `GET /health`, which returns `{"status": "ok"}`.

### Configuration

All configuration is through environment variables. None are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (binds to `0.0.0.0`) |
| `DATA_DIR` | `./data` (next to `app.py`) | Directory for the SQLite database; created if missing |
| `APP_DEBUG` | `0` | Set to `1` to enable Flask debug mode (local development only) |

### Database

SQLite file at `$DATA_DIR/techpack.db`. It is created and initialized automatically on startup, with no manual migration step.

To start from an empty database, stop the app and delete that file.

## Tests and coverage

```bash
python -m pytest --cov
```

`pytest` and `pytest-cov` are in `requirements.txt`. `.coveragerc` measures only the app's own code and omits `tests/`.

Result on 2026-10-02: 91 tests passed, 99% total coverage. The pure logic (`specs/grading.py`, `samples/review.py`, `units.py`) and both stores (`specs/store.py`, `samples/store.py`) are at 100%. The only uncovered lines are the `if __name__ == "__main__":` block in `app.py`, which reads `PORT` and `APP_DEBUG` and is checked by starting the app (see ADR-4).

## Project documents

- [`ADR.md`](ADR.md): architecture decision records
- [`AI_USAGE.md`](AI_USAGE.md): log of AI assistance used in this project
