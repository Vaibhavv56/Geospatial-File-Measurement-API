import logging
from typing import Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from app.core.exceptions import GeospatialServiceError, RecordNotFoundError
from app.models.schemas import (
    FileListResponse,
    FileMeasurementsResponse,
    FileMetadataResponse,
)
from app.services.file_processor import file_processor
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process geospatial file",
    description="Upload a .kml file or a .zip archive containing an ESRI Shapefile (.shp, .dbf, .prj). "
                "The service extracts all features, identifies CRS, and computes precision measurements.",
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip Shapefile)")
) -> FileMetadataResponse:
    try:
        return await file_processor.process_uploaded_file(file)
    except GeospatialServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error("Unhandled error processing file %s: %s", file.filename, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred while processing the file: {str(e)}",
        )


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List uploaded files",
    description="Returns a paginated list of all uploaded and processed geospatial files.",
)
def list_files(
    limit: int = Query(50, ge=1, le=100, description="Max files to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> FileListResponse:
    total, files = storage_service.list_files(limit=limit, offset=offset)
    return FileListResponse(total=total, files=files)


@router.get(
    "/{file_id}/",
    response_model=FileMetadataResponse,
    summary="Get file information",
    description="Returns metadata, feature count, CRS, and aggregate measurement summary for an uploaded file.",
)
def get_file_info(file_id: str) -> FileMetadataResponse:
    try:
        return storage_service.get_file(file_id)
    except RecordNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get feature measurements",
    description="Returns measurement details for all features in the file: "
                "Polygons (Area in m², ha, km², acres), LineStrings (Length in m, km), Points (no measurement).",
)
def get_file_measurements(file_id: str) -> FileMeasurementsResponse:
    try:
        return storage_service.get_file_measurements(file_id)
    except RecordNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/{file_id}/geojson/",
    summary="Export features as GeoJSON",
    description="Returns an RFC 7946 compliant GeoJSON FeatureCollection containing all features and their calculated measurements.",
)
def get_file_geojson(file_id: str):
    try:
        measurements_resp = storage_service.get_file_measurements(file_id)
        geojson_features = []
        for feat in measurements_resp.features:
            geojson_features.append({
                "type": "Feature",
                "id": feat.feature_id,
                "geometry": feat.geometry,
                "properties": {
                    **feat.properties,
                    "_measurement": feat.measurement.model_dump(),
                    "_crs": feat.crs,
                    "_geometry_type": feat.geometry_type,
                }
            })
        return {
            "type": "FeatureCollection",
            "name": measurements_resp.filename,
            "crs": {
                "type": "name",
                "properties": {"name": measurements_resp.source_crs}
            },
            "features": geojson_features
        }
    except RecordNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete uploaded file",
    description="Deletes a file and all associated feature records and measurements.",
)
def delete_file(file_id: str):
    deleted = storage_service.delete_file(file_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File with id '{file_id}' not found.")
    return None
