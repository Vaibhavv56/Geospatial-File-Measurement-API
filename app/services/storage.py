import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from app.core.config import settings
from app.core.exceptions import RecordNotFoundError
from app.models.schemas import (
    FeatureDetail,
    FeatureMeasurement,
    FileMeasurementsResponse,
    FileMetadataResponse,
    FileStatus,
    MeasurementSummary,
)

logger = logging.getLogger(__name__)


from contextlib import contextmanager


class StorageService:
    """
    SQLite-backed persistent storage for geospatial files, features, and measurements.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    feature_count INTEGER NOT NULL,
                    crs TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    summary_json TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    feature_id TEXT NOT NULL,
                    geometry_type TEXT NOT NULL,
                    crs TEXT NOT NULL,
                    geometry_json TEXT,
                    properties_json TEXT NOT NULL,
                    measurement_json TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_features_file_id ON features (file_id);")

    def save_file_record(
        self,
        file_id: str,
        filename: str,
        file_type: str,
        file_size_bytes: int,
        feature_count: int,
        crs: str,
        status: FileStatus,
        summary: MeasurementSummary,
        features: list[FeatureDetail],
    ) -> None:
        created_at_iso = datetime.now(timezone.utc).isoformat()
        summary_json = summary.model_dump_json()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO files 
                (id, filename, file_type, file_size_bytes, feature_count, crs, status, created_at, summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    file_id,
                    filename,
                    file_type,
                    file_size_bytes,
                    feature_count,
                    crs,
                    status.value,
                    created_at_iso,
                    summary_json,
                ),
            )

            # Insert features
            feature_rows = []
            for feat in features:
                geom_json = json.dumps(feat.geometry) if feat.geometry else None
                props_json = json.dumps(feat.properties)
                meas_json = feat.measurement.model_dump_json()
                feature_rows.append(
                    (
                        file_id,
                        str(feat.feature_id),
                        feat.geometry_type,
                        feat.crs,
                        geom_json,
                        props_json,
                        meas_json,
                    )
                )

            conn.executemany(
                """
                INSERT INTO features 
                (file_id, feature_id, geometry_type, crs, geometry_json, properties_json, measurement_json)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                feature_rows,
            )

    def get_file(self, file_id: str) -> FileMetadataResponse:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM files WHERE id = ?;", (file_id,))
            row = cur.fetchone()
            if not row:
                raise RecordNotFoundError(f"File with id '{file_id}' not found.")

            summary_data = json.loads(row["summary_json"]) if row["summary_json"] else {}
            summary = MeasurementSummary(**summary_data)

            return FileMetadataResponse(
                id=row["id"],
                filename=row["filename"],
                feature_count=row["feature_count"],
                crs=row["crs"],
                status=FileStatus(row["status"]),
                file_type=row["file_type"],
                file_size_bytes=row["file_size_bytes"],
                created_at=datetime.fromisoformat(row["created_at"]),
                summary=summary,
            )

    def list_files(self, limit: int = 50, offset: int = 0) -> tuple[int, list[FileMetadataResponse]]:
        with self._get_connection() as conn:
            count_cur = conn.execute("SELECT COUNT(*) AS total FROM files;")
            total = count_cur.fetchone()["total"]

            cur = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC LIMIT ? OFFSET ?;",
                (limit, offset),
            )
            rows = cur.fetchall()

            files = []
            for row in rows:
                summary_data = json.loads(row["summary_json"]) if row["summary_json"] else {}
                files.append(
                    FileMetadataResponse(
                        id=row["id"],
                        filename=row["filename"],
                        feature_count=row["feature_count"],
                        crs=row["crs"],
                        status=FileStatus(row["status"]),
                        file_type=row["file_type"],
                        file_size_bytes=row["file_size_bytes"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        summary=MeasurementSummary(**summary_data),
                    )
                )

            return total, files

    def get_file_measurements(self, file_id: str) -> FileMeasurementsResponse:
        file_meta = self.get_file(file_id)

        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM features WHERE file_id = ? ORDER BY id ASC;",
                (file_id,),
            )
            rows = cur.fetchall()

            features: list[FeatureDetail] = []
            for r in rows:
                geom = json.loads(r["geometry_json"]) if r["geometry_json"] else None
                props = json.loads(r["properties_json"])
                meas = FeatureMeasurement(**json.loads(r["measurement_json"]))

                features.append(
                    FeatureDetail(
                        feature_id=r["feature_id"],
                        geometry_type=r["geometry_type"],
                        properties=props,
                        crs=r["crs"],
                        geometry=geom,
                        measurement=meas,
                    )
                )

            return FileMeasurementsResponse(
                id=file_meta.id,
                filename=file_meta.filename,
                feature_count=file_meta.feature_count,
                source_crs=file_meta.crs,
                status=file_meta.status,
                summary=file_meta.summary or MeasurementSummary(),
                features=features,
            )

    def delete_file(self, file_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM files WHERE id = ?;", (file_id,))
            return cur.rowcount > 0


# Global storage instance
storage_service = StorageService()
