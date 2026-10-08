from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import shapely.geometry.base


@dataclass
class ParsedFeature:
    feature_id: str | int
    geometry_type: str
    geometry: Optional[shapely.geometry.base.BaseGeometry]
    geometry_geojson: Optional[dict[str, Any]]
    properties: dict[str, Any] = field(default_factory=dict)
    crs: str = "EPSG:4326"


@dataclass
class ParsedGeospatialData:
    crs: str
    features: list[ParsedFeature]
    file_type: str


class BaseGeospatialParser(ABC):
    """Abstract base parser for geospatial files."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedGeospatialData:
        """Parses a geospatial file and returns extracted features and CRS."""
        pass
