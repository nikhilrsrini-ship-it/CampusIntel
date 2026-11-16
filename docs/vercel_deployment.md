# Vercel deployment notes

The root `vercel.json` defines two Vercel Services for one deployment:

- `frontend` builds the Vite app from `frontend/` and receives public page traffic.
- `backend` runs the FastAPI app from `backend/` and receives public API traffic at `/api/*`.

The browser calls the backend through the same public domain using `/api`. Vercel routes those requests to `backend`; a backend service route transform removes `/api` before FastAPI sees the request, preserving the API's existing route definitions. FastAPI's root path remains `/api` on Vercel so generated API documentation and schema URLs use the public prefix. In local development, the frontend keeps using `http://localhost:8000` unless `VITE_API_URL` is supplied.

## Vercel project setup

1. Import this Git repository into Vercel and configure the project's framework preset as **Services**. Vercel currently documents Services as a beta feature.
2. Confirm the monorepo root is the repository root, where `vercel.json` lives.
3. Add the environment variables below to the Vercel project. Use Vercel's Production/Preview scopes as appropriate; never commit real secrets.
4. Deploy after the required database schema is migrated and the catalog/admin setup is complete.

## Required runtime configuration

- `DATABASE_URL`: connection string for a reachable managed PostgreSQL database. The Compose-only `db` hostname does not exist in Vercel.
- `JWT_SECRET`: long, randomly generated signing secret.
- `FRONTEND_PUBLIC_URL`: the deployed site's public base URL, used in password-reset links.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and the appropriate SMTP credentials/TLS settings: required to deliver reset emails to real users. Mailpit is local-only.
- Optional institution settings: `VITE_INSTITUTION_NAME`, `VITE_SUPPORT_EMAIL`, `VITE_PRIVACY_URL`, and `VITE_PASSWORD_RESET_EXPIRE_MINUTES`. Vite variables are embedded at build time and are public; do not put secrets in them.
- `VITE_API_URL` is optional on Vercel. The frontend defaults to same-origin `/api` in production. If set, use `/api`, not a private binding URL.

## Before using real requests

Vercel does not run the Docker Compose startup command. Apply Alembic migrations to the managed database and run the catalog seed/admin bootstrap through a controlled one-off operation before users sign in. Do not run schema changes or bootstrap a superadmin automatically on every serverless function startup.

The current attachment implementation writes to local private storage, which is not durable across serverless deployments. Configure durable private object storage before relying on uploads. The demo classifier is trained during Compose startup, so Vercel will not automatically create that model artifact; ML suggestions may be unavailable until a suitable artifact is deployed. The managed database, SMTP delivery, backups, retention, and access controls must be configured for the institution before real student data is used.

## Local Vercel Services development

With a supported Vercel CLI version and the services feature available to the account, run `vercel dev` from the repository root to exercise the services routing locally. Docker Compose remains the project's existing local stack and includes PostgreSQL and Mailpit.
