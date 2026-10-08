import logging
import math
from typing import Optional, Tuple
import shapely.geometry
import shapely.ops
from pyproj import CRS, Transformer

logger = logging.getLogger(__name__)


class CRSService:
    """
    Intelligent Coordinate Reference System (CRS) management and projection service.
    
    Ensures that geographic coordinates (degrees, e.g., EPSG:4326) are never used directly
    for Euclidean measurements. Automatically determines optimal conformal/equal-area
    projected coordinate systems (e.g., local UTM zones or equal-area projections) based
    on feature centroid and spatial extent.
    """

    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    def parse_crs(cls, crs_input: Optional[str]) -> CRS:
        """
        Parses various CRS representations (EPSG codes, WKT strings, PROJ strings).
        Defaults to EPSG:4326 if None or unparseable.
        """
        if not crs_input:
            return CRS.from_epsg(4326)
        try:
            return CRS.from_user_input(crs_input)
        except Exception as e:
            logger.warning("Failed to parse CRS input '%s': %s. Falling back to %s", crs_input, e, cls.DEFAULT_GEOGRAPHIC_CRS)
            return CRS.from_epsg(4326)

    @classmethod
    def get_utm_epsg_for_coordinates(cls, lon: float, lat: float) -> Tuple[int, str]:
        """
        Calculates optimal Universal Transverse Mercator (UTM) or Universal Polar
        Stereographic (UPS) EPSG code for a given longitude and latitude.
        
        Returns:
            Tuple of (epsg_code, description)
        """
        # Clamp latitude to valid domain
        lat = max(min(lat, 89.999), -89.999)
        # Normalize longitude to [-180, 180]
        lon = ((lon + 180) % 360) - 180

        # Polar regions (> 84°N or < 80°S) use UPS
        if lat >= 84.0:
            return 32661, "Universal Polar Stereographic North (WGS 84)"
        if lat <= -80.0:
            return 32761, "Universal Polar Stereographic South (WGS 84)"

        # Standard UTM zones 1-60 (6 degrees width each)
        zone = int((lon + 180) / 6.0) + 1
        zone = max(min(zone, 60), 1)

        if lat >= 0:
            epsg_code = 32600 + zone
            desc = f"UTM Zone {zone}N (EPSG:{epsg_code}) - Conformal local metric projection"
        else:
            epsg_code = 32700 + zone
            desc = f"UTM Zone {zone}S (EPSG:{epsg_code}) - Conformal local metric projection"

        return epsg_code, desc

    @classmethod
    def determine_target_projected_crs(
        cls,
        geometry: shapely.geometry.base.BaseGeometry,
        source_crs: CRS
    ) -> Tuple[CRS, str]:
        """
        Determines the most accurate projected CRS for calculating measurements on the geometry.
        
        - If source is already a local projected CRS (e.g. local UTM / State Plane) and NOT
          Web Mercator (EPSG:3857 which suffers from extreme latitudinal scale distortion),
          it can be preserved.
        - If source is geographic (degrees, e.g. EPSG:4326) or Web Mercator (EPSG:3857),
          we calculate the optimal local UTM zone based on geometry centroid.
        """
        # Check if source CRS is already a suitable local projected CRS in meters
        is_web_mercator = False
        try:
            if source_crs.to_epsg() in (3857, 900913):
                is_web_mercator = True
        except Exception:
            pass

        if source_crs.is_projected and not is_web_mercator:
            # Check linear units
            axis_units = source_crs.axis_info[0].unit_name if source_crs.axis_info else "metre"
            return source_crs, f"Source Projected CRS ({source_crs.name}, linear units: {axis_units})"

        # If source is Web Mercator, first convert geometry centroid to WGS84 to find true lon/lat
        if is_web_mercator:
            centroid = geometry.centroid
            to_wgs84 = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)
            lon, lat = to_wgs84.transform(centroid.x, centroid.y)
        else:
            # Source is geographic (EPSG:4326 or similar)
            centroid = geometry.centroid
            lon, lat = centroid.x, centroid.y

        # Handle NaN / invalid centroids
        if math.isnan(lon) or math.isnan(lat):
            lon, lat = 0.0, 0.0

        epsg_code, desc = cls.get_utm_epsg_for_coordinates(lon, lat)
        target_crs = CRS.from_epsg(epsg_code)
        return target_crs, desc

    @classmethod
    def project_geometry(
        cls,
        geometry: shapely.geometry.base.BaseGeometry,
        source_crs_input: Optional[str]
    ) -> Tuple[shapely.geometry.base.BaseGeometry, str, str]:
        """
        Projects a geometry into an optimal metric coordinate system.
        
        Returns:
            Tuple of (projected_geometry, target_crs_str, projection_description)
        """
        source_crs = cls.parse_crs(source_crs_input)
        target_crs, desc = cls.determine_target_projected_crs(geometry, source_crs)

        # If source and target are effectively the same CRS, return directly
        if source_crs == target_crs:
            crs_str = f"EPSG:{target_crs.to_epsg()}" if target_crs.to_epsg() else target_crs.to_string()
            return geometry, crs_str, desc

        # Perform transformation
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        projected_geom = shapely.ops.transform(transformer.transform, geometry)

        target_crs_str = f"EPSG:{target_crs.to_epsg()}" if target_crs.to_epsg() else str(target_crs)
        return projected_geom, target_crs_str, desc
