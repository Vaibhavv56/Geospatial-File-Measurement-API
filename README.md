# Geospatial File Measurement API

A production-ready FastAPI service for ingesting geospatial files (Keyhole Markup Language and ESRI Shapefiles), performing Coordinate Reference System (CRS) transformations, and computing high-precision geometric measurements including areas, perimeters, and lengths.

---

## Overview

The Geospatial File Measurement API provides automated parsing, validation, reprojection, and geometric analysis of vector geospatial files. Geographic coordinates (such as WGS 84 / EPSG:4326) are dynamically reprojected into locally optimal Universal Transverse Mercator (UTM) projected coordinate systems to calculate planar metrics in SI units (meters and square meters) alongside secondary units (hectares, acres, kilometers).

### Key Features

- **Format Ingestion**: Supports `.kml` documents and zipped ESRI Shapefile packages (`.zip` containing `.shp`, `.shx`, `.dbf`, and optional `.prj`).
- **Dynamic Projection**: Automatically determines the centroid of ingested geometries and transforms coordinates into the appropriate local UTM projection (e.g., WGS 84 / UTM Zone 43N).
- **Geometric Calculations**: Computes planar areas, perimeters, and lengths for Polygons, MultiPolygons, LineStrings, and MultiLineStrings, while preserving Point locations and feature attributes.
- **Validation and Repair**: Detects and repairs common topological defects (such as self-intersecting "bowtie" polygons) using Shapely buffer validation.
- **RESTful Endpoints**: Full CRUD interface for file management, measurement inspection, and GeoJSON data export.
- **Interactive Visualization**: Built-in Leaflet-based map interface for file upload and geometry visualization.

---

## System Requirements

- Python 3.11 or higher
- GDAL / GEOS / PROJ development libraries (pre-bundled via Python wheels or system packages)
- Docker and Docker Compose (optional, for containerized deployment)

---

## Installation and Setup

### 1. Clone Repository

```bash
git clone https://github.com/Vaibhavv56/Geospatial-File-Measurement-API.git
cd Geospatial-File-Measurement-API
```

### 2. Virtual Environment Configuration

Create and activate a virtual environment:

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running the Application

### Local Development Server

Run using the entrypoint script:
```powershell
python run.py
```

Or run directly via Uvicorn:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

When started, the service provides the following interfaces:
- **Web Interface**: http://localhost:8000/
- **Interactive Swagger Documentation**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Service Health Check**: http://localhost:8000/api/health

### Docker Deployment

Run using Docker Compose:
```bash
docker compose up --build
```

Alternatively, build and run via Docker CLI:
```bash
docker build -t geospatial-measurement-api .
docker run -p 8000:8000 geospatial-measurement-api
```

---

## API Reference

### Endpoints

| HTTP Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web dashboard and Leaflet map visualizer |
| `GET` | `/api/health` | Service health status and driver availability |
| `POST` | `/api/files/` | Upload and process a geospatial file (`.kml` or `.zip`) |
| `GET` | `/api/files/` | Retrieve list of uploaded files |
| `GET` | `/api/files/{id}/` | Retrieve metadata and summary statistics for a file |
| `GET` | `/api/files/{id}/measurements/` | Retrieve detailed feature measurements |
| `GET` | `/api/files/{id}/geojson/` | Export processed features in GeoJSON format |
| `DELETE` | `/api/files/{id}/` | Delete uploaded file and purge stored data |

---

## Geometric Measurement Methodology

1. **CRS Detection**: The source CRS is identified from KML metadata or the Shapefile `.prj` sidecar file. If omitted, WGS 84 (`EPSG:4326`) is applied as the default geographic system.
2. **Optimal Projected CRS Selection**: For geographic coordinate systems expressed in angular units (degrees), the geometric centroid is computed to identify the corresponding UTM zone:
   $$\text{Zone} = \left\lfloor \frac{\text{Longitude} + 180}{6} \right\rfloor + 1$$
   The appropriate EPSG code (e.g., `EPSG:32643` for UTM Zone 43 North) is selected for Euclidean calculations.
3. **Reprojection**: Coordinate transformations are executed using `pyproj.Transformer` with `always_xy=True`.
4. **Calculations**:
   - **Polygon / MultiPolygon**: Surface area ($\text{m}^2$, hectares, acres), perimeter ($\text{m}$).
   - **LineString / MultiLineString**: Linear distance ($\text{m}$, $\text{km}$).
   - **Point / MultiPoint**: Coordinate extraction and point count.

---

## Automated Testing

The project maintains test coverage across parser validation, coordinate transformations, and geometric algorithms.

Run test suite:
```powershell
pytest
```

Run test suite with code coverage:
```powershell
pytest --cov=app tests/
```

---

## Sample Data

Sample datasets are located in the `samples/` directory:
- `survey_parcels.kml`: Parcels, linear features, and control points in Bengaluru, India.
- `road_network.kml`: Regional highway corridors.
- `cadastral_parcels.zip`: Zipped ESRI Shapefile package containing polygon cadastral records.

To regenerate sample files:
```powershell
python samples/generate_samples.py
```

---

## Project Structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── run.py
├── app/
│   ├── api/
│   │   ├── endpoints/
│   │   │   ├── files.py
│   │   │   └── health.py
│   │   └── router.py
│   ├── core/
│   │   ├── config.py
│   │   └── exceptions.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── crs_service.py
│   │   ├── file_processor.py
│   │   ├── measurement_service.py
│   │   ├── storage.py
│   │   └── parsers/
│   │       ├── base.py
│   │       ├── kml_parser.py
│   │       └── shapefile_parser.py
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── templates/
│       └── index.html
├── data/
├── samples/
└── tests/
```
