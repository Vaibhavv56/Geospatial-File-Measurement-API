from pathlib import Path
from fastapi.testclient import TestClient

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "drivers_available" in data


def test_kml_upload_and_measurements_flow(client: TestClient):
    kml_path = SAMPLES_DIR / "survey_parcels.kml"
    
    # 1. POST /api/files/ (Upload)
    with open(kml_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("survey_parcels.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    
    assert upload_resp.status_code == 201
    file_data = upload_resp.json()
    assert "id" in file_data
    file_id = file_data["id"]
    assert file_data["filename"] == "survey_parcels.kml"
    assert file_data["feature_count"] == 6
    assert file_data["crs"] == "EPSG:4326"
    assert file_data["status"] == "COMPLETED"
    assert file_data["summary"]["polygon_count"] == 2
    assert file_data["summary"]["linestring_count"] == 2
    assert file_data["summary"]["point_count"] == 2
    assert file_data["summary"]["total_area_sq_meters"] > 0
    assert file_data["summary"]["total_length_meters"] > 0

    # 2. GET /api/files/{id}/ (File Info)
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 6

    # 3. GET /api/files/{id}/measurements/ (Measurements)
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["id"] == file_id
    assert len(meas_data["features"]) == 6

    # Verify polygon measurements
    polygons = [f for f in meas_data["features"] if f["geometry_type"] == "Polygon"]
    assert len(polygons) == 2
    for p in polygons:
        m = p["measurement"]
        assert m["type"] == "area"
        assert m["unit"] == "square_meters"
        assert m["area_sq_meters"] > 0
        assert m["area_hectares"] > 0
        assert m["perimeter_meters"] > 0
        assert m["projected_crs"].startswith("EPSG:326")  # Local UTM Zone in Bangalore

    # Verify line measurements
    lines = [f for f in meas_data["features"] if f["geometry_type"] == "LineString"]
    assert len(lines) == 2
    for l in lines:
        m = l["measurement"]
        assert m["type"] == "length"
        assert m["unit"] == "meters"
        assert m["length_meters"] > 0
        assert m["projected_crs"].startswith("EPSG:326")

    # Verify point measurements
    points = [f for f in meas_data["features"] if f["geometry_type"] == "Point"]
    assert len(points) == 2
    for pt in points:
        m = pt["measurement"]
        assert m["type"] == "none"
        assert m["area_sq_meters"] is None
        assert m["length_meters"] is None

    # 4. GET /api/files/{id}/geojson/ (GeoJSON Export)
    geojson_resp = client.get(f"/api/files/{file_id}/geojson/")
    assert geojson_resp.status_code == 200
    geojson_data = geojson_resp.json()
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) == 6

    # 5. DELETE /api/files/{id}/
    del_resp = client.delete(f"/api/files/{file_id}/")
    assert del_resp.status_code == 204

    # Subsequent GET should return 404
    get_del = client.get(f"/api/files/{file_id}/")
    assert get_del.status_code == 404


def test_shapefile_zip_upload_and_measurements(client: TestClient):
    shp_zip = SAMPLES_DIR / "cadastral_parcels.zip"

    with open(shp_zip, "rb") as f:
        resp = client.post(
            "/api/files/",
            files={"file": ("cadastral_parcels.zip", f, "application/zip")},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["file_type"] == "SHAPEFILE"
    assert data["feature_count"] == 3
    assert data["summary"]["polygon_count"] == 3

    file_id = data["id"]
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    features = meas_resp.json()["features"]
    assert len(features) == 3

    for feat in features:
        assert feat["geometry_type"] == "Polygon"
        m = feat["measurement"]
        assert m["type"] == "area"
        assert m["area_sq_meters"] > 0
        assert m["area_acres"] > 0
        assert "EPSG:326" in m["projected_crs"]


def test_list_files_endpoint(client: TestClient):
    kml_path = SAMPLES_DIR / "road_network.kml"
    with open(kml_path, "rb") as f:
        client.post("/api/files/", files={"file": ("road_network.kml", f, "application/vnd.google-earth.kml+xml")})

    resp = client.get("/api/files/")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "files" in data
    assert data["total"] >= 1


def test_unsupported_file_extension(client: TestClient):
    resp = client.post(
        "/api/files/",
        files={"file": ("document.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert resp.status_code == 400
    assert "not supported" in resp.json()["detail"].lower()


def test_file_not_found(client: TestClient):
    resp = client.get("/api/files/nonexistent_file_999/")
    assert resp.status_code == 404
