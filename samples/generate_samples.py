import os
import shutil
import zipfile
from pathlib import Path
import pyproj
import shapefile
import shapely.geometry

SAMPLES_DIR = Path(__file__).parent
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def generate_kml_survey_parcels():
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Survey Parcels and Infrastructure</name>
    <description>Realistic survey dataset containing agricultural parcels, roadways, and control points in Bengaluru, India (EPSG:4326).</description>
    
    <!-- Parcel Alpha: Polygon -->
    <Placemark>
      <name>Parcel Alpha</name>
      <description>Commercial Development Zone A</description>
      <ExtendedData>
        <Data name="survey_no"><value>SY-104/1</value></Data>
        <Data name="zoning"><value>Commercial</value></Data>
        <Data name="owner"><value>Karnataka Industrial Corp</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0 77.5950,12.9700,0 77.5950,12.9750,0 77.5900,12.9750,0 77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Parcel Beta: Polygon with Hole (Courtyard) -->
    <Placemark>
      <name>Parcel Beta</name>
      <description>Residential Estate B</description>
      <ExtendedData>
        <Data name="survey_no"><value>SY-105/2</value></Data>
        <Data name="zoning"><value>Residential High-Density</value></Data>
        <Data name="owner"><value>Greenfield Estates Ltd</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5960,12.9700,0 77.6020,12.9700,0 77.6020,12.9740,0 77.5960,12.9740,0 77.5960,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
        <innerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5980,12.9710,0 77.6000,12.9710,0 77.6000,12.9730,0 77.5980,12.9730,0 77.5980,12.9710,0
            </coordinates>
          </LinearRing>
        </innerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Arterial Road: LineString -->
    <Placemark>
      <name>Main Spine Road</name>
      <description>4-lane divided collector boulevard</description>
      <ExtendedData>
        <Data name="road_class"><value>Arterial</value></Data>
        <Data name="surface"><value>Asphalt</value></Data>
        <Data name="lanes"><value>4</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5880,12.9690,920 77.5930,12.9715,922 77.5980,12.9730,925 77.6040,12.9760,928
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Drainage Canal: LineString -->
    <Placemark>
      <name>Stormwater Drainage Canal</name>
      <description>Reinforced concrete stormwater channel</description>
      <ExtendedData>
        <Data name="type"><value>Open Canal</value></Data>
        <Data name="width_m"><value>3.5</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5900,12.9760,918 77.5960,12.9755,916 77.6010,12.9750,914
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Survey Monument: Point -->
    <Placemark>
      <name>GCP Monument #42</name>
      <description>Permanent Geodetic Ground Control Point</description>
      <ExtendedData>
        <Data name="elevation_m"><value>924.5</value></Data>
        <Data name="order"><value>First Order Benchmark</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5925,12.9725,924.5</coordinates>
      </Point>
    </Placemark>

    <!-- Borewell: Point -->
    <Placemark>
      <name>Monitoring Borewell #07</name>
      <description>Subsurface hydrological sensor station</description>
      <ExtendedData>
        <Data name="depth_m"><value>180.0</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5975,12.9715,920.0</coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""
    file_path = SAMPLES_DIR / "survey_parcels.kml"
    file_path.write_text(kml_content.strip(), encoding="utf-8")
    print(f"Generated: {file_path}")


def generate_kml_road_network():
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Regional Highway Corridors</name>
    <Placemark>
      <name>Outer Ring Road Expressway - Section 1</name>
      <LineString>
        <coordinates>
          77.600,12.900,900 77.620,12.915,905 77.640,12.935,910 77.660,12.960,915
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Industrial Link Road - Section 2</name>
      <LineString>
        <coordinates>
          77.620,12.915,905 77.610,12.930,908 77.600,12.945,912
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    file_path = SAMPLES_DIR / "road_network.kml"
    file_path.write_text(kml_content.strip(), encoding="utf-8")
    print(f"Generated: {file_path}")


def generate_shapefile_zip():
    temp_shp_dir = SAMPLES_DIR / "_temp_shp"
    temp_shp_dir.mkdir(parents=True, exist_ok=True)
    base_name = "cadastral_parcels"
    shp_base = temp_shp_dir / base_name

    # Write Shapefile using pyshp
    w = shapefile.Writer(str(shp_base), shapefile.POLYGON)
    w.field("PLOT_ID", "C", 20)
    w.field("ZONE", "C", 25)
    w.field("SECTOR", "N", 5)
    w.field("TAX_CODE", "C", 15)

    # Polygon 1: Parcel 101 in Delhi / Gurgaon (EPSG:4326 ~28.45 Lat, 77.02 Lon)
    poly1 = [
        [77.020, 28.450],
        [77.025, 28.450],
        [77.025, 28.455],
        [77.020, 28.455],
        [77.020, 28.450]
    ]
    w.poly([poly1])
    w.record(PLOT_ID="PLOT-101", ZONE="Industrial Light", SECTOR=4, TAX_CODE="TX-2026-A")

    # Polygon 2: Parcel 102
    poly2 = [
        [77.026, 28.450],
        [77.032, 28.450],
        [77.032, 28.454],
        [77.026, 28.454],
        [77.026, 28.450]
    ]
    w.poly([poly2])
    w.record(PLOT_ID="PLOT-102", ZONE="Logistics & Warehousing", SECTOR=4, TAX_CODE="TX-2026-B")

    # Polygon 3: Parcel 103 (Irregular L-shape)
    poly3 = [
        [77.020, 28.456],
        [77.030, 28.456],
        [77.030, 28.458],
        [77.025, 28.458],
        [77.025, 28.460],
        [77.020, 28.460],
        [77.020, 28.456]
    ]
    w.poly([poly3])
    w.record(PLOT_ID="PLOT-103", ZONE="Commercial Retail", SECTOR=5, TAX_CODE="TX-2026-C")

    w.close()

    # Create WGS84 .prj file
    prj_content = (
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
    )
    prj_path = temp_shp_dir / f"{base_name}.prj"
    prj_path.write_text(prj_content, encoding="utf-8")

    # Create zip archive
    zip_path = SAMPLES_DIR / "cadastral_parcels.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in temp_shp_dir.glob(f"{base_name}.*"):
            zf.write(f, arcname=f.name)

    # Clean up temp files
    shutil.rmtree(temp_shp_dir)
    print(f"Generated: {zip_path}")


if __name__ == "__main__":
    generate_kml_survey_parcels()
    generate_kml_road_network()
    generate_shapefile_zip()
    print("All sample files generated successfully!")
