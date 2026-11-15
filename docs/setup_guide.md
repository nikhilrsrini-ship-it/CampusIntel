# Development setup

## Docker Compose

Install Docker Compose, copy the project-root `.env.example` to `.env`, change the database password and JWT secret, and run `docker compose up --build`. The API waits for PostgreSQL health, applies Alembic migrations, seeds default departments/categories, and by default trains a local classifier using explicitly labeled synthetic demonstration text. Open the web app at port 5173, API docs at port 8000 `/docs`, and readiness at `/readyz`.

Run `python -m scripts.bootstrap_superadmin` inside the backend container with `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` supplied to that command. The bootstrap script refuses an existing email and requires a 16-character password. Subsequent accounts are provisioned by an authorized administrator.

The named volumes hold PostgreSQL, private attachments, and model artifacts. `docker compose down` retains data; `docker compose down -v` removes it.

## Local services

Python 3.12+ and Node.js 24+ are required. Create a Python virtual environment in `backend/`, install `requirements-dev.txt`, start a PostgreSQL instance, set `DATABASE_URL` and `JWT_SECRET`, apply Alembic migrations, seed the catalog, then start Uvicorn. In `frontend/`, install with `npm.cmd install` and run `npm.cmd run dev`.

The optional `requirements-ml.txt` provides Sentence Transformers, FAISS CPU, and PM4Py. Keep model weights in an approved local directory and set `EMBEDDING_MODEL_PATH`; the runtime does not download weights. Classification and resolution artifacts are stored below `.models/` by default. `.models/` is ignored by source control.

## Troubleshooting

- API returns 503 from `/readyz`: check PostgreSQL health and `DATABASE_URL`.
- Category list is empty: run `python -m scripts.seed_catalog` from `backend/`.
- No model suggestion: run the baseline dataset generation/training steps or configure a trained local artifact.
- Resolution estimate unavailable: the system needs sufficient resolved request history (ten in the category for the historical median; twenty institutional resolved rows to train the Random Forest).
- Attachments fail validation: only PDF, PNG, or JPEG content up to the configured byte limit is accepted.

Use synthetic records only for development. For institutional data, define access controls, retention policy, model validation, backups, and HTTPS before deployment.
