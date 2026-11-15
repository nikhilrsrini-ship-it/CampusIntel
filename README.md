# CAMPUSINTEL

CAMPUSINTEL is a modular college student-service and workflow intelligence application. The repository now contains a working student request lifecycle, role-based API, local model pipeline, event analytics, and responsive role-aware frontend.

## Current scope

- Student registration/login, staff/admin provisioning, JWT access tokens, and backend role checks.
- Request creation/tracking, administrative assignment, staff status changes, student reopening, comments, notifications, audit history, feedback, and private attachments.
- PostgreSQL schema and Alembic migrations for the core account, request, event, assignment, prediction, feedback, notification, and audit tables.
- Local TF-IDF/logistic-regression classification; clear `SYNTHETIC` provenance for the built-in demonstration corpus. Suggestions never select a final category, close, reject, or penalize a request.
- TF-IDF duplicate suggestions with optional local Sentence Transformer + FAISS retrieval; requests are never merged automatically.
- Resolution estimates use a historical median only with at least 10 resolved requests; a Random Forest training script requires at least 20 actual resolved records.
- Live database analytics, department workload, event-history process metrics, authorized CSV exports, and an optional PM4Py event-log discovery script.
- Frontend flows for student, staff, admin, account provisioning, tracking, updates, attachments, model suggestions, notifications, and real-record analytics.

This is a local research prototype, not a production-ready institutional deployment. Before using real student data, the institution must configure its official identity, support contact, privacy and retention policy, departments, access policy, model data, and security operations. Email verification and multi-factor authentication are not implemented. Password recovery requires a working SMTP configuration. The interface identifies missing support/privacy configuration instead of inventing trust claims.

## Start locally with Docker Compose

Start Docker Desktop, copy `.env.example` to `.env`, replace the sample database password and JWT secret, and configure the public institution details. `VITE_INSTITUTION_NAME`, `VITE_SUPPORT_EMAIL`, and `VITE_PRIVACY_URL` are shown to users. Then run:

```powershell
docker compose up --build
```

After changing any `VITE_` setting, rebuild the frontend with `docker compose up --build -d`; these settings are embedded in the frontend image.

Open <http://localhost:5173>, API documentation at <http://localhost:8000/docs>, liveness at `/healthz`, and database readiness at `/readyz`. The public trust panel reports live readiness, access scope, configured support/privacy links, and whether demonstration mode is enabled. The backend applies migrations, seeds the catalog, and (when `DEMO_MODE=true`) generates labeled synthetic examples for the baseline model. Synthetic results are for demonstration only.

## Password recovery

The local Compose stack includes Mailpit as a development-only email catcher. On the sign-in page, choose **Forgot password?**, enter the account email, then open <http://localhost:8025> and use the reset link in the captured message. Local reset email is not delivered to external inboxes. The link is single-use and expires after `PASSWORD_RESET_EXPIRE_MINUTES` (30 by default); tokens are stored as hashes and using a reset link revokes existing login sessions for that account.

For an institutional deployment, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, the appropriate TLS/authentication settings, and `FRONTEND_PUBLIC_URL` in `.env`; set `VITE_EMAIL_PREVIEW_URL` to empty so the development inbox is not advertised. Rebuild the frontend after changing `VITE_` values. Reset responses do not disclose whether an email belongs to an account. Email verification and multi-factor authentication are separate features and are not currently implemented.

Create the first super administrator after the services start. In PowerShell, set credentials for this command only; use at least 16 characters for the password:

```powershell
$env:INITIAL_ADMIN_EMAIL = "admin@your-college.edu"
$env:INITIAL_ADMIN_PASSWORD = "replace-with-a-long-random-secret"
$env:INITIAL_ADMIN_NAME = "Institution Administrator"
docker compose exec -e INITIAL_ADMIN_EMAIL -e INITIAL_ADMIN_PASSWORD -e INITIAL_ADMIN_NAME backend python -m scripts.bootstrap_superadmin
Remove-Item Env:INITIAL_ADMIN_EMAIL, Env:INITIAL_ADMIN_PASSWORD, Env:INITIAL_ADMIN_NAME
```

The seed is idempotent. PostgreSQL data, private attachments, and model artifacts use named Docker volumes. `docker compose down` preserves them; `docker compose down -v` deletes local data.

## Local backend and frontend

Use Python 3.12+ and Node.js 24+. Start PostgreSQL, then from `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = "postgresql+psycopg://campusintel:your-password@localhost:5432/campusintel"
$env:JWT_SECRET = "replace-with-a-long-random-secret"
alembic upgrade head
python -m scripts.seed_catalog
python -m scripts.generate_synthetic_dataset
python -m scripts.train_classification_model
uvicorn app.main:app --reload
```

The last two commands use only explicitly labeled synthetic data. Set `CLASSIFICATION_MODEL_PATH` to a trained model built from authorized, institution-labeled examples before using classification as an institutional aid.

From `frontend/` in a second terminal:

```powershell
npm.cmd install
npm.cmd run dev
npm.cmd test
```

## Migrations and accounts

After changing SQLAlchemy models, create and review a migration from `backend/`:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Students can register. Staff and admin accounts must be created by an administrator from the secured workspace or by the initial bootstrap script. Students cannot set their own roles. `ADMIN` accounts can provision staff; only `SUPER_ADMIN` accounts can provision other administrators.

## Local semantic model and process mining (optional)

Core services run without transformer weights. To enable the improved semantic classifier and FAISS duplicate retrieval, install the pinned optional dependencies with `python -m pip install -r requirements-ml.txt`, place an approved local Sentence Transformer model directory at the path configured by `EMBEDDING_MODEL_PATH`, and run:

```powershell
python -m scripts.train_semantic_classifier --embedding-model .models/all-MiniLM-L6-v2
```

The loader uses local files only; it does not fetch model code or weights at runtime. The duplicate index is rebuilt from authorized PostgreSQL records and is not an authoritative store. For process discovery, export and analyze authorized workflow events:

```powershell
python -m scripts.export_process_logs
python -m scripts.run_process_mining
python -m scripts.evaluate_models
```

The resolution model trains only from resolved database cases and stops unless at least 20 are available:

```powershell
python -m scripts.train_resolution_model
```

Evaluation files contain measured outputs from the selected dataset and seed. Do not interpret metrics from synthetic examples as research evidence or institutional performance.

## Tests

Backend tests use an isolated in-memory SQLite database and cover registration, ownership boundaries, role checks, assignment, status history, comment visibility, attachments, analytics, and notifications:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Frontend tests and production build:

```powershell
cd frontend
npm.cmd test
npm.cmd run build
```

PostgreSQL container startup and production deployment still require verification on a machine with Docker/PostgreSQL. Review [the architecture](docs/architecture.md), [setup guide](docs/setup_guide.md), [research protocol](research/experiment_protocol.md), [development log](DEVELOPMENT_LOG.md), and [tasks](TASKS.md) for limitations and current status.
