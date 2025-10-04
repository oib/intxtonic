from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
from urllib.parse import quote_plus
import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings(BaseSettings):
    app_name: str
    secret_key: str
    log_level: str
    token_expiry_hours: int
    database_url: str
    ollama_base_url: str = ""
    ollama_api_key: str = ""
    ollama_model: str = ""
    default_max_posts_per_day: int
    default_max_replies_per_day: int
    app_env: str
    cors_allow_origins: List[str] = ["*"]
    email_from: str = ""
    email_from_name: str = ""
    frontend_base_url: str = ""
    smtp_server: str = ""
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    redis_url: str


@lru_cache()
def get_settings() -> Settings:
    load_dotenv()
    email_from = os.getenv('EMAIL_FROM')
    if not email_from:
        raise RuntimeError('EMAIL_FROM must be set in environment (see .env)')

    email_from_name = os.getenv('EMAIL_FROM_NAME')
    if not email_from_name:
        raise RuntimeError('EMAIL_FROM_NAME must be set in environment (see .env)')
    frontend_base_url = os.getenv('FRONTEND_BASE_URL')
    if not frontend_base_url:
        raise RuntimeError('FRONTEND_BASE_URL must be set in environment (see .env)')

    smtp_server = os.getenv('SMTP_SERVER')
    if not smtp_server:
        raise RuntimeError('SMTP_SERVER must be set in environment (see .env)')
    smtp_port = int(os.getenv('SMTP_PORT', '25'))
    smtp_use_tls = os.getenv('SMTP_USE_TLS', 'false').lower() in ('1','true','yes')
    smtp_use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        raise RuntimeError('REDIS_URL must be set in environment (see .env)')

    # Secrets and service endpoints
    secret_key = os.getenv('APP_SECRET', '')

    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'postgres')
        db_user = os.getenv('DB_USER', '')
        db_password = os.getenv('DB_PASSWORD', '')
        password_fragment = f":{quote_plus(db_password)}" if db_password else ''
        auth_fragment = f"{db_user}{password_fragment}@" if db_user else ''
        database_url = f"postgresql://{auth_fragment}{db_host}:{db_port}/{db_name}"

    ollama_base_url = os.getenv('OPENWEBUI_BASE_URL', os.getenv('OLLAMA_BASE', ''))
    ollama_api_key = os.getenv('OPENWEBUI_API_KEY', os.getenv('OLLAMA_API_KEY', ''))
    ollama_model = os.getenv('OPENWEBUI_MODEL_TRANSLATE',
                             os.getenv('OPENWEBUI_MODEL_SUMMARY', os.getenv('OLLAMA_MODEL', '')))

    cors_origins = os.getenv('CORS_ALLOW_ORIGINS')
    if cors_origins:
        cors_allow_origins = [o.strip() for o in cors_origins.split(',') if o.strip()]
    else:
        cors_allow_origins = ["*"]

    app_env = os.getenv('APP_ENV')
    if not app_env:
        raise RuntimeError('APP_ENV must be set in environment (see .env)')

    default_max_posts_per_day_val = os.getenv('DEFAULT_MAX_POSTS_PER_DAY')
    if not default_max_posts_per_day_val:
        raise RuntimeError('DEFAULT_MAX_POSTS_PER_DAY must be set in environment (see .env)')
    try:
        default_max_posts_per_day = int(default_max_posts_per_day_val)
    except ValueError as exc:
        raise RuntimeError('DEFAULT_MAX_POSTS_PER_DAY must be an integer') from exc

    default_max_replies_per_day_val = os.getenv('DEFAULT_MAX_REPLIES_PER_DAY')
    if not default_max_replies_per_day_val:
        raise RuntimeError('DEFAULT_MAX_REPLIES_PER_DAY must be set in environment (see .env)')
    try:
        default_max_replies_per_day = int(default_max_replies_per_day_val)
    except ValueError as exc:
        raise RuntimeError('DEFAULT_MAX_REPLIES_PER_DAY must be an integer') from exc

    return Settings(
        app_name="intxtonic",
        secret_key=secret_key,
        log_level="INFO",
        token_expiry_hours=168,
        database_url=database_url,
        ollama_base_url=ollama_base_url,
        ollama_api_key=ollama_api_key,
        ollama_model=ollama_model,
        app_env=app_env,
        cors_allow_origins=cors_allow_origins,
        default_max_posts_per_day=default_max_posts_per_day,
        default_max_replies_per_day=default_max_replies_per_day,
        email_from=email_from,
        email_from_name=email_from_name,
        frontend_base_url=frontend_base_url,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_use_tls=smtp_use_tls,
        smtp_use_ssl=smtp_use_ssl,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        redis_url=redis_url
    )
