# CAMPUSINTEL tasks

## Completed

- [x] Inspect the repository and available runtimes.
- [x] Create Phase 1 frontend/backend/database foundation.
- [x] Add Docker Compose, Alembic wiring, architecture and setup documentation.
- [x] Phase 2: 15 normalized PostgreSQL models, reviewed Alembic schema migration, authentication, roles, and backend access guards.
- [x] Phase 3: request submission/tracking, assignment/status history, comments, notifications, feedback, private attachments, and audit records.
- [x] Phase 4 baseline: local TF-IDF classifier, synthetic corpus generator, and reproducible metrics output.
- [x] Phase 5 baseline: TF-IDF duplicate suggestions; optional local Sentence Transformer + FAISS pathway.
- [x] Phase 6 baseline: historical median estimates and a Random Forest training/evaluation script.
- [x] Phase 7: event analytics and optional PM4Py log discovery scripts.
- [x] Phase 8 initial role-aware flows, request tools, workload analytics, and authorized CSV export.
- [x] Phase 9 initial isolated API and frontend tests.
- [x] Phase 10 setup, architecture, research protocol, and limitations docs.

## Remaining verification and institutional configuration

- [ ] Run Compose against live PostgreSQL and verify fresh install, migration, seeding, startup, readiness, and full request lifecycle when Docker is available.
- [ ] Run optional Sentence Transformer/FAISS and PM4Py integrations; those dependencies/model weights are intentionally optional and not downloaded at runtime.
- [ ] Run resolution-model training against at least 20 approved, resolved institutional cases.
- [ ] Re-evaluate classification and duplicate retrieval with authorized, representative, institution-labeled data; do not use synthetic scores as research evidence.
- [ ] Configure institution-specific categories, escalation transitions, email domain policy, retention, backups, malware scanning, HTTPS, and secret management before production use.
- [ ] Expand automated coverage to PostgreSQL integration and end-to-end browser workflows.
