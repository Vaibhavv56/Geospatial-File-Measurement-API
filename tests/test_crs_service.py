import shapely.geometry
from pyproj import CRS
from app.services.crs_service import CRSService


def test_parse_crs():
    # Valid EPSG code
    crs_4326 = CRSService.parse_crs("EPSG:4326")
    assert crs_4326.to_epsg() == 4326

    # Valid Projected EPSG
    crs_3857 = CRSService.parse_crs("EPSG:3857")
    assert crs_3857.to_epsg() == 3857

    # None or empty fallback
    crs_fallback = CRSService.parse_crs(None)
    assert crs_fallback.to_epsg() == 4326

    # Garbage input fallback
    crs_invalid = CRSService.parse_crs("INVALID_CRS_STRING")
    assert crs_invalid.to_epsg() == 4326


def test_utm_zone_calculation():
    # Bengaluru, India (77.5° E, 12.9° N) -> Zone 43N (EPSG:32643)
    epsg, desc = CRSService.get_utm_epsg_for_coordinates(77.59, 12.97)
    assert epsg == 32643
    assert "Zone 43N" in desc

    # Sydney, Australia (151.2° E, -33.8° S) -> Zone 56S (EPSG:32756)
    epsg_syd, desc_syd = CRSService.get_utm_epsg_for_coordinates(151.2, -33.86)
    assert epsg_syd == 32756
    assert "Zone 56S" in desc_syd

    # London, UK (-0.12° W, 51.5° N) -> Zone 30N (EPSG:32630)
    epsg_lon, desc_lon = CRSService.get_utm_epsg_for_coordinates(-0.12, 51.5)
    assert epsg_lon == 32630

    # North Pole (> 84° N) -> UPS North (EPSG:32661)
    epsg_np, desc_np = CRSService.get_utm_epsg_for_coordinates(0.0, 85.0)
    assert epsg_np == 32661


def test_project_geometry_accuracy():
    # A polygon of approximately 0.01 x 0.01 degrees at the equator
    # 0.01 degree at equator is approx 1113 meters on each side
    # Expected area is roughly ~1.23 square kilometers (1,230,000 m²)
    poly = shapely.geometry.Polygon([
        (0.0, 0.0),
        (0.01, 0.0),
        (0.01, 0.01),
        (0.0, 0.01),
        (0.0, 0.0),
    ])

    projected_geom, target_crs, desc = CRSService.project_geometry(poly, "EPSG:4326")
    
    assert target_crs.startswith("EPSG:326")
    # Area should be metric in square meters (approx 1.23 million m²), NOT square degrees (0.0001)
    assert projected_geom.area > 1_000_000
    assert projected_geom.area < 1_500_000
    # Perimeter should be approx 4450 meters
    assert projected_geom.length > 4000
    assert projected_geom.length < 5000
