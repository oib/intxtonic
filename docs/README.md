# inTxTonic

An inTxTonic multilingual, tag‑centric blogging platform. Mobile‑first frontend, FastAPI backend, PostgreSQL database.

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 6+ (for caching/tag list acceleration)

### 1) Clone and prepare env
```bash
cp config/env/.env.example .env
# Edit .env to set DB credentials and secrets
```

### 2) Create database (example)
If you already created `langsum` and user `langsum`, skip.
```bash
# Example (adjust as needed)
sudo -u postgres psql -c "CREATE DATABASE langsum;"
sudo -u postgres psql -c "CREATE USER langsum WITH PASSWORD 'yourpass';"
sudo -u postgres psql -c "ALTER DATABASE langsum OWNER TO langsum;"
```

### 3) Apply schema and seeds
```bash
# Replace PGPASSWORD with your value from .env
PGPASSWORD=... psql -h localhost -p 5432 -U langsum -d langsum -v ON_ERROR_STOP=1 -f src/backend/app/db/schema.sql
PGPASSWORD=... psql -h localhost -p 5432 -U langsum -d langsum -v ON_ERROR_STOP=1 -f src/backend/app/db/seeds/initial.sql
```

### 4) Run the app (dev)
```bash
# ensure Redis is running locally
redis-server --daemonize yes

bash scripts/dev_run.sh
```
- API docs: http://127.0.0.1:8002/docs
- Frontend pages:
  - Home: http://127.0.0.1:8002/src/frontend/pages/index.html
  - Login: http://127.0.0.1:8002/src/frontend/pages/login.html
  - Dashboard: http://127.0.0.1:8002/src/frontend/pages/dashboard.html

## Backend
- FastAPI app at `src/backend/app/main.py`
- Config loader `src/backend/app/core/config.py` reads `.env`
- Async PostgreSQL pool `src/backend/app/core/db.py` (psycopg-pool)
- Auth `src/backend/app/api/auth.py`: register, login (JWT), me
- Tags `src/backend/app/api/tags.py`: list/search, create, ban/unban
- Posts `src/backend/app/api/posts.py`: list (pagination/sorting), create, get, replies, vote
- Global error handlers `src/backend/app/core/errors.py` return standardized JSON

### Rate limits
- Tables `app.rate_limits`, `app.user_limits`
- Defaults from `.env`:
  - `DEFAULT_MAX_POSTS_PER_DAY` (default 10)
  - `DEFAULT_MAX_REPLIES_PER_DAY` (default 50)

## Frontend
- CSS in `src/frontend/css/` following `docs/bootstrap/layout.md`
- Pages in `src/frontend/pages/`: `index.html`, `login.html`, `dashboard.html`, `post.html`
- JS utilities:
  - Toasts: `src/frontend/js/toast.js`
  - Notifications: `src/frontend/js/notify.js`
  - Auth helper: `src/frontend/js/auth.js`

## Profiles
- User profiles are accessible via `user.html?handle=<username>` and display user information, posts, and replies.
- Features include:
  - Avatar placeholder with the initial letter of the user's handle or display name.
  - Tabbed interface to switch between a user's posts and replies.
  - Deep linking to specific user content through URL parameters.
- Relevant endpoints:
  - `GET /users/{handle}` — Retrieve user profile information.
  - `GET /users/{handle}/posts` — List user's posts with pagination and sorting options.
  - `GET /users/{handle}/replies` — List user's replies with pagination and sorting options.

## Tag filtering and management

- Dashboard filtering
  - Click tag chips to toggle active filters. The feed reloads with `GET /posts?tag=slug` (multi-tag supported).
  - Deep links supported via URL: `dashboard.html?tags=tag1,tag2`.
  - Selected filters are shown as chips with a “Clear filters” button.

- Post detail
  - Read-only tag chips link back to dashboard with preselected `?tags=`.
  - Admin-only panel allows attaching a tag by slug and detaching existing tags.

- Relevant endpoints
  - `GET /posts?tag=...` — returns `items` with `tags` inline for each post.
  - `GET /posts/{post_id}/tags` — list tags for a post.
  - `POST /posts/{post_id}/tags` — attach tag by slug (admin).
  - `DELETE /posts/{post_id}/tags/{tag_id}` — detach tag (admin).

## Moderation
- Moderation features are accessible to users with admin or moderator roles via `admin.html`.
- Features include:
  - UI stubs for moderation queues to review reported content and new posts/replies.
  - Tag management list with options to create new tags and toggle ban/unban status.
- Relevant endpoints:
  - `GET /moderation/reports` — Retrieve a list of reported content for review (admin/moderator only).
  - `GET /moderation/new-content` — Retrieve a list of new content for review (admin/moderator only).
  - `POST /tags` — Create a new tag (admin only).
  - `POST /tags/{id}/ban` — Ban a tag (admin only).
  - `POST /tags/{id}/unban` — Unban a tag (admin only).

## Deployment (user-level systemd)
- Template at `config/systemd/langsum-gunicorn.user.service.example`
- Steps:
```bash
mkdir -p ~/.config/systemd/user
cp config/systemd/langsum-gunicorn.user.service.example ~/.config/systemd/user/langsum-gunicorn.service
systemctl --user daemon-reload
systemctl --user enable langsum-gunicorn.service
systemctl --user start langsum-gunicorn.service
systemctl --user status langsum-gunicorn.service --no-pager
```
- Provision a Redis service (systemd, Docker, or managed) reachable at the `REDIS_URL` configured in `.env`.
- Example systemd setup using redis-server package:
```bash
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```
- Health: http://localhost:8002/health

### Nginx Reverse Proxy Example
For production deployment, you may want to set up an Nginx reverse proxy to handle incoming requests, provide SSL termination, and serve static files efficiently. Below is an example configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS (optional, if SSL is configured)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    # SSL configuration (adjust paths to your certificates)
    ssl_certificate /path/to/your/fullchain.pem;
    ssl_certificate_key /path/to/your/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve static files directly (adjust path as needed)
    location /src/frontend/ {
        alias /path/to/langsum/src/frontend/;
        expires 1M;
        access_log off;
        add_header Cache-Control "public";
    }

    # Additional security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; object-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'none';";
}
```

- **Notes on Nginx Configuration**:
  - Replace `yourdomain.com` with your actual domain.
  - Update paths to SSL certificates if using HTTPS.
  - Adjust the `alias` path in the static files location block to match your server's file structure.
  - The security headers are a starting point; customize based on your specific requirements.
  - Ensure Nginx has appropriate permissions to access static files if serving them directly.

## Notes
- Use admin endpoint to set `user1` password: `POST /auth/admin/set-password` (requires admin token)
- Consider tightening CORS for production.
- OpenAPI at `/docs` reflects Pydantic models and response schemas.
