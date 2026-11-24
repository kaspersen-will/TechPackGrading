# The samples service. Build from this folder: docker build -t samples services/samples
FROM python:3.13-slim

# No .pyc files in a read-only app folder; logs reach stdout straight away.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001

WORKDIR /app

# Dependencies first, so editing code doesn't reinstall them. Versions are pinned.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Named files only, never COPY . . : no tests, .env or local venv end up in the image.
COPY app.py web.py db.py migrate.py ./
COPY migrations/ migrations/
COPY samples/ samples/

# The commit this image was built from, reported by /health. CI passes it as a build arg.
ARG GIT_SHA=dev
ENV GIT_SHA=${GIT_SHA}

# Unprivileged user; it can read /app but not change it.
RUN useradd --no-create-home --uid 10001 app
USER app

EXPOSE 8001

# Migrations run once, before gunicorn starts, so its workers can't race on them.
# --timeout 120: a request may wait for a paused database to resume (DB_CONNECT_TIMEOUT_S, 90 s);
# gunicorn's default 30 s would kill the worker first.
# --no-control-socket: gunicorn 27 would otherwise create a socket in a home folder the user doesn't have.
CMD ["sh", "-c", "python migrate.py && exec gunicorn 'app:create_app()' --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 --no-control-socket"]
