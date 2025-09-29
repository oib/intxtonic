# 📂 Project Folder Hierarchy

This document outlines the recommended project folder structure, optimized for **Windsurf** development and deployment.

---

## Project Root

```
project/
│
├── docs/                             # Documentation root
│   └── bootstrap/                    # Bootstrapping specs consumed by Windsurf
│       ├── concept.md
│       ├── layout.md
│       ├── admin.md
│       ├── tag.md
│       ├── db.md
│       └── dirs.md                   # This file
│
├── windsurf/                         # Windsurf IDE orchestration
│   ├── prompts/                      # High-level prompt blueprints (coding, review, refactor)
│   │   ├── coding.md
│   │   ├── review.md
│   │   └── refactor.md
│   ├── tasks/                        # Step-by-step task flows for Windsurf runs
│   │   ├── backend-boot.md
│   │   ├── frontend-boot.md
│   │   └── deploy-boot.md
│   ├── sessions/                     # Saved Windsurf session notes (text only)
│   ├── mcp/                          # Model Context Protocol configs
│   │   ├── postgres/                 # Postgres MCP client/server setup
│   │   │   ├── README.md
│   │   │   └── install.sh
│   │   └── memory/                   # Memory graph (nodes/relations) recipes
│   │       └── README.md
│   ├── tools/                        # Helper CLI prompts/macros for Windsurf
│   │   └── README.md
│   └── bootstrap.md                  # How Windsurf should bootstrap this repo
│
├── src/                              # Application source code
│   ├── backend/                      # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py               # Uvicorn entry
│   │   │   ├── api/                  # Routers
│   │   │   ├── models/               # Pydantic/SQLModel (when used)
│   │   │   ├── services/             # Business logic
│   │   │   ├── core/                 # Settings, logging, security
│   │   │   └── db/                   # DB init & SQL snippets (no migration lock-in)
│   │   │       ├── schema.sql
│   │   │       ├── seeds/
│   │   │       └── snippets/         # Small, copy-pasteable SQL chunks
│   │   └── tests/                    # Backend tests
│   │
│   └── frontend/                     # Static frontend (separate CSS/JS files)
│       ├── pages/                    # HTML pages
│       ├── css/                      # One CSS file per page
│       ├── js/                       # Vanilla JS modules only
│       │   ├── components/
│       │   ├── utils/
│       │   └── charts.js             # Custom minimal charts implementation
│       └── assets/                   # Page-local assets (if needed)
│
├── assets/                           # Global images, icons, fonts
│   ├── images/
│   ├── icons/
│   └── fonts/
│
├── config/                           # Runtime & operations configs
│   ├── nginx/                        # Host reverse proxy (outside LXC)
│   │   └── site.conf
│   ├── systemd/                      # System-wide units on host
│   │   └── project.service
│   ├── env/                          # Environment samples (no secrets)
│   │   └── .env.example
│   └── logging/                      # Log configuration templates
│       └── uvicorn.ini
│
├── scripts/                          # DevOps & utility scripts
│   ├── init_game.sh                  # Production deployment (host + LXC wiring)
│   ├── init_game_dev.sh              # Dev setup for Windsurf
│   ├── deploy/
│   │   ├── build.sh
│   │   ├── release.sh
│   │   └── lxc/
│   │       └── notes.md              # LXC container notes
│   └── db/
│       ├── psql_snippets.sql
│       └── maintenance.sql
│
├── tests/                            # End-to-end / integration tests
│
├── data/                             # Temporary data, fixtures
│
├── .env                              # Local development env (git-ignored)
├── requirements.txt                  # Python dependencies
├── package.json                      # JS dependencies (if any)
├── README.md                         # Project overview
└── CONTRIBUTING.md                   # Contribution guidelines for Windsurf
```

---

## Windsurf Notes

### Prompts

All reusable prompts live in `windsurf/prompts/`. Reference them from task files to ensure repeatable runs.

### Frontend

Do not use inline CSS or JS in HTML pages. Keep styles in `src/frontend/css` and scripts in `src/frontend/js`.

### Database

Prefer small SQL snippets in `src/backend/app/db/snippets/` instead of large migration frameworks.

### Secrets

Never commit real `.env` files. Use `config/env/.env.example` as a template.

### Deployment

Nginx and systemd are managed on the host (`config/nginx`, `config/systemd`), while FastAPI runs inside the LXC container via Uvicorn.

