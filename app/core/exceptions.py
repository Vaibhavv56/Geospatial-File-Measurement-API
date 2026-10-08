class GeospatialServiceError(Exception):
    """Base exception for geospatial measurement service errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RecordNotFoundError(GeospatialServiceError):
    """Raised when an uploaded file or feature record cannot be found."""
    def __init__(self, message: str = "Requested geospatial record not found."):
        super().__init__(message, status_code=404)


class UnsupportedFileFormatError(GeospatialServiceError):
    """Raised when uploaded file format is not supported."""
    def __init__(self, message: str = "Unsupported file format. Please upload .kml or .zip (containing Shapefile)."):
        super().__init__(message, status_code=400)


class CorruptFileError(GeospatialServiceError):
    """Raised when uploaded file is corrupted or cannot be read."""
    def __init__(self, message: str = "File is corrupted or has an invalid structure."):
        super().__init__(message, status_code=422)


class EmptyDatasetError(GeospatialServiceError):
    """Raised when uploaded file contains no geospatial features."""
    def __init__(self, message: str = "Geospatial file contains zero features."):
        super().__init__(message, status_code=422)


class CrsTransformationError(GeospatialServiceError):
    """Raised when CRS transformation fails."""
    def __init__(self, message: str = "Failed to determine or project CRS."):
        super().__init__(message, status_code=422)
