from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class FileStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileType(str, Enum):
    KML = "KML"
    SHAPEFILE = "SHAPEFILE"
    UNKNOWN = "UNKNOWN"


class MeasurementSummary(BaseModel):
    total_features: int = 0
    polygon_count: int = 0
    linestring_count: int = 0
    point_count: int = 0
    unsupported_count: int = 0
    total_area_sq_meters: float = 0.0
    total_area_hectares: float = 0.0
    total_length_meters: float = 0.0
    total_length_km: float = 0.0


class FileMetadataResponse(BaseModel):
    id: str = Field(..., description="Unique identifier for uploaded file")
    filename: str = Field(..., description="Original uploaded filename")
    feature_count: int = Field(0, description="Total number of extracted features")
    crs: str = Field("EPSG:4326", description="Source Coordinate Reference System")
    status: FileStatus = Field(FileStatus.COMPLETED, description="Processing status")
    file_type: Optional[str] = Field(None, description="Type of geospatial file: KML or SHAPEFILE")
    file_size_bytes: Optional[int] = Field(None, description="Size of file in bytes")
    created_at: Optional[datetime] = Field(None, description="Timestamp of upload")
    summary: Optional[MeasurementSummary] = Field(None, description="Measurement summary across all features")


class FeatureMeasurement(BaseModel):
    type: str = Field(..., description="Measurement category: area, length, none, or unsupported")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    area_sq_meters: Optional[float] = Field(None, description="Area in square meters")
    area_hectares: Optional[float] = Field(None, description="Area in hectares")
    area_sq_km: Optional[float] = Field(None, description="Area in square kilometers")
    area_acres: Optional[float] = Field(None, description="Area in acres")
    perimeter_meters: Optional[float] = Field(None, description="Perimeter boundary length in meters")
    length_meters: Optional[float] = Field(None, description="Linear length in meters")
    length_km: Optional[float] = Field(None, description="Linear length in kilometers")
    projected_crs: Optional[str] = Field(None, description="Projected CRS used for metric calculation")
    projection_description: Optional[str] = Field(None, description="Explanation of chosen projection")
    message: Optional[str] = Field(None, description="Informational message or explanation")


class FeatureDetail(BaseModel):
    feature_id: Union[int, str] = Field(..., description="Feature identifier or index")
    geometry_type: str = Field(..., description="Geometry type (Polygon, LineString, Point, etc.)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Feature attributes and metadata")
    crs: str = Field("EPSG:4326", description="Source CRS")
    geometry: Optional[dict[str, Any]] = Field(None, description="GeoJSON geometry object")
    measurement: FeatureMeasurement = Field(..., description="Calculated measurement or reason if omitted")


class FileMeasurementsResponse(BaseModel):
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    feature_count: int = Field(..., description="Number of features")
    source_crs: str = Field(..., description="Source coordinate reference system")
    status: FileStatus = Field(..., description="File status")
    summary: MeasurementSummary = Field(..., description="Aggregate measurements summary")
    features: list[FeatureDetail] = Field(..., description="List of measured features")


class FileListResponse(BaseModel):
    total: int
    files: list[FileMetadataResponse]


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: datetime
    drivers_available: list[str]
