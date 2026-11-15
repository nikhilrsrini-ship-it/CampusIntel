# CAMPUSINTEL architecture

## Runtime

The application is a modular monolith. React/TypeScript/Vite calls FastAPI REST endpoints. FastAPI owns authorization, request lifecycle operations, audit events, analytics, and local inference services. SQLAlchemy 2.x and PostgreSQL persist all application records; Alembic contains reviewed schema changes. Docker Compose runs the local database, API, and UI.

```text
Browser -> React/Vite -> FastAPI -> PostgreSQL
                                |-> local scikit-learn and optional Sentence Transformers/FAISS
                                |-> event-log analytics and optional PM4Py discovery
```

`/healthz` reports process liveness. `/readyz` executes a database query. API documentation is available at `/docs` in development.

## Data model and workflow

The current migration creates users, departments, request categories, service requests, attachments, append-only workflow events, assignment history, comments, staff/department membership, classification and resolution predictions, feedback, notifications, audit logs, and model experiments. Workflow changes create `request_events` rows; assignments create history rows; the database remains the source of truth.

Student queries scope to the authenticated student. Staff queries scope to requests assigned to them or their department membership. Institution-wide exports and analytics require an administrator. Internal comments are filtered at the API. Attachment files use private local storage, random stored names, MIME/signature checks, and authenticated download endpoints.

## Intelligence and data provenance

The baseline classifier is a local TF-IDF/logistic-regression pipeline. Demo training records include `dataset_type=SYNTHETIC`; prediction history retains this provenance and the UI identifies suggestions as unverified. Suggested classifications do not overwrite the selected category or cause an automatic workflow outcome.

Duplicate candidates use TF-IDF cosine similarity by default. Optional local Sentence Transformer embeddings plus FAISS improve retrieval when a permitted model directory is configured. The FAISS index is rebuilt from database requests and is disposable. Resolution estimation uses a category median when at least ten historical cases exist; a Random Forest training script requires at least twenty resolved cases and records metrics. Process metrics and PM4Py discovery derive from request event records, not fixed dashboard constants.

Synthetic data is only for local demonstration and controlled pipeline checks. Model experiments must use a documented dataset, reproducible seed, train/test protocol, and should be re-run with institution-authorized labeled data before institutional use.

## Security boundaries

Authorization is enforced on backend dependencies and scoped queries. Student registration creates only `STUDENT` users. Staff and administrator accounts require privileged provisioning. Passwords use salted PBKDF2-HMAC-SHA256. Bearer tokens are signed with a configurable secret and expire. Secrets are environment configuration, not source files. Audit metadata excludes passwords, tokens, and attachment contents.

Attachments are not served from a public static directory. Current storage is a private local volume; deployment needs institution-specific retention, backup, malware scanning, and access monitoring before accepting sensitive production documents. Use HTTPS and a strong secret in any non-local deployment.

## Known limitations

- Docker/PostgreSQL startup was not exercised in the current machine because Docker is not installed.
- Semantic embeddings and PM4Py are optional extras; the core stack uses TF-IDF and direct event analytics if optional weights/packages are absent.
- Synthetic training metrics are not evidence of improved performance on real campus requests.
- There is no SMTP/SMS integration, SSO, malware scanner, college calendar, or production object store yet.
- Local development defaults are not a production security configuration.
