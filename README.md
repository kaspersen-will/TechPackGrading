# Maison Grader — Tech Pack & Size Grading

A web application that helps a small independent fashion label manage garment measurement specs and check factory samples against them.

## The problem

A small independent label (one designer and one production manager, about 40 styles per season, working with two overseas factories) tracks garment measurements in scattered spreadsheets. When a factory sends a sample, there is no quick way to tell which measurements are out of tolerance or in which sizes.

## Feature domains

The application has two feature domains. Assignment 1 built them as one Flask app; Assignment 2 splits them into two services along the seam below (ADR-6).

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

**Live URL:** https://wnklavoldieu2024ui.z1.web.core.windows.net

Everything runs in my Azure for Students subscription, in resource group `rg-wnklavold-ieu2024`. The UI, the Container Apps and the identity are in Norway East; the SQL server is in Belgium Central, because Norway East and Poland Central refuse new SQL servers for this subscription (ADR-8):

| Resource | Name | Billed |
|---|---|---|
| Storage static website (the UI) | `wnklavoldieu2024ui` | per GB stored and served |
| Container Apps environment (Consumption) | `wnklavold-ieu2024-env` | nothing itself |
| Container App, 0–1 replicas | `wnklavold-ieu2024-specs`, `wnklavold-ieu2024-samples` | per second while a replica runs |
| Log Analytics workspace | created with the environment | per GB of logs |
| SQL server, two Basic databases | `wnklavold-ieu2024-sql-be`, `wnklavold-ieu2024-specs-db`, `…-samples-db` | about $5 a month each |
| Managed identity the pipeline signs in as | `wnklavold-ieu2024-github` | free |

Images are in GHCR: `ghcr.io/kaspersen-will/maison-grader-specs` and `-samples`, tagged with the commit SHA.

### How a deploy works

I'm the only contributor, so I commit straight to `main`. Every push to `main` runs `.github/workflows/cd.yml`, and nothing deploys unless CI passes on that commit:

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
SQL=$PREFIX-sql-be
UI_STORAGE=wnklavoldieu2024ui
GH_REPO=kaspersen-will/TechPackGrading
```

**1. Subscription and region.** Azure for Students allows five regions, and the list differs between subscriptions.

```bash
az login
az account set --subscription "Azure for Students"
az policy assignment list \
  --query "[?displayName=='Allowed resource deployment regions'].parameters.listOfAllowedLocations.value" -o tsv
# empty? the display name differs: az policy assignment list -o table, then look at that assignment
REGION=norwayeast                 # one region from that list, for everything except SQL
SQL_REGION=belgiumcentral          # a region that accepts new SQL servers, checked below
# Which allowed regions accept new SQL servers ("Available"; "Visible" means refused):
SUB=$(az account show --query id -o tsv)
for r in $(az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters.listOfAllowedLocations.value[]" -o tsv); do
  echo "$r $(az rest --method get --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.Sql/locations/$r/capabilities?api-version=2023-08-01-preview" --query status -o tsv)"
done
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

**4. SQL server, two Basic databases, one contained user each.** The free serverless offer isn't available in any region this subscription can create SQL servers in, so each database is Basic (5 DTU, 2 GB, always on; ADR-8). A failed `az sql server create` can reserve the name in the resource group for a while, so check the region first (step 1).

```bash
read -rsp "SQL admin password: " SQL_ADMIN_PW; echo
az sql server create -n "$SQL" -g "$RG" -l "$SQL_REGION" -u sqladmin -p "$SQL_ADMIN_PW"
for s in specs samples; do
  az sql db create -g "$RG" -s "$SQL" -n "$PREFIX-$s-db" \
    --edition Basic --backup-storage-redundancy Local
done
az sql server firewall-rule create -g "$RG" -s "$SQL" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# Open the firewall to this machine only while creating the users.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SQL" -n setup-my-ip \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP"
read -rsp "specs_user password: " SPECS_DB_PASSWORD; echo
read -rsp "samples_user password: " SAMPLES_DB_PASSWORD; echo
for pair in "specs:$SPECS_DB_PASSWORD" "samples:$SAMPLES_DB_PASSWORD"; do
  s=${pair%%:*}; pw=${pair#*:}
  # A contained user exists only in its own database, so it can't reach the other one.
  # db_ddladmin lets it run its own migrations.
  sqlcmd -S "$SQL.database.windows.net" -d "$PREFIX-$s-db" -U sqladmin -P "$SQL_ADMIN_PW" -b -Q "
    CREATE USER ${s}_user WITH PASSWORD = '$pw';
    ALTER ROLE db_ddladmin ADD MEMBER ${s}_user;
    ALTER ROLE db_datareader ADD MEMBER ${s}_user;
    ALTER ROLE db_datawriter ADD MEMBER ${s}_user;"
done
az sql server firewall-rule delete -g "$RG" -s "$SQL" -n setup-my-ip
```

**5. Container Apps.** Scale 0 to 1, so a migration never runs twice at once and an idle system costs nothing. Ingress CORS stays off: the services allow `UI_ORIGIN` themselves, because ingress CORS rejects the JSON preflight. The placeholder image is replaced by the first deploy, which also sets every environment variable and the secret.

```bash
az containerapp env create -n "$PREFIX-env" -g "$RG" -l "$REGION"   # also creates its Log Analytics workspace
# Recent az versions create an "Express" environment, which rejects the revision suffix cd.yml sets.
# Switch it to a standard Consumption (workload profiles) environment; this takes a few minutes.
az rest --method patch \
  --url "https://management.azure.com$(az containerapp env show -n "$PREFIX-env" -g "$RG" --query id -o tsv)?api-version=2025-10-02-preview" \
  --body '{"properties": {"environmentMode": "WorkloadProfiles"}}'
for pair in specs:8000 samples:8001; do
  az containerapp create -n "$PREFIX-${pair%%:*}" -g "$RG" --environment "$PREFIX-env" \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --ingress external --target-port "${pair#*:}" \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done
```

**6. The pipeline's identity.** The pipeline signs in as a user-assigned managed identity with Contributor on this resource group only: no client secret to store or rotate, unlike a service principal. GitHub may send the OIDC subject with names or with numeric IDs, so both are registered.

```bash
az identity create -n "$PREFIX-github" -g "$RG" -l "$REGION"
CLIENT_ID=$(az identity show -n "$PREFIX-github" -g "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n "$PREFIX-github" -g "$RG" --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID"
NUMERIC_SUBJECT=$(gh api "repos/$GH_REPO" --jq '"repo:\(.owner.login)@\(.owner.id)/\(.name)@\(.id):ref:refs/heads/main"')
for pair in "github-main-names|repo:${GH_REPO}:ref:refs/heads/main" "github-main-ids|$NUMERIC_SUBJECT"; do
  az identity federated-credential create -g "$RG" --identity-name "$PREFIX-github" \
    -n "${pair%%|*}" --subject "${pair#*|}" \
    --issuer https://token.actions.githubusercontent.com \
    --audiences api://AzureADTokenExchange
done
az identity federated-credential list -g "$RG" --identity-name "$PREFIX-github" --query "[].subject" -o tsv
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
gh variable set SQL_SERVER     -R "$GH_REPO" -b "$SQL"
```

**8. First deploy.** Push to `main`. If the deploy job fails with "Authentication failed when pulling container image", the new GHCR packages are private: make `maison-grader-specs` and `maison-grader-samples` public (GitHub → Packages → Package settings → Change visibility), then re-run the failed job.

**9. Read access for the professors.** The subscription is in my personal directory, which doesn't know IE accounts, so each professor is invited as a guest first (they get an email and must accept it), then given Reader on the resource group.

```bash
for p in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  id=$(az rest --method post --url https://graph.microsoft.com/v1.0/invitations \
    --body "{\"invitedUserEmailAddress\": \"$p\", \"inviteRedirectUrl\": \"https://portal.azure.com\", \"sendInvitationMessage\": true}" \
    --query invitedUser.id -o tsv)
  az role assignment create --assignee-object-id "$id" --assignee-principal-type User --role Reader --scope "$RG_ID"
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
| "ExpressRevisionSuffixNotSupported" | The environment is in Express mode: switch it as in step 5 |
| "Authentication failed when pulling container image" | GHCR package still private (step 8) |
| `/health` never 200, app restarts | Wrong `DATABASE_URL` password, wrong target port, or the database still resuming |
| UI reads work, every save says "Failed to fetch" | Ingress CORS turned on, or `UI_ORIGIN` isn't the storage endpoint |
| First request after idle: 503 "App port is not ready" | Normal cold start; the UI says to try again in a minute |

## Project documents

- [`ADR.md`](ADR.md): architecture decision records
- [`AI_USAGE.md`](AI_USAGE.md): log of AI assistance used in this project
