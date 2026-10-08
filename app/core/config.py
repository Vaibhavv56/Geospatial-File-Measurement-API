import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TEMP_DIR = DATA_DIR / "temp"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "Production-ready FastAPI service for geospatial file ingestion (Shapefile, KML), "
        "intelligent CRS transformation, and precision feature measurement calculation."
    )
    API_PREFIX: str = "/api"
    
    # Storage settings
    DATA_DIR: Path = DATA_DIR
    UPLOAD_DIR: Path = UPLOAD_DIR
    TEMP_DIR: Path = TEMP_DIR
    DB_PATH: Path = DATA_DIR / "geomeasure.db"
    
    # Upload constraints
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: set[str] = {".zip", ".kml"}
    
    # Measurement configuration
    DEFAULT_FALLBACK_CRS: str = "EPSG:4326"


settings = Settings()
