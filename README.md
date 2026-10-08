# Aereo Geospatial File Measurement API

A production-ready FastAPI service designed for ingesting geospatial files (`.kml` and `.zip` Shapefiles), automatically reprojecting coordinates into optimal projected coordinate systems (local UTM zones), and computing high-precision geometric measurements (areas, perimeters, lengths, coordinate counts).

---

## 🚀 Quick Start Guide

### 1. Run Locally (Recommended)

A configured Python virtual environment (`.venv`) is already present with all required dependencies installed.

#### Option A: Run directly using the virtual environment
```powershell
# Using the preconfigured virtual environment directly
.\.venv\Scripts\python.exe run.py
```

#### Option B: Activate the virtual environment first
**PowerShell:**
```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

**Command Prompt (`cmd`):**
```cmd
.\.venv\Scripts\activate.bat
python run.py
```

**Direct Uvicorn command:**
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running, the application will be available at:
- **Interactive Web UI**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 2. Run with Docker / Docker Compose

You can containerize and run the service using Docker:

#### Using Docker Compose:
```bash
docker compose up --build
```

#### Using Docker CLI:
```bash
docker build -t aereo-geomeasure .
docker run -p 8000:8000 aereo-geomeasure
```

---

## 🧪 Running Automated Tests

Run the test suite with coverage using `pytest`:

```powershell
.\.venv\Scripts\pytest
```

To run with full coverage report:
```powershell
.\.venv\Scripts\pytest --cov=app tests/
```

---

## 📁 Sample Datasets

Synthetic sample datasets are located in the [samples/](file:///d:/aereo/samples) directory:
- `survey_parcels.kml` (Polygons, Lines, Points in Bengaluru)
- `road_network.kml` (LineString highway network)
- `cadastral_parcels.zip` (Shapefile package containing `.shp`, `.shx`, `.dbf`, `.prj`)

To re-generate them at any time:
```powershell
.\.venv\Scripts\python.exe samples/generate_samples.py
```

---

## 📡 API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI Dashboard & Leaflet Map Visualizer |
| `GET` | `/api/health` | Service health & driver availability |
| `POST` | `/api/files/` | Upload `.kml` or `.zip` (Shapefile) |
| `GET` | `/api/files/` | List all processed files |
| `GET` | `/api/files/{id}/` | File metadata and summary stats |
| `GET` | `/api/files/{id}/measurements/` | Full feature-level measurement calculations |
| `GET` | `/api/files/{id}/geojson/` | Export processed features as standard GeoJSON |
| `DELETE` | `/api/files/{id}/` | Delete uploaded file and clean storage |
