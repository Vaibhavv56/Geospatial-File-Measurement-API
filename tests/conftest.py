import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.storage import StorageService, storage_service

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture(scope="session", autouse=True)
def ensure_samples():
    """Ensure sample datasets are generated before running tests."""
    from samples.generate_samples import (
        generate_kml_survey_parcels,
        generate_kml_road_network,
        generate_shapefile_zip,
    )
    if not (SAMPLES_DIR / "survey_parcels.kml").exists():
        generate_kml_survey_parcels()
    if not (SAMPLES_DIR / "road_network.kml").exists():
        generate_kml_road_network()
    if not (SAMPLES_DIR / "cadastral_parcels.zip").exists():
        generate_shapefile_zip()


@pytest.fixture
def temp_db(monkeypatch):
    """Provides a fresh isolated SQLite database for each test."""
    temp_dir = tempfile.mkdtemp(prefix="test_db_")
    db_file = Path(temp_dir) / "test_geomeasure.db"
    
    test_storage = StorageService(db_path=db_file)
    monkeypatch.setattr("app.services.storage.storage_service", test_storage)
    monkeypatch.setattr("app.services.file_processor.storage_service", test_storage)
    monkeypatch.setattr("app.api.endpoints.files.storage_service", test_storage)

    yield test_storage

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(temp_db):
    """FastAPI test client with isolated storage."""
    return TestClient(app)
