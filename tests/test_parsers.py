import io
import zipfile
from pathlib import Path
import pytest
from app.core.exceptions import CorruptFileError, EmptyDatasetError, UnsupportedFileFormatError
from app.services.parsers.kml_parser import KMLParser
from app.services.parsers.shapefile_parser import ShapefileParser

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def test_kml_parser_survey_parcels():
    parser = KMLParser()
    kml_path = SAMPLES_DIR / "survey_parcels.kml"
    result = parser.parse(kml_path)

    assert result.file_type == "KML"
    assert result.crs == "EPSG:4326"
    assert len(result.features) == 6

    # Verify extracted geometry types
    types = [f.geometry_type for f in result.features]
    assert types.count("Polygon") == 2
    assert types.count("LineString") == 2
    assert types.count("Point") == 2

    # Check properties extraction
    p1 = next(f for f in result.features if f.feature_id == "Parcel Alpha" or f.properties.get("name") == "Parcel Alpha")
    assert p1.properties.get("zoning") == "Commercial" or p1.properties.get("survey_no") == "SY-104/1"


def test_shapefile_parser_cadastral():
    parser = ShapefileParser()
    zip_path = SAMPLES_DIR / "cadastral_parcels.zip"
    result = parser.parse(zip_path)

    assert result.file_type == "SHAPEFILE"
    assert "EPSG:" in result.crs
    assert len(result.features) == 3

    for f in result.features:
        assert f.geometry_type == "Polygon"
        assert f.geometry is not None
        assert "PLOT_ID" in f.properties or "plot_id" in [k.lower() for k in f.properties.keys()]


def test_shapefile_parser_not_a_zip(tmp_path):
    parser = ShapefileParser()
    fake_file = tmp_path / "fake.zip"
    fake_file.write_text("not a real zip file")

    with pytest.raises(UnsupportedFileFormatError):
        parser.parse(fake_file)


def test_shapefile_parser_zip_missing_shp(tmp_path):
    parser = ShapefileParser()
    empty_zip = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty_zip, "w") as zf:
        zf.writestr("test.txt", "hello")

    with pytest.raises(CorruptFileError):
        parser.parse(empty_zip)


def test_shapefile_parser_zip_slip_protection(tmp_path):
    parser = ShapefileParser()
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../../etc/passwd.shp", "malicious payload")

    with pytest.raises(CorruptFileError) as exc_info:
        parser.parse(malicious_zip)
    assert "illegal relative path" in str(exc_info.value)


def test_kml_direct_xml_parser():
    parser = KMLParser()
    kml_path = SAMPLES_DIR / "survey_parcels.kml"
    result = parser._parse_with_xml(kml_path)

    assert result.file_type == "KML"
    assert len(result.features) == 6
    types = [f.geometry_type for f in result.features]
    assert "Polygon" in types
    assert "LineString" in types
    assert "Point" in types


def test_kml_corrupt_xml(tmp_path):
    parser = KMLParser()
    corrupt = tmp_path / "broken.kml"
    corrupt.write_text("<kml><unclosed></kml>")

    with pytest.raises(CorruptFileError):
        parser._parse_with_xml(corrupt)


def test_kml_empty_placemarks(tmp_path):
    parser = KMLParser()
    empty_kml = tmp_path / "empty.kml"
    empty_kml.write_text("""<?xml version="1.0"?><kml><Document><name>Empty</name></Document></kml>""")

    with pytest.raises(EmptyDatasetError):
        parser._parse_with_xml(empty_kml)
