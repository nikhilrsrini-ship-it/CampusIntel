# Development log

## Phase 1 — Project foundation

- Created the React/TypeScript frontend, FastAPI application, PostgreSQL Compose service, SQLAlchemy session/base, and Alembic configuration.
- Added liveness and database readiness endpoints, architecture notes, and setup instructions.

## Phase 2 — Data model and access control

- Added 15 PostgreSQL models and the core Alembic schema migration.
- Implemented account registration/login, password hashing, signed access tokens, role and resource authorization, and super administrator bootstrap.
- Added catalog, administration, audit, and model-management API foundations.

## Phase 3 — Student services workflow

- Implemented request submission and tracking, assignment history, guarded status transitions, comments, notifications, feedback, private attachments, and audit events.
- Added student/staff/admin workspaces and live record-based workload analytics and CSV export.
- Added baseline classification, duplicate candidate suggestions, historical resolution estimates, and workflow analytics with explicit synthetic-data provenance and optional local semantic retrieval/process mining.
- Rewrote setup, architecture, and research documentation; updated `TASKS.md` with completed work and remaining deployment/institutional checks.

## Verification

- Backend tests: 6 passed.
- Frontend tests: 2 passed; production build passed.
- Frontend dependency audit: 0 vulnerabilities.
- Python source compilation passed; Compose YAML parsed successfully; Alembic generated PostgreSQL SQL through the latest migration.
- Docker was unavailable during the initial scaffold review. It has since been installed; the live PostgreSQL stack, migration/seed startup, and service readiness have been verified. Optional semantic/FAISS/PM4Py paths and institution-data model evaluation still require local prerequisites and authorized representative data.

## Trust and transparency update

- Fixed optional blank student identifiers so registration does not collide with the unique identifier constraint; administrators can provision student profiles from the account workspace.
- Added password show/hide controls for passwords being entered; saved passwords remain one-way hashes.
- Added a user-facing trust panel with live API/database readiness, role-based visibility, collected-data summary, model limitations, and explicit missing-policy/support notices.
- Added administrator environment/policy status and configurable institution name, support email, privacy link, and demo-mode display. Updated the brown/beige visual theme.
- Verification: frontend TypeScript production build passed; Docker Compose rebuilt and restarted the app; frontend and Vite app module returned HTTP 200, and `/readyz` confirmed database connectivity.
- Password recovery now uses hashed, single-use expiring email tokens, account-enumeration-safe responses, per-account request limits, and session revocation; local Compose captures mail in Mailpit.
- Remaining institutional trust prerequisites are deliberately called out: configure production SMTP and official support/privacy information, define retention and response standards, and implement email verification and MFA before real student deployment.
