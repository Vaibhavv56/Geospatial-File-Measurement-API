import logging
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import (
    CorruptFileError,
    EmptyDatasetError,
    GeospatialServiceError,
    UnsupportedFileFormatError,
)
from app.models.schemas import (
    FeatureDetail,
    FileMetadataResponse,
    FileStatus,
    MeasurementSummary,
)
from app.services.measurement_service import MeasurementService
from app.services.parsers.base import ParsedGeospatialData
from app.services.parsers.kml_parser import KMLParser
from app.services.parsers.shapefile_parser import ShapefileParser
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class FileProcessorService:
    """
    Coordinates file validation, storage, parsing, CRS transformation,
    measurement computation, and persistence.
    """

    def __init__(self):
        self.shapefile_parser = ShapefileParser()
        self.kml_parser = KMLParser()

    async def process_uploaded_file(self, upload_file: UploadFile) -> FileMetadataResponse:
        filename = upload_file.filename or "uploaded_file"
        file_ext = Path(filename).suffix.lower()

        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatError(
                f"File format '{file_ext}' is not supported. Only .kml and .zip (Shapefile) are accepted."
            )

        # Generate unique file identifier
        file_id = uuid.uuid4().hex[:10]
        saved_path = settings.UPLOAD_DIR / f"{file_id}_{Path(filename).name}"

        # Write uploaded file in chunks with size limit enforcement
        total_size = 0
        try:
            with open(saved_path, "wb") as buffer:
                while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                        raise GeospatialServiceError(
                            f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB.",
                            status_code=413,
                        )
                    buffer.write(chunk)
        except Exception:
            if saved_path.exists():
                saved_path.unlink()
            raise

        try:
            return self.process_file_from_path(
                file_path=saved_path,
                filename=filename,
                file_id=file_id,
                file_size_bytes=total_size,
            )
        except Exception:
            # If processing completely fails, clean up upload
            if saved_path.exists():
                saved_path.unlink()
            raise

    def process_file_from_path(
        self,
        file_path: Path,
        filename: str,
        file_id: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
    ) -> FileMetadataResponse:
        if file_id is None:
            file_id = uuid.uuid4().hex[:10]
        if file_size_bytes is None:
            file_size_bytes = file_path.stat().st_size

        file_ext = file_path.suffix.lower()

        # 1. Parse geospatial data
        parsed_data: ParsedGeospatialData
        if file_ext == ".zip":
            parsed_data = self.shapefile_parser.parse(file_path)
        elif file_ext == ".kml":
            parsed_data = self.kml_parser.parse(file_path)
        else:
            raise UnsupportedFileFormatError(f"Unsupported extension: {file_ext}")

        if not parsed_data.features:
            raise EmptyDatasetError("Geospatial dataset does not contain any features.")

        # 2. Process features and compute measurements
        feature_details: list[FeatureDetail] = []
        summary = MeasurementSummary(total_features=len(parsed_data.features))

        for feat in parsed_data.features:
            measurement = MeasurementService.calculate_measurement(
                geometry=feat.geometry,
                source_crs=feat.crs,
            )

            # Accumulate summary statistics
            g_type = feat.geometry_type.lower()
            if "polygon" in g_type:
                summary.polygon_count += 1
                if measurement.area_sq_meters:
                    summary.total_area_sq_meters += measurement.area_sq_meters
                    summary.total_area_hectares += (measurement.area_hectares or 0.0)
            elif "linestring" in g_type or "ring" in g_type:
                summary.linestring_count += 1
                if measurement.length_meters:
                    summary.total_length_meters += measurement.length_meters
                    summary.total_length_km += (measurement.length_km or 0.0)
            elif "point" in g_type:
                summary.point_count += 1
            else:
                summary.unsupported_count += 1

            feature_details.append(
                FeatureDetail(
                    feature_id=feat.feature_id,
                    geometry_type=feat.geometry_type,
                    properties=feat.properties,
                    crs=feat.crs,
                    geometry=feat.geometry_geojson,
                    measurement=measurement,
                )
            )

        summary.total_area_sq_meters = round(summary.total_area_sq_meters, 4)
        summary.total_area_hectares = round(summary.total_area_hectares, 4)
        summary.total_length_meters = round(summary.total_length_meters, 4)
        summary.total_length_km = round(summary.total_length_km, 6)

        # 3. Persist to storage
        storage_service.save_file_record(
            file_id=file_id,
            filename=filename,
            file_type=parsed_data.file_type,
            file_size_bytes=file_size_bytes,
            feature_count=len(feature_details),
            crs=parsed_data.crs,
            status=FileStatus.COMPLETED,
            summary=summary,
            features=feature_details,
        )

        return FileMetadataResponse(
            id=file_id,
            filename=filename,
            feature_count=len(feature_details),
            crs=parsed_data.crs,
            status=FileStatus.COMPLETED,
            file_type=parsed_data.file_type,
            file_size_bytes=file_size_bytes,
            summary=summary,
        )


file_processor = FileProcessorService()
