import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional
import pyproj
import shapely.geometry
from app.core.exceptions import CorruptFileError, EmptyDatasetError, UnsupportedFileFormatError
from app.services.parsers.base import BaseGeospatialParser, ParsedFeature, ParsedGeospatialData

logger = logging.getLogger(__name__)


class ShapefileParser(BaseGeospatialParser):
    """
    Parser for ESRI Shapefiles packaged as .zip archives.
    
    Extracts features, coordinates, geometry types, attributes, and spatial reference (CRS)
    from .shp, .dbf, and .prj files inside the zip archive.
    """

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        if not zipfile.is_zipfile(file_path):
            raise UnsupportedFileFormatError("The uploaded file is not a valid ZIP archive.")

        temp_dir = tempfile.mkdtemp(prefix="shp_extract_")
        try:
            # 1. Safely extract zip with Zip Slip protection
            self._safe_extract_zip(file_path, temp_dir)

            # 2. Locate .shp file
            shp_files = list(Path(temp_dir).rglob("*.shp"))
            if not shp_files:
                raise CorruptFileError("The ZIP archive does not contain any .shp (Shapefile) file.")

            shp_path = shp_files[0]
            logger.info("Found Shapefile to parse: %s", shp_path.name)

            # 3. Read CRS from .prj if available
            prj_files = list(Path(temp_dir).rglob("*.prj"))
            source_crs_str = "EPSG:4326"
            if prj_files:
                try:
                    prj_text = prj_files[0].read_text(encoding="utf-8", errors="ignore").strip()
                    if prj_text:
                        parsed_crs = pyproj.CRS.from_wkt(prj_text)
                        epsg = parsed_crs.to_epsg()
                        source_crs_str = f"EPSG:{epsg}" if epsg else parsed_crs.to_string()
                except Exception as e:
                    logger.warning("Could not parse .prj file (%s): %s. Falling back to EPSG:4326", prj_files[0].name, e)

            # 4. Try parsing using pyogrio/geopandas first
            try:
                return self._parse_with_pyogrio(shp_path, source_crs_str)
            except Exception as e:
                logger.warning("pyogrio failed to read Shapefile: %s. Falling back to pyshp.", e)
                return self._parse_with_pyshp(shp_path, source_crs_str)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _safe_extract_zip(self, zip_path: Path, extract_to: str) -> None:
        """Extracts zip archive while preventing path traversal (Zip Slip)."""
        target_path = Path(extract_to).resolve()
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                # Check for Zip Slip vulnerability
                member_path = (target_path / member.filename).resolve()
                if not str(member_path).startswith(str(target_path)):
                    raise CorruptFileError(f"Security error: ZIP archive contains illegal relative path '{member.filename}'")
                zf.extract(member, target_path)

    def _parse_with_pyogrio(self, shp_path: Path, fallback_crs: str) -> ParsedGeospatialData:
        import pyogrio

        info = pyogrio.read_info(shp_path)
        feature_count = info.get("features", 0)
        if feature_count == 0:
            raise EmptyDatasetError("Shapefile contains zero features.")

        # Read CRS from pyogrio metadata if not already discovered
        detected_crs = info.get("crs")
        source_crs = fallback_crs
        if detected_crs:
            try:
                crs_obj = pyproj.CRS.from_user_input(detected_crs)
                epsg = crs_obj.to_epsg()
                source_crs = f"EPSG:{epsg}" if epsg else crs_obj.to_string()
            except Exception:
                pass

        import math
        import pandas as pd

        df = pyogrio.read_dataframe(shp_path)
        features: list[ParsedFeature] = []

        for idx, row in df.iterrows():
            geom = row.get("geometry")
            # Extract properties (all columns except geometry)
            props = {}
            for col in df.columns:
                if col != "geometry":
                    val = row[col]
                    if pd.isna(val):
                        val = None
                    elif hasattr(val, "item"):
                        val = val.item()
                        if isinstance(val, float) and math.isnan(val):
                            val = None
                    elif hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif isinstance(val, float) and math.isnan(val):
                        val = None
                    props[str(col)] = val

            geom_type = geom.geom_type if geom is not None and not geom.is_empty else "Unknown"
            geom_geojson = shapely.geometry.mapping(geom) if geom is not None and not geom.is_empty else None

            # Determine best feature id
            fid = props.get("id") or props.get("ID") or props.get("FID") or props.get("OBJECTID") or idx

            features.append(
                ParsedFeature(
                    feature_id=fid,
                    geometry_type=geom_type,
                    geometry=geom,
                    geometry_geojson=geom_geojson,
                    properties=props,
                    crs=source_crs,
                )
            )

        if not features:
            raise EmptyDatasetError("Shapefile contains zero valid features.")

        return ParsedGeospatialData(
            crs=source_crs,
            features=features,
            file_type="SHAPEFILE",
        )

    def _parse_with_pyshp(self, shp_path: Path, source_crs: str) -> ParsedGeospatialData:
        import shapefile

        try:
            sf = shapefile.Reader(str(shp_path))
        except Exception as e:
            raise CorruptFileError(f"Failed to read Shapefile with pyshp: {str(e)}")

        if len(sf) == 0:
            raise EmptyDatasetError("Shapefile contains zero features.")

        features: list[ParsedFeature] = []
        for idx, shape_rec in enumerate(sf.shapeRecords()):
            shape_obj = shape_rec.shape
            record_dict = shape_rec.record.as_dict()

            geom = None
            geom_geojson = None
            geom_type = "Unknown"

            if shape_obj and len(shape_obj.points) > 0:
                try:
                    geo_interface = shape_obj.__geo_interface__
                    geom = shapely.geometry.shape(geo_interface)
                    geom_type = geom.geom_type
                    geom_geojson = shapely.geometry.mapping(geom)
                except Exception as e:
                    logger.warning("Feature %d geometry conversion failed: %s", idx, e)

            fid = record_dict.get("id") or record_dict.get("ID") or record_dict.get("FID") or idx

            features.append(
                ParsedFeature(
                    feature_id=fid,
                    geometry_type=geom_type,
                    geometry=geom,
                    geometry_geojson=geom_geojson,
                    properties=record_dict,
                    crs=source_crs,
                )
            )

        return ParsedGeospatialData(
            crs=source_crs,
            features=features,
            file_type="SHAPEFILE",
        )
