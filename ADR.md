## 1. Framework Choice: Flask
Date: 2026-09-27
Status: Decided
Context: The app is mostly data entry and review: entering points of measure and grade rules, generating size runs, and recording factory sample measurements against tolerances. It must run as one Python process with SQLite and serve its own pages.
Decision: Use Flask with Jinja templates to serve server-rendered HTML forms and pages from a single process.
Alternatives considered: FastAPI. FastAPI's async support helps when a request spends time waiting on slow I/O, wheras this app's I/O is local SQLite reads and writes. Furthermore its other strengths, Pydantic and auto-generated API docs, are for JSON APIs, and my app serves HTML forms.
Consequences: Flask enforces no structure, so keeping the two domains separable is my responsibility, not the framework's. Flask renders HTML pages directly with its built-in template engine (Jinja), so I won't need a separate frontend.

## 3. Data-Model/ Schema Decision: Per-Step-Grade-Rules and unit conversion
Date: 2026-09-29 
Status: Decided
Context: Real size runs don't grade evenly (e.g. XS-->S at +2cm, M-->L at +3.5cm...), designers use cm to describe their designs despite lack of accuracy, and for Assignment 2, domain 2 needs it's own db.
Decision: One grade_rule row per point of measure per size step, where increment is value at that size minus the size below. All measurements stored as integer mm in STRICT tables; cm only at form/ display edge. Domain 2 stores no foreign keys.
Alternatives considered: Storing values as real centimetres was rejected because calculations end up not being 100% precise; a sleeve measuring 60.8 cm failed a 1 cm tolerance that it actually met. Foreign keys going from domain 2 to domain 1; they would have to be removed once the dbs split.
Consequences: It enables exact integer tolerance comparisons, and a diagram with no relationship line crossing the seam. It costs a cm to mm conversion at every form and display, and orphaned sample rounds become possible.
