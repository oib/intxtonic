# Project structure

- **Backend**
  - `src/backend/app/main.py` – FastAPI entrypoint and route wiring.
  - `src/backend/app/api/` – HTTP API routers (auth, posts, tags, admin, etc.).
  - `src/backend/app/core/` – configuration, DB, errors, security utilities.
  - `src/backend/app/db/` – SQL schema and seed data.
  - `src/backend/app/services/` – domain services (AI integration, business logic).
  - `src/backend/app/workers/` – background workers (e.g. translation worker).

- **Frontend**
  - `src/frontend/pages/` – HTML pages (landing, login, dashboard, admin, etc.).
  - `src/frontend/css/` – shared styles and page-specific CSS.
  - `src/frontend/js/` – small JS modules for auth, toasts, i18n, notifications.
  - `src/frontend/assets/` – static assets such as images, illustrations, icons.

- **Docs**
  - `docs/README.md` – main development and deployment guide.
  - `docs/structure.md` – high-level codebase map (this file).

- **Config & Dev**
  - `config/` – environment templates and deployment configuration.
  - `dev/` – scripts, templates, and helper files for local/dev deployment.

- **Localization & i18n**
  - `i18n/` – JSON translation files for UI strings and landing page copy.

- **Root**
  - `requirements.txt` – Python dependencies for backend/worker.
  - `package.json` – Node dependencies and scripts used by tooling.
  - `Makefile` – convenience targets for linting, tests, and dev workflows.
