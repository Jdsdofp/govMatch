from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite+aiosqlite:///./govmatch.db"
    PNCP_BASE_URL: str = "https://pncp.gov.br/api/pncp/v1"
    COMPRAS_GOV_URL: str = "https://compras.gov.br"
    TESSERACT_CMD: str = "tesseract"
    PDF_DOWNLOAD_DIR: Path = Path("./tmp/pdfs")
    SYNC_INTERVAL_SECONDS: int = 3600
    LOG_LEVEL: str = "INFO"

    def model_post_init(self, _: object) -> None:
        self.PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
