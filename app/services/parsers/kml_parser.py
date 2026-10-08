import logging
import re
from pathlib import Path
from typing import Any, Optional
import defusedxml.ElementTree as ET
import shapely.geometry
from app.core.exceptions import CorruptFileError, EmptyDatasetError
from app.services.parsers.base import BaseGeospatialParser, ParsedFeature, ParsedGeospatialData

logger = logging.getLogger(__name__)


class KMLParser(BaseGeospatialParser):
    """
    Parser for Open Geospatial Consortium (OGC) KML files.
    
    Tries pyogrio first, with a comprehensive XML fallback to ensure robust parsing
    of all KML dialects, namespaces, and ExtendedData attributes.
    """

    KML_CRS = "EPSG:4326"

    def parse(self, file_path: Path) -> ParsedGeospatialData:
        # First attempt: pyogrio
        try:
            return self._parse_with_pyogrio(file_path)
        except Exception as e:
            logger.info("pyogrio failed to parse KML (%s). Falling back to direct XML parser.", e)
            return self._parse_with_xml(file_path)

    def _parse_with_pyogrio(self, file_path: Path) -> ParsedGeospatialData:
        import pyogrio

        import math
        import pandas as pd

        df = pyogrio.read_dataframe(file_path)
        if len(df) == 0:
            raise EmptyDatasetError("KML file contains zero features.")

        features: list[ParsedFeature] = []
        for idx, row in df.iterrows():
            geom = row.get("geometry")
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
            fid = props.get("Name") or props.get("name") or props.get("id") or idx

            features.append(
                ParsedFeature(
                    feature_id=fid,
                    geometry_type=geom_type,
                    geometry=geom,
                    geometry_geojson=geom_geojson,
                    properties=props,
                    crs=self.KML_CRS,
                )
            )

        return ParsedGeospatialData(
            crs=self.KML_CRS,
            features=features,
            file_type="KML",
        )

    def _parse_with_xml(self, file_path: Path) -> ParsedGeospatialData:
        try:
            tree = ET.parse(str(file_path))
            root = tree.getroot()
        except Exception as e:
            raise CorruptFileError(f"Malformed KML XML content: {str(e)}")

        # Helper to strip namespace from tags
        def strip_ns(tag: str) -> str:
            return re.sub(r"\{.*?\}", "", tag)

        placemarks = [elem for elem in root.iter() if strip_ns(elem.tag) == "Placemark"]
        if not placemarks:
            raise EmptyDatasetError("KML file contains zero <Placemark> features.")

        features: list[ParsedFeature] = []

        for idx, placemark in enumerate(placemarks):
            props: dict[str, Any] = {}
            geom = None
            geom_type = "Unknown"

            # Parse attributes
            for child in placemark:
                clean_tag = strip_ns(child.tag)
                if clean_tag in ("name", "description"):
                    if child.text:
                        props[clean_tag] = child.text.strip()
                elif clean_tag == "ExtendedData":
                    for sub in child:
                        sub_tag = strip_ns(sub.tag)
                        if sub_tag == "Data":
                            name_attr = sub.get("name")
                            val_elem = next((v for v in sub if strip_ns(v.tag) == "value"), None)
                            if name_attr and (val_elem is not None) and val_elem.text:
                                props[name_attr] = val_elem.text.strip()
                        elif sub_tag == "SchemaData":
                            for sdata in sub:
                                if strip_ns(sdata.tag) == "SimpleData":
                                    sname = sdata.get("name")
                                    if sname and sdata.text:
                                        props[sname] = sdata.text.strip()

            # Parse geometry elements
            geom = self._extract_geometry_from_element(placemark, strip_ns)
            if geom:
                geom_type = geom.geom_type
                geom_geojson = shapely.geometry.mapping(geom)
            else:
                geom_geojson = None

            fid = props.get("name") or props.get("id") or idx
            features.append(
                ParsedFeature(
                    feature_id=fid,
                    geometry_type=geom_type,
                    geometry=geom,
                    geometry_geojson=geom_geojson,
                    properties=props,
                    crs=self.KML_CRS,
                )
            )

        if not features:
            raise EmptyDatasetError("KML file contains zero valid features.")

        return ParsedGeospatialData(
            crs=self.KML_CRS,
            features=features,
            file_type="KML",
        )

    def _extract_geometry_from_element(self, element: Any, strip_ns: Any) -> Optional[shapely.geometry.base.BaseGeometry]:
        for child in element:
            tag = strip_ns(child.tag)
            if tag == "Point":
                coords = self._parse_coordinates(child, strip_ns)
                if coords:
                    return shapely.geometry.Point(coords[0][:2])
            elif tag == "LineString":
                coords = self._parse_coordinates(child, strip_ns)
                if coords and len(coords) >= 2:
                    return shapely.geometry.LineString([c[:2] for c in coords])
            elif tag == "Polygon":
                return self._parse_polygon(child, strip_ns)
            elif tag == "MultiGeometry":
                sub_geoms = []
                for sub in child:
                    sg = self._extract_geometry_from_element([sub], strip_ns)
                    if sg:
                        sub_geoms.append(sg)
                if sub_geoms:
                    return shapely.geometry.GeometryCollection(sub_geoms)
        return None

    def _parse_polygon(self, poly_elem: Any, strip_ns: Any) -> Optional[shapely.geometry.Polygon]:
        shell = []
        holes = []

        for child in poly_elem:
            tag = strip_ns(child.tag)
            if tag == "outerBoundaryIs":
                ring = next((r for r in child if strip_ns(r.tag) == "LinearRing"), None)
                if ring is not None:
                    coords = self._parse_coordinates(ring, strip_ns)
                    if coords and len(coords) >= 3:
                        shell = [c[:2] for c in coords]
            elif tag == "innerBoundaryIs":
                ring = next((r for r in child if strip_ns(r.tag) == "LinearRing"), None)
                if ring is not None:
                    coords = self._parse_coordinates(ring, strip_ns)
                    if coords and len(coords) >= 3:
                        holes.append([c[:2] for c in coords])

        if shell and len(shell) >= 3:
            try:
                return shapely.geometry.Polygon(shell=shell, holes=holes if holes else None)
            except Exception as e:
                logger.warning("Error constructing Shapely polygon: %s", e)
        return None

    def _parse_coordinates(self, parent_elem: Any, strip_ns: Any) -> list[tuple[float, ...]]:
        coords_elem = next((c for c in parent_elem if strip_ns(c.tag) == "coordinates"), None)
        if coords_elem is None or not coords_elem.text:
            return []

        coord_strings = coords_elem.text.strip().split()
        parsed: list[tuple[float, ...]] = []
        for cs in coord_strings:
            parts = cs.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    if len(parts) >= 3:
                        alt = float(parts[2])
                        parsed.append((lon, lat, alt))
                    else:
                        parsed.append((lon, lat))
                except ValueError:
                    continue
        return parsed
