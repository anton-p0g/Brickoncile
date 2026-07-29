from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    rebrickable_api_key: str = ""
    brickognize_base_url: str = "https://api.brickognize.com"
    max_upload_bytes: int = 12 * 1024 * 1024
    """Cap on an uploaded photo. Phone cameras produce a few MB, so this leaves room while keeping a
    mistaken upload (a video, a raw file) from being read into memory."""
    database_path: Path = BACKEND_ROOT / "data" / "brickoncile.db"
    images_dir: Path = BACKEND_ROOT / "data" / "images"
    frontend_dist_dir: Path = BACKEND_ROOT.parent / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
