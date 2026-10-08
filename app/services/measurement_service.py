import logging
from typing import Optional, Union
import shapely.geometry
import shapely.validation
from app.models.schemas import FeatureMeasurement
from app.services.crs_service import CRSService

logger = logging.getLogger(__name__)

SQ_METERS_TO_HECTARE = 1.0 / 10000.0
SQ_METERS_TO_SQ_KM = 1.0 / 1_000_000.0
SQ_METERS_TO_ACRES = 1.0 / 4046.8564224
METERS_TO_KM = 1.0 / 1000.0


class MeasurementService:
    """
    Precision measurement service for geospatial geometries.
    
    Transforms geographic coordinates into suitable local projected metric coordinate systems
    before calculating areas and lengths, ensuring high accuracy and metric consistency.
    """

    @classmethod
    def calculate_measurement(
        cls,
        geometry: Optional[shapely.geometry.base.BaseGeometry],
        source_crs: str = "EPSG:4326"
    ) -> FeatureMeasurement:
        """
        Calculates measurement for a given Shapely geometry with CRS projection.
        Handles unsupported, invalid, and empty geometries gracefully.
        """
        if geometry is None or geometry.is_empty:
            return FeatureMeasurement(
                type="none",
                message="Geometry is null or empty. No measurement available."
            )

        geom_type = geometry.geom_type

        # Check and attempt to repair invalid geometries (e.g. self-intersecting polygons)
        if not geometry.is_valid:
            try:
                geometry = shapely.validation.make_valid(geometry)
                geom_type = geometry.geom_type
            except Exception as e:
                logger.warning("Could not repair invalid geometry: %s", e)
                return FeatureMeasurement(
                    type="unsupported",
                    message=f"Geometry is topologically invalid and could not be repaired: {e}"
                )

        # 1. Point / MultiPoint: No measurement required per requirements
        if geom_type in ("Point", "MultiPoint"):
            return FeatureMeasurement(
                type="none",
                message="Point geometries represent discrete coordinate locations without length or area."
            )

        # 2. Polygon / MultiPolygon: Calculate Area & Perimeter
        if geom_type in ("Polygon", "MultiPolygon"):
            try:
                projected_geom, target_crs, desc = CRSService.project_geometry(geometry, source_crs)
                area_m2 = round(float(projected_geom.area), 4)
                perimeter_m = round(float(projected_geom.length), 4)

                return FeatureMeasurement(
                    type="area",
                    unit="square_meters",
                    area_sq_meters=area_m2,
                    area_hectares=round(area_m2 * SQ_METERS_TO_HECTARE, 4),
                    area_sq_km=round(area_m2 * SQ_METERS_TO_SQ_KM, 6),
                    area_acres=round(area_m2 * SQ_METERS_TO_ACRES, 4),
                    perimeter_meters=perimeter_m,
                    projected_crs=target_crs,
                    projection_description=desc,
                )
            except Exception as e:
                logger.error("Error calculating polygon area: %s", e, exc_info=True)
                return FeatureMeasurement(
                    type="error",
                    message=f"Failed to project and calculate polygon area: {str(e)}"
                )

        # 3. LineString / MultiLineString / LinearRing: Calculate Length
        if geom_type in ("LineString", "MultiLineString", "LinearRing"):
            try:
                projected_geom, target_crs, desc = CRSService.project_geometry(geometry, source_crs)
                length_m = round(float(projected_geom.length), 4)

                return FeatureMeasurement(
                    type="length",
                    unit="meters",
                    length_meters=length_m,
                    length_km=round(length_m * METERS_TO_KM, 6),
                    projected_crs=target_crs,
                    projection_description=desc,
                )
            except Exception as e:
                logger.error("Error calculating linestring length: %s", e, exc_info=True)
                return FeatureMeasurement(
                    type="error",
                    message=f"Failed to project and calculate line length: {str(e)}"
                )

        # 4. GeometryCollection or other compound/unsupported types
        if geom_type == "GeometryCollection":
            # Gracefully handle GeometryCollection: sum area and length across components
            try:
                projected_geom, target_crs, desc = CRSService.project_geometry(geometry, source_crs)
                area_m2 = 0.0
                length_m = 0.0
                for part in projected_geom.geoms:
                    if part.geom_type in ("Polygon", "MultiPolygon"):
                        area_m2 += part.area
                    elif part.geom_type in ("LineString", "MultiLineString", "LinearRing"):
                        length_m += part.length

                if area_m2 > 0:
                    return FeatureMeasurement(
                        type="area",
                        unit="square_meters",
                        area_sq_meters=round(area_m2, 4),
                        area_hectares=round(area_m2 * SQ_METERS_TO_HECTARE, 4),
                        length_meters=round(length_m, 4),
                        projected_crs=target_crs,
                        projection_description=desc,
                        message="GeometryCollection measured: composite polygon area and linear elements."
                    )
                elif length_m > 0:
                    return FeatureMeasurement(
                        type="length",
                        unit="meters",
                        length_meters=round(length_m, 4),
                        length_km=round(length_m * METERS_TO_KM, 6),
                        projected_crs=target_crs,
                        projection_description=desc,
                        message="GeometryCollection measured: linear elements length."
                    )
                else:
                    return FeatureMeasurement(
                        type="none",
                        message="GeometryCollection contains only point geometries; no length or area."
                    )
            except Exception as e:
                return FeatureMeasurement(
                    type="unsupported",
                    message=f"GeometryCollection measurement could not be computed: {str(e)}"
                )

        # 5. Unsupported geometry types
        return FeatureMeasurement(
            type="unsupported",
            message=f"Measurement is not supported for geometry type: '{geom_type}'"
        )
