# CAMPUSINTEL

CAMPUSINTEL is a student-services request portal and workflow research prototype. Students can submit and track support requests; staff can work on assigned requests; administrators can manage accounts, route work, and review service activity.

> **Status:** Research/demo prototype. It is not ready for real institutional data until campus identity, support and privacy policies, SMTP, security operations, and access rules are configured and reviewed. The built-in machine-learning examples use synthetic data.

## Features

- **Student portal:** account registration, request submission, status history, comments, attachments, notifications, and post-resolution feedback.
- **Staff workspace:** scoped request queue, status updates, student-visible replies, and internal notes.
- **Administration:** account provisioning, request routing, department workload, live workflow summaries, audit history, and authorized CSV export.
- **Request suggestions:** local category classification, duplicate candidates, and resolution estimates. Suggestions are advisory; staff make decisions and requests are never merged automatically.
- **Password recovery:** email reset links that expire and can be used once. Completing a reset revokes existing sessions for that account.
- **Transparency:** role-based access information, live database readiness, model-data disclosures, and visible notices when campus support or privacy details are not configured.

## Technology

- React, TypeScript, and Vite
- FastAPI, SQLAlchemy, and Alembic
- PostgreSQL
- Docker Compose
- Local scikit-learn baseline models; optional Sentence Transformers, FAISS, and PM4Py integrations

## Run with Docker Desktop

Start Docker Desktop. In PowerShell, from the project root, create a local environment file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Change `POSTGRES_PASSWORD` and use the same value in `DATABASE_URL`. Replace `JWT_SECRET` with a long, random secret. The `.env` file is ignored by Git; keep it private.

Build and start the services:

```powershell
docker compose up --build -d
docker compose ps
```

Wait for the database and backend to report **healthy**. Then open:

- Student/admin portal: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- Database readiness: <http://localhost:8000/readyz>
- Local development email inbox: <http://localhost:8025>

Compose runs PostgreSQL, the API, the frontend, and Mailpit. Reset emails are captured by Mailpit and **are not sent to real email inboxes** in the local setup. Mailpit’s web interface is bound to localhost. Its default ports and Docker setup are documented in the [Mailpit installation guide](https://mailpit.axllent.org/docs/install/docker/).

### Create the first administrator

Create a superadmin once, using an email you control. This PowerShell example prompts for the password without echoing it; use at least 16 characters.

```powershell
$env:INITIAL_ADMIN_EMAIL = Read-Host "Administrator email"
$env:INITIAL_ADMIN_NAME = Read-Host "Administrator name"
$secureAdminPassword = Read-Host "Choose administrator password (16+ characters)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAdminPassword)
try {
    $env:INITIAL_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    docker compose exec -e INITIAL_ADMIN_EMAIL -e INITIAL_ADMIN_PASSWORD -e INITIAL_ADMIN_NAME backend python -m scripts.bootstrap_superadmin
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    $secureAdminPassword.Dispose()
    Remove-Item Env:INITIAL_ADMIN_EMAIL, Env:INITIAL_ADMIN_PASSWORD, Env:INITIAL_ADMIN_NAME -ErrorAction SilentlyContinue
    Remove-Variable secureAdminPassword, passwordPointer -ErrorAction SilentlyContinue
}
```

On success, the command prints `Initial super administrator created.` Sign in at <http://localhost:5173> with the email and password you supplied. If it says the account already exists, bootstrap did not change its password; use the password-reset flow instead.

Students can self-register. Administrators can also create student or staff accounts from the **Team** area. Only superadmins can create additional administrators.

### Reset a forgotten password

1. On the sign-in screen, choose **Forgot password?** and enter the account email.
2. Open <http://localhost:8025> and find the reset email captured by Mailpit.
3. Follow its link and choose a new password.

The app gives the same confirmation whether or not an active account matches the email. Reset links are single-use and expire after 30 minutes by default. Existing sessions for the account are invalidated after a successful reset. Passwords are stored as hashes; the app cannot reveal a saved password.

For a real deployment, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, SMTP authentication/TLS settings, and `FRONTEND_PUBLIC_URL` in `.env`. Set `VITE_EMAIL_PREVIEW_URL` to empty so the local inbox is not advertised. Rebuild after changing any `VITE_` setting:

```powershell
docker compose up --build -d
```

### Stop and start later

```powershell
docker compose down
docker compose up -d
```

`docker compose down` preserves PostgreSQL, uploads, and model artifacts in named volumes. **`docker compose down -v` deletes those volumes and their data.**

## Institution configuration

Set these values in `.env` before sharing the portal with students:

| Setting | Purpose |
| --- | --- |
| `VITE_INSTITUTION_NAME` | Name shown in the portal |
| `VITE_SUPPORT_EMAIL` | Institution support contact |
| `VITE_PRIVACY_URL` | Link to the institution privacy notice |
| `FRONTEND_PUBLIC_URL` | Public base URL used in password-reset emails |
| `SMTP_*` | Email server and sender configuration for reset messages |
| `PASSWORD_RESET_EXPIRE_MINUTES` | Reset-link lifetime; defaults to 30 minutes |
| `DEMO_MODE` | Generates the synthetic baseline-model demo data when enabled |

Vite settings beginning with `VITE_` are embedded in the frontend image at build time. Rebuild the frontend after changing them.

## Model and research notes

The default model corpus contains synthetic examples for demonstration; it is not institutional evidence and should not be used to claim real-world model quality. Classification, duplicate, and resolution outputs are suggestions only. Staff remain responsible for reviewing and routing requests.

For the research protocol, data description, and evaluation guidance, see:

- [Architecture](docs/architecture.md)
- [Setup guide](docs/setup_guide.md)
- [Experiment protocol](backend/research/experiment_protocol.md)
- [Dataset documentation](backend/research/dataset_documentation.md)
- [Evaluation metrics](backend/research/evaluation_metrics.md)
- [Methodology](backend/research/research_methodology.md)

Optional semantic retrieval and process-mining workflows are described in the setup and research documents. They require additional dependencies, local model weights, or authorized institutional data.

## Development

### Backend

Use Python 3.12 or newer. From `backend/` in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The backend requires a running PostgreSQL database for normal development. Docker Compose is the simplest way to start all services together.

### Frontend

Use Node.js 24 or newer. From `frontend/`:

```powershell
cd frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
```

### Database migrations

From `backend/`, after changing SQLAlchemy models:

```powershell
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Review generated migrations before applying them to any shared database. Compose applies existing migrations automatically at backend startup.

## Troubleshooting

- **`localhost` refuses to connect:** make sure Docker Desktop is running, then run `docker compose up -d` and check `docker compose ps`.
- **Backend is not running:** inspect `docker compose logs --tail 100 backend` and wait for the backend health check to pass.
- **Forgot-password email is missing:** in the local setup, check Mailpit at <http://localhost:8025>. Local reset mail is not delivered externally.
- **Institution links are missing:** set the corresponding `VITE_` settings in `.env`, then rebuild with `docker compose up --build -d`.

## Production readiness

Before using real student data, an institution must review and configure its official identity, role/access policies, privacy notice, retention schedule, support contact, response expectations, SMTP, HTTPS, secrets, backups, and attachment scanning. Email verification, multi-factor authentication, and institutional SSO are not implemented. The local Docker Compose configuration is for development and demonstration, not a production deployment recipe.
