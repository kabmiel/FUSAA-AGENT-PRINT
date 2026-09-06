from pathlib import Path
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
ENV_FILE = None if "pytest" in sys.modules else PROJECT_DIR/".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
    database_url: str = "sqlite:///./fusaa.db"
    jwt_secret: str = "development-only-secret-must-be-replaced-32b"
    access_token_minutes: int = 60
    storage_dir: Path = Path("./storage")

    def model_post_init(self, __context):
        if not self.storage_dir.is_absolute():
            self.storage_dir = (BACKEND_DIR / self.storage_dir).resolve()
        if self.database_url.startswith("sqlite:///"):
            raw_path = self.database_url.removeprefix("sqlite:///")
            if raw_path != ":memory:":
                p = Path(raw_path)
                if not p.is_absolute():
                    self.database_url = f"sqlite:///{(BACKEND_DIR / p).resolve().as_posix()}"
    cors_origins: str = "http://localhost:8000"
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claim_email: str = "mailto:admin@example.com"
    environment: str = "development"
    log_level: str = "INFO"
    trusted_hosts: str = "localhost,127.0.0.1"
    max_upload_bytes: int = 100 * 1024 * 1024
    # AI is local by default: no cloud provider and no API key are required.
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:0.5b"
    single_workshop_id: str = ""
    single_workshop_name: str = "FUSAA INFORMATIQUE"
    # Optional. Required only to activate signed Meta WhatsApp Business webhooks.
    meta_whatsapp_app_secret: str = ""

    def validate_runtime(self):
        if self.environment.lower()=="production":
            if self.jwt_secret.startswith("development") or len(self.jwt_secret)<32:raise RuntimeError("Production requires a random JWT_SECRET of at least 32 characters")
            if self.database_url.startswith("sqlite"):raise RuntimeError("Production requires PostgreSQL, not SQLite")
            if "*" in self.cors_origins:raise RuntimeError("Production CORS origins must be explicit")


settings = Settings()
