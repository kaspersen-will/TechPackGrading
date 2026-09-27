## 1. Framework Choice
Date: 2026-09-27
Status: Decided
Context: The app is mostly data entry and review: entering points of measure and grade rules, generating size runs, and recording factory sample measurements against tolerances. It must run as one Python process with SQLite and serve its own pages.
Decision: Use Flask with Jinja templates to serve server-rendered HTML forms and pages from a single process.
Alternatives considered: FastAPI. FastAPI's async support helps when a request spends time waiting on slow I/O, wheras this app's I/O is local SQLite reads and writes. Furthermore its other strengths, Pydantic and auto-generated API docs, are for JSON APIs, and my app serves HTML forms.
Consequences: Flask enforces no structure, so keeping the two domains separable is my responsibility, not the framework's. Flask renders HTML pages directly with its built-in template engine (Jinja), so I won't need a separate frontend.
