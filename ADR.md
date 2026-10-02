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

## 2. Domain Split + Snapshot Across the Seam
Date: 2026-09-30
Status: Decided
Context: Separate jobs in the two domains (specs + grading / sample fit review), and must be separable into services for later. A recorded verdict must not change when a spec is later edited or deleted
Decision: Domain 2 only reads domain 1 through get_graded_spec; each domain owns its own schema string, store module and template.
Alternatives considered: Live lookup at report time --> an edited grade rule silently rewrites past verdicts. Snapshot at round creation, measurements later --> nullable measured_mm, half-entered rounds
Consequences: Reports survive style deletion, one function turns it into a HTTP call later. However spec values are stored twice and correcting one doesn't overwrite old rounds.

## 4. Testing Approach: Pure Logic First, Each Store Against Its Own Schema
Date: 2026-10-02
Status: Decided
Context: Coverage has to reach 70% on the core logic of both domains, and the rules that would cost the label money if wrong are the grading math, the tolerance boundary and the all-or-nothing sample round. Domain 2 also has to stay testable without Domain 1
Decision: Test the pure modules (grading.py, review.py, units.py) directly on boundary cases, test each store against a temporary SQLite file built from only its own SCHEMA, and keep Flask test-client tests for the 400/404 paths and the two cross-domain guarantees. Coverage is measured with tests/ omitted.
Alternatives considered: Testing everything through the Flask test client. It reaches the same percentage, but a failure doesn't show whether the math, the SQL or the form parsing broke, and Domain 2's tests would need Domain 1's tables, which hides a seam violation. Mocking SQLite was also rejected, since STRICT types, foreign keys and cascades are behaviour I rely on and need to test for real.
Consequences: test_review.py and test_samples_store.py move to Domain 2's service unchanged; only test_samples_routes.py, which spans both domains, needs rewriting. Templates and the __main__ block (PORT, APP_DEBUG) stay thin and are checked by hand, which is how a stray "+" in base.html passed all 89 tests.
