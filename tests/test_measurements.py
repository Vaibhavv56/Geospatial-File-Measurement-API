import shapely.geometry
from app.services.measurement_service import MeasurementService


def test_polygon_measurement():
    # Polygon in Bengaluru (EPSG:4326)
    poly = shapely.geometry.Polygon([
        (77.5900, 12.9700),
        (77.5950, 12.9700),
        (77.5950, 12.9750),
        (77.5900, 12.9750),
        (77.5900, 12.9700),
    ])
    meas = MeasurementService.calculate_measurement(poly, "EPSG:4326")

    assert meas.type == "area"
    assert meas.unit == "square_meters"
    assert meas.area_sq_meters is not None
    assert meas.area_sq_meters > 200_000  # Expected ~300,000 m²
    assert meas.area_hectares is not None
    assert meas.area_hectares > 20
    assert meas.perimeter_meters is not None
    assert meas.perimeter_meters > 1500
    assert meas.projected_crs == "EPSG:32643"


def test_multipolygon_measurement():
    p1 = shapely.geometry.Polygon([(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)])
    p2 = shapely.geometry.Polygon([(77.60, 12.97), (77.605, 12.97), (77.605, 12.975), (77.60, 12.975), (77.60, 12.97)])
    mp = shapely.geometry.MultiPolygon([p1, p2])

    meas = MeasurementService.calculate_measurement(mp, "EPSG:4326")
    assert meas.type == "area"
    assert meas.area_sq_meters > 500_000
    assert meas.area_hectares > 50


def test_linestring_measurement():
    # LineString across ~0.01 degrees in latitude (~1.11 km)
    line = shapely.geometry.LineString([
        (77.5900, 12.9700),
        (77.5900, 12.9800),
    ])
    meas = MeasurementService.calculate_measurement(line, "EPSG:4326")

    assert meas.type == "length"
    assert meas.unit == "meters"
    assert meas.length_meters is not None
    assert 1050 < meas.length_meters < 1150  # ~1106 meters
    assert 1.05 < meas.length_km < 1.15
    assert meas.projected_crs == "EPSG:32643"


def test_multilinestring_measurement():
    l1 = shapely.geometry.LineString([(77.59, 12.97), (77.59, 12.98)])
    l2 = shapely.geometry.LineString([(77.60, 12.97), (77.60, 12.98)])
    mls = shapely.geometry.MultiLineString([l1, l2])

    meas = MeasurementService.calculate_measurement(mls, "EPSG:4326")
    assert meas.type == "length"
    assert 2100 < meas.length_meters < 2300


def test_point_measurement():
    point = shapely.geometry.Point(77.5925, 12.9725)
    meas = MeasurementService.calculate_measurement(point, "EPSG:4326")

    assert meas.type == "none"
    assert meas.area_sq_meters is None
    assert meas.length_meters is None
    assert "Point geometries" in meas.message


def test_multipoint_measurement():
    mp = shapely.geometry.MultiPoint([(77.59, 12.97), (77.60, 12.98)])
    meas = MeasurementService.calculate_measurement(mp, "EPSG:4326")

    assert meas.type == "none"
    assert meas.area_sq_meters is None
    assert meas.length_meters is None


def test_invalid_bowtie_polygon_repair():
    # Self-intersecting bowtie polygon
    bowtie = shapely.geometry.Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid

    meas = MeasurementService.calculate_measurement(bowtie, "EPSG:4326")
    # Should be gracefully repaired via make_valid rather than crashing
    assert meas.type == "area"
    assert meas.area_sq_meters is not None
    assert meas.area_sq_meters > 0


def test_empty_and_null_geometry():
    empty_poly = shapely.geometry.Polygon()
    meas_empty = MeasurementService.calculate_measurement(empty_poly)
    assert meas_empty.type == "none"

    meas_none = MeasurementService.calculate_measurement(None)
    assert meas_none.type == "none"


def test_polygon_with_inner_hole():
    # Outer ring 0 to 100 meters, inner ring 20 to 80 meters
    outer = [(77.590, 12.970), (77.600, 12.970), (77.600, 12.980), (77.590, 12.980), (77.590, 12.970)]
    hole = [(77.592, 12.972), (77.598, 12.972), (77.598, 12.978), (77.592, 12.978), (77.592, 12.972)]
    poly_hole = shapely.geometry.Polygon(shell=outer, holes=[hole])

    meas = MeasurementService.calculate_measurement(poly_hole, "EPSG:4326")
    assert meas.type == "area"
    assert meas.area_sq_meters is not None
    assert meas.area_sq_meters > 0

    # Area of polygon with hole must be less than solid polygon
    solid = shapely.geometry.Polygon(shell=outer)
    meas_solid = MeasurementService.calculate_measurement(solid, "EPSG:4326")
    assert meas.area_sq_meters < meas_solid.area_sq_meters


def test_geometry_collection_mixed():
    poly = shapely.geometry.Polygon([(77.59, 12.97), (77.595, 12.97), (77.595, 12.975), (77.59, 12.975), (77.59, 12.97)])
    line = shapely.geometry.LineString([(77.59, 12.97), (77.59, 12.98)])
    gc = shapely.geometry.GeometryCollection([poly, line])

    meas = MeasurementService.calculate_measurement(gc, "EPSG:4326")
    assert meas.type == "area"
    assert meas.area_sq_meters > 0
    assert meas.length_meters > 0
    assert "composite" in meas.message.lower()


def test_geometry_collection_points_only():
    p1 = shapely.geometry.Point(77.59, 12.97)
    p2 = shapely.geometry.Point(77.60, 12.98)
    gc = shapely.geometry.GeometryCollection([p1, p2])

    meas = MeasurementService.calculate_measurement(gc, "EPSG:4326")
    assert meas.type == "none"
    assert "only point geometries" in meas.message.lower()
