from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
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
    default_max_posts_per_day: int = 10
    default_max_replies_per_day: int = 50
    app_env: str = ""
    cors_allow_origins: List[str] = ["*"]
    email_from: str = ""
    email_from_name: str = "LangSum"
    frontend_base_url: str = "http://127.0.0.1:8002"
    smtp_server: str = ""
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    redis_url: str = "redis://localhost:6379/0"


@lru_cache()
def get_settings() -> Settings:
    load_dotenv()
    email_from = os.getenv('EMAIL_FROM', 'test@keisanki.net')
    email_from_name = os.getenv('EMAIL_FROM_NAME', 'LangSum')
    frontend_base_url = os.getenv('FRONTEND_BASE_URL', 'http://127.0.0.1:8002')
    smtp_server = os.getenv('SMTP_SERVER', 'localhost')
    smtp_port = int(os.getenv('SMTP_PORT', '25'))
    smtp_use_tls = os.getenv('SMTP_USE_TLS', 'false').lower() in ('1','true','yes')
    smtp_use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('1','true','yes')
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    return Settings(
        app_name="LangSum",
        secret_key="your-secret-key-here",
        log_level="INFO",
        token_expiry_hours=168,
        database_url="postgresql://langsum:bc9c9fc44ba50f34@localhost:5432/langsum",
        ollama_base_url="https://at1.dynproxy.net",
        ollama_api_key="sk-d0e3a491b19c435a975b234969298cd0",
        ollama_model="gemma3:1b",
        app_env="development",
        cors_allow_origins=["*"],
        default_max_posts_per_day=10,
        default_max_replies_per_day=50,
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
