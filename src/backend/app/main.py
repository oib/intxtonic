from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.staticfiles import StaticFiles
from pathlib import Path
from starlette.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.db import init_pool, close_pool
from .core.cache import init_redis, close_redis
from .core.errors import register_exception_handlers
from .core.deps import get_current_account_id
from fastapi import HTTPException
from .api.auth import router as auth_router
from .api.tags import router as tags_router
from .api.bookmarks import router as bookmarks_router
from .api.i18n_admin import router as i18n_admin_router
from .api.posts import router as posts_router
from .api.users import router as users_router
from .api.ai import ai_route as ai_router
from .api.notify import router as notify_router
from .api.uploads import router as uploads_router
from .api.moderation import router as moderation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    app_env = getattr(settings, 'app_env', 'development')
    if app_env != "test":
        await init_pool(app, settings.database_url)
        await init_redis(app)
    try:
        yield
    finally:
        # Shutdown
        if app_env != "test":
            await close_redis(app)
            await close_pool(app)


app = FastAPI(title="LangSum API", lifespan=lifespan)
register_exception_handlers(app)

# Minimal CORS for local dev; tighten later
settings_for_cors = get_settings()
allow_origins = getattr(settings_for_cors, "cors_allow_origins", ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    # Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Minimal, privacy-friendly Permissions-Policy
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=(), payment=()",
    )
    # Basic CSP for non-dev/test environments
    env = getattr(get_settings(), "app_env", "development").lower()
    if env not in ("development", "dev", "test"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self' data:; object-src 'none'; frame-ancestors 'none'",
        )
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve static frontend (css/js/pages/assets). Paths stay as absolute '/src/frontend/...'
app.mount("/src/frontend", StaticFiles(directory="src/frontend"), name="frontend")
# Serve i18n locale JSON files
app.mount("/i18n", StaticFiles(directory="i18n"), name="i18n")
def _project_root_from_here() -> Path:
    here = Path(__file__).resolve()
    for anc in here.parents:
        if anc.name == 'src':
            return anc.parent
    try:
        return here.parents[2].parent
    except Exception:
        return here.parent

_PROJECT_ROOT = _project_root_from_here()
# Serve uploaded files from absolute path to align with upload saver
app.mount("/uploads", StaticFiles(directory=str(_PROJECT_ROOT / "src" / "frontend" / "uploads")), name="uploads")

_FEATURE_PAGES = {
    "translation-engine": "src/frontend/pages/features/translation-engine.html",
    "ui-localization": "src/frontend/pages/features/ui-localization.html",
    "culture-language": "src/frontend/pages/features/culture-language.html",
    "developer-workflow": "src/frontend/pages/features/developer-workflow.html",
    "tech-briefings": "src/frontend/pages/features/tech-briefings.html",
    "governance-controls": "src/frontend/pages/features/governance-controls.html",
    "policy-society": "src/frontend/pages/features/policy-society.html",
    "localization-ops": "src/frontend/pages/features/localization-ops.html",
}


@app.get("/")
def landing_page():
    return FileResponse("src/frontend/pages/index.html")


@app.get("/features/")
def features_index_page():
    return FileResponse("src/frontend/pages/features/index.html")


@app.get("/features/{slug}.html")
def features_detail_page(slug: str):
    page_path = _FEATURE_PAGES.get(slug)
    if not page_path:
        raise HTTPException(status_code=404, detail="Feature page not found")
    return FileResponse(page_path)

# Register API routers BEFORE clean URL frontend routes to ensure specific API
# endpoints (e.g., /tags/usage) are not shadowed by catch-all page routes like
# /tags/{slug}.
app.include_router(auth_router)
app.include_router(tags_router)
app.include_router(bookmarks_router)
app.include_router(posts_router)
app.include_router(users_router)
app.include_router(ai_router)
app.include_router(i18n_admin_router)
app.include_router(moderation_router)
app.include_router(notify_router)
app.include_router(uploads_router)


@app.get("/favicon.ico")
def favicon():
    # Serve the SVG favicon as .ico path; browsers will accept image/svg+xml
    return FileResponse("src/frontend/assets/favicon.svg", media_type="image/svg+xml")


# Clean URL routes for frontend pages
@app.get("/home")
async def home_page(request: Request):
    try:
        await get_current_account_id(request)
    except HTTPException:
        return RedirectResponse(url="/", status_code=307)
    return FileResponse("src/frontend/pages/home.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("src/frontend/pages/dashboard.html")


@app.get("/login")
def login_page():
    return FileResponse("src/frontend/pages/login.html")


@app.get("/register")
def register_page():
    return FileResponse("src/frontend/pages/register.html")


@app.get("/confirm-email")
def confirm_email_page():
    return FileResponse("src/frontend/pages/confirm-email.html")


@app.get("/magic-login")
def magic_login_page():
    return FileResponse("src/frontend/pages/magic-login.html")


@app.get("/post/{post_id}")
def post_page(post_id: str):
    return FileResponse("src/frontend/pages/post.html")


@app.get("/user/settings")
def settings_page():
    return FileResponse("src/frontend/pages/settings.html")


@app.get("/user/{handle}")
def user_page(handle: str):
    return FileResponse("src/frontend/pages/user.html")


@app.get("/admin")
def admin_page():
    return FileResponse("src/frontend/pages/admin.html")


@app.get("/admin/users")
def admin_users_page():
    return FileResponse("src/frontend/pages/admin-users.html")


@app.get("/admin/tags")
def admin_tags_page():
    return FileResponse("src/frontend/pages/admin-tags.html")


@app.get("/admin/moderation")
def admin_moderation_page():
    return FileResponse("src/frontend/pages/admin-moderation.html")


@app.get("/create")
def create_post_page():
    return FileResponse("src/frontend/pages/create.html")


@app.get("/tags/top")
def tags_top_page():
    return FileResponse("src/frontend/pages/tagstop.html")


@app.get("/tags/{slug}")
def tag_page(slug: str):
    return FileResponse("src/frontend/pages/tags.html")


@app.get("/admin/i18n")
def admin_i18n_page():
    return FileResponse("src/frontend/pages/admin-i18n.html")


@app.get("/notifications")
def notifications_page():
    return FileResponse("src/frontend/pages/notification.html")
