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

`.github/workflows/ci.yml` runs on every push to a branch and every pull request: it validates `system.yaml` against `system.schema.json` and both `openapi.yaml` files, then for each service runs ruff and the tests with coverage (failing under 70%) against a throwaway SQL Server started from this compose file with random passwords, and builds the image. CI never connects to Azure SQL. On `main` it runs only as the first job of the deploy workflow, and there it also pushes the images.

## Deployment to Azure

**Live URL:** _added once the first deploy is up_

Everything runs in the Azure for Students subscription, in resource group `rg-wnklavold-ieu2024`:

| Resource | Name | Billed |
|---|---|---|
| Storage static website (the UI) | `wnklavoldieu2024ui` | per GB stored and served |
| Container Apps environment (Consumption) | `wnklavold-ieu2024-env` | nothing itself |
| Container App, 0–1 replicas | `wnklavold-ieu2024-specs`, `wnklavold-ieu2024-samples` | per second while a replica runs |
| Log Analytics workspace | created with the environment | per GB of logs |
| SQL server, two serverless databases (free offer) | `wnklavold-ieu2024-sql`, `…-specs-db`, `…-samples-db` | per vCore second while resumed |
| Managed identity the pipeline signs in as | `wnklavold-ieu2024-github` | free |

Images are in GHCR: `ghcr.io/kaspersen-will/maison-grader-specs` and `-samples`, tagged with the commit SHA.

### How a deploy works

Changes reach `main` only through pull requests, so CI has already run on the branch. Merging runs `.github/workflows/cd.yml`:

1. CI runs on the merged commit (`workflow_call`) and, because this is `main`, pushes both images tagged with the commit SHA.
2. Only if CI passed, the deploy job signs in to Azure as `wnklavold-ieu2024-github` over OIDC: no Azure password is stored anywhere.
3. For each service it sets the `database-url` secret, built from the `SPECS_DB_PASSWORD` / `SAMPLES_DB_PASSWORD` GitHub secret, then points the Container App at the new image with every environment variable (`--replace-env-vars`), so Azure always matches `system.yaml`.
4. It writes `ui/config.js` with the two services' HTTPS addresses and uploads `ui/` to the storage account's `$web` container.
5. It calls `/health` on both services for up to 6 minutes each and fails the run unless each answers 200 with this commit's SHA. The wait covers a container starting from zero, the database resuming from pause and the migrations.

### Initial setup (once, by hand)

Run in Bash (Azure Cloud Shell has `az`, `gh` and `sqlcmd`). In zsh, `"repo:$GH_REPO:ref:…"` silently loses characters, so type `bash` first. No password is written here or anywhere in the repository: they are typed at a prompt and stored only as GitHub secrets.

```bash
PREFIX=wnklavold-ieu2024
RG=rg-$PREFIX
UI_STORAGE=wnklavoldieu2024ui
GH_REPO=kaspersen-will/TechPackGrading
```

**1. Subscription and region.** Azure for Students allows five regions, and the list differs between subscriptions.

```bash
az login
az account set --subscription "Azure for Students"
az policy assignment list \
  --query "[?displayName=='Allowed resource deployment regions'].parameters.listOfAllowedLocations.value" -o tsv
REGION=__REGION__                 # one region from that list, used for everything
SQL_REGION=__SQL_REGION__          # the free SQL offer isn't in every region (not spaincentral)
```

**2. Providers and resource group.**

```bash
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register -n "$p" --wait
done
az group create -n "$RG" -l "$REGION"
RG_ID=$(az group show -n "$RG" --query id -o tsv)
```

**3. The UI: a Storage static website.** Its web endpoint is the system's public URL and the only origin the services accept (`UI_ORIGIN`).

```bash
az storage account create -n "$UI_STORAGE" -g "$RG" -l "$REGION" --sku Standard_LRS --kind StorageV2
az storage blob service-properties update --account-name "$UI_STORAGE" --auth-mode key \
  --static-website --index-document index.html
az storage account show -n "$UI_STORAGE" -g "$RG" --query primaryEndpoints.web -o tsv   # -> public_url in system.yaml
```

**4. SQL server, two serverless databases, one contained user each.** The free offer fixes auto-pause at 60 minutes and the size at 32 GB, so `--auto-pause-delay` and `--max-size` are not passed.

```bash
read -rsp "SQL admin password: " SQL_ADMIN_PW; echo
az sql server create -n "$PREFIX-sql" -g "$RG" -l "$SQL_REGION" -u sqladmin -p "$SQL_ADMIN_PW"
for s in specs samples; do
  az sql db create -g "$RG" -s "$PREFIX-sql" -n "$PREFIX-$s-db" \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 \
    --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local \
    --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
az sql server firewall-rule create -g "$RG" -s "$PREFIX-sql" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# Open the firewall to this machine only while creating the users.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$PREFIX-sql" -n setup-my-ip \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP"
read -rsp "specs_user password: " SPECS_DB_PASSWORD; echo
read -rsp "samples_user password: " SAMPLES_DB_PASSWORD; echo
for pair in "specs:$SPECS_DB_PASSWORD" "samples:$SAMPLES_DB_PASSWORD"; do
  s=${pair%%:*}; pw=${pair#*:}
  # A contained user exists only in its own database, so it can't reach the other one.
  # db_ddladmin lets it run its own migrations.
  sqlcmd -S "$PREFIX-sql.database.windows.net" -d "$PREFIX-$s-db" -U sqladmin -P "$SQL_ADMIN_PW" -b -Q "
    CREATE USER ${s}_user WITH PASSWORD = '$pw';
    ALTER ROLE db_ddladmin ADD MEMBER ${s}_user;
    ALTER ROLE db_datareader ADD MEMBER ${s}_user;
    ALTER ROLE db_datawriter ADD MEMBER ${s}_user;"
done
az sql server firewall-rule delete -g "$RG" -s "$PREFIX-sql" -n setup-my-ip
```

**5. Container Apps.** Scale 0 to 1, so a migration never runs twice at once and an idle system costs nothing. Ingress CORS stays off: the services allow `UI_ORIGIN` themselves, because ingress CORS rejects the JSON preflight. The placeholder image is replaced by the first deploy, which also sets every environment variable and the secret.

```bash
az containerapp env create -n "$PREFIX-env" -g "$RG" -l "$REGION"   # also creates its Log Analytics workspace
for pair in specs:8000 samples:8001; do
  az containerapp create -n "$PREFIX-${pair%%:*}" -g "$RG" --environment "$PREFIX-env" \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --ingress external --target-port "${pair#*:}" \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done
```

**6. The pipeline's identity.** IE accounts can't create service principals, so the pipeline signs in as a user-assigned managed identity with Contributor on this resource group only. GitHub may send the OIDC subject with names or with numeric IDs, so both are registered.

```bash
az identity create -n "$PREFIX-github" -g "$RG" -l "$REGION"
CLIENT_ID=$(az identity show -n "$PREFIX-github" -g "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n "$PREFIX-github" -g "$RG" --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID"
NUMERIC_SUBJECT=$(gh api "repos/$GH_REPO" --jq '"repo:\(.owner.login)@\(.owner.id)/\(.name)@\(.id):ref:refs/heads/main"')
for subject in "repo:${GH_REPO}:ref:refs/heads/main" "$NUMERIC_SUBJECT"; do
  az identity federated-credential create -g "$RG" --identity-name "$PREFIX-github" \
    -n "github-main-$(echo "$subject" | md5sum | cut -c1-8)" \
    --issuer https://token.actions.githubusercontent.com --subject "$subject" \
    --audiences api://AzureADTokenExchange
done
```

**7. GitHub secrets and variables.**

```bash
gh secret set AZURE_CLIENT_ID       -R "$GH_REPO" -b "$CLIENT_ID"
gh secret set AZURE_TENANT_ID       -R "$GH_REPO" -b "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID -R "$GH_REPO" -b "$(az account show --query id -o tsv)"
gh secret set SPECS_DB_PASSWORD     -R "$GH_REPO" -b "$SPECS_DB_PASSWORD"
gh secret set SAMPLES_DB_PASSWORD   -R "$GH_REPO" -b "$SAMPLES_DB_PASSWORD"
gh variable set PREFIX         -R "$GH_REPO" -b "$PREFIX"
gh variable set RESOURCE_GROUP -R "$GH_REPO" -b "$RG"
gh variable set UI_STORAGE     -R "$GH_REPO" -b "$UI_STORAGE"
```

**8. First deploy.** Merge a pull request into `main`. The deploy job fails the first time on purpose: new GHCR packages are private, so Azure can't pull them. Make `maison-grader-specs` and `maison-grader-samples` public (GitHub → Packages → Package settings → Change visibility), then re-run the failed job.

**9. Read access for the professors.**

```bash
for p in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee "$p" --role Reader --scope "$RG_ID"
done
```

From here on, only the pipeline changes anything.

### When a deploy fails

Read the logs before guessing:

```bash
az containerapp logs show -n wnklavold-ieu2024-specs -g rg-wnklavold-ieu2024 --follow
az containerapp logs show -n wnklavold-ieu2024-specs -g rg-wnklavold-ieu2024 --type system   # start-up and probe events
```

| Symptom | Likely cause |
|---|---|
| `azure/login`: "No matching federated identity record" | OIDC subject mismatch (zsh, or the numeric-ID form): compare with `az identity federated-credential list` |
| "Authentication failed when pulling container image" | GHCR package still private (step 8) |
| `/health` never 200, app restarts | Wrong `DATABASE_URL` password, wrong target port, or the database still resuming |
| UI reads work, every save says "Failed to fetch" | Ingress CORS turned on, or `UI_ORIGIN` isn't the storage endpoint |
| First request after idle: 503 "App port is not ready" | Normal cold start; the UI says to try again in a minute |

## Project documents

- [`ADR.md`](ADR.md): architecture decision records
- [`AI_USAGE.md`](AI_USAGE.md): log of AI assistance used in this project
