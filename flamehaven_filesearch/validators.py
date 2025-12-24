"""
Input validation module for FLAMEHAVEN FileSearch

Validators for file uploads, search queries, and configuration parameters.
"""

import os
import re
from typing import List, Optional, Tuple

from .exceptions import (
    EmptySearchQueryError,
    FileSizeExceededError,
    InvalidFilenameError,
    InvalidSearchQueryError,
    ValidationError,
)


class FilenameValidator:
    """Validator for file names and paths"""

    # Dangerous path patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\.",  # Parent directory
        r"^/",  # Absolute path
        r"^\\",  # Windows absolute path
        r"^[A-Za-z]:",  # Windows drive letter
    ]

    # Invalid filename characters (OS-specific)
    INVALID_CHARS_PATTERN = r'[<>:"|?*\x00-\x1f]'  # Windows + control chars

    # Maximum filename length (typical filesystem limit)
    MAX_FILENAME_LENGTH = 255

    @classmethod
    def validate_filename(cls, filename: str, allow_empty: bool = False) -> str:
        """
        Validate and sanitize filename

        Args:
            filename: Original filename
            allow_empty: Whether to allow empty filenames

        Returns:
            Sanitized filename

        Raises:
            InvalidFilenameError: If filename is invalid
        """
        # Check empty
        if not filename or not filename.strip():
            if allow_empty:
                return ""
            raise InvalidFilenameError(filename, "Filename cannot be empty")

        filename = filename.strip()

        # Check for path traversal attempts
        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, filename):
                raise InvalidFilenameError(
                    filename,
                    (
                        "Path traversal detected - filename must not contain "
                        "path components"
                    ),
                )

        # Check for directory separators
        if "/" in filename or "\\" in filename:
            # Extract basename (last component)
            filename = os.path.basename(filename)
            if not filename:
                raise InvalidFilenameError(
                    filename, "Invalid path - no filename component"
                )

        # Check for hidden files (starting with .)
        if filename.startswith("."):
            raise InvalidFilenameError(filename, "Hidden files not allowed")

        # Check for invalid characters
        if re.search(cls.INVALID_CHARS_PATTERN, filename):
            raise InvalidFilenameError(filename, "Filename contains invalid characters")

        # Check length
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            raise InvalidFilenameError(
                filename,
                f"Filename too long (max {cls.MAX_FILENAME_LENGTH} characters)",
            )

        # Check for reserved names (Windows)
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        ]
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            raise InvalidFilenameError(
                filename, f"Reserved filename: {name_without_ext}"
            )

        return filename

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename by removing/replacing invalid characters

        Args:
            filename: Original filename

        Returns:
            Sanitized safe filename
        """
        # Extract basename if path provided
        filename = os.path.basename(filename)

        # Remove leading dots (hidden files)
        filename = filename.lstrip(".")

        # Replace invalid characters with underscore
        filename = re.sub(cls.INVALID_CHARS_PATTERN, "_", filename)

        # Remove path traversal sequences
        filename = filename.replace("..", "_")

        # Limit length
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(filename)
            max_name_len = cls.MAX_FILENAME_LENGTH - len(ext)
            filename = name[:max_name_len] + ext

        # Ensure not empty after sanitization
        if not filename:
            filename = "unnamed_file"

        return filename


class FileSizeValidator:
    """Validator for file sizes"""

    @staticmethod
    def validate_file_size(
        file_size: int, max_size_mb: int, filename: Optional[str] = None
    ) -> None:
        """
        Validate file size against maximum allowed

        Args:
            file_size: File size in bytes
            max_size_mb: Maximum allowed size in megabytes
            filename: Optional filename for error message

        Raises:
            FileSizeExceededError: If file size exceeds limit
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        if file_size > max_size_bytes:
            raise FileSizeExceededError(file_size, max_size_mb, filename)

    @staticmethod
    def bytes_to_mb(size_bytes: int) -> float:
        """Convert bytes to megabytes"""
        return round(size_bytes / (1024 * 1024), 2)


class SearchQueryValidator:
    """Validator for search queries"""

    MIN_QUERY_LENGTH = 1
    MAX_QUERY_LENGTH = 1000  # Reasonable limit

    # Patterns that might indicate injection attempts
    SUSPICIOUS_PATTERNS = [
        r"<script",  # XSS
        r"javascript:",  # XSS
        r"on\w+\s*=",  # Event handlers
        r"--",  # SQL comment
        r";\s*DROP",  # SQL injection
        r"UNION\s+SELECT",  # SQL injection
    ]

    @classmethod
    def validate_query(cls, query: str, strict: bool = False) -> str:
        """
        Validate search query

        Args:
            query: Search query string
            strict: If True, apply stricter validation

        Returns:
            Validated query

        Raises:
            EmptySearchQueryError: If query is empty
            InvalidSearchQueryError: If query is invalid
        """
        # Check empty
        if not query or not query.strip():
            raise EmptySearchQueryError()

        query = query.strip()

        # Check length
        if len(query) < cls.MIN_QUERY_LENGTH:
            raise InvalidSearchQueryError(
                query, f"Query too short (min {cls.MIN_QUERY_LENGTH} character)"
            )

        if len(query) > cls.MAX_QUERY_LENGTH:
            raise InvalidSearchQueryError(
                query, f"Query too long (max {cls.MAX_QUERY_LENGTH} characters)"
            )

        # Check for suspicious patterns if strict mode
        if strict:
            for pattern in cls.SUSPICIOUS_PATTERNS:
                if re.search(pattern, query, re.IGNORECASE):
                    raise InvalidSearchQueryError(
                        query, "Query contains suspicious patterns"
                    )

        return query

    @classmethod
    def sanitize_query(cls, query: str) -> str:
        """
        Sanitize search query by removing potentially dangerous content

        Args:
            query: Original query

        Returns:
            Sanitized query
        """
        if not query:
            return ""

        query = query.strip()

        # Remove HTML tags
        query = re.sub(r"<[^>]+>", "", query)

        # Remove SQL comment sequences
        query = query.replace("--", "")

        # Limit length
        if len(query) > cls.MAX_QUERY_LENGTH:
            query = query[: cls.MAX_QUERY_LENGTH]

        return query


class ConfigValidator:
    """Validator for configuration parameters"""

    @staticmethod
    def validate_positive_int(value: int, name: str, min_value: int = 0) -> int:
        """
        Validate positive integer value

        Args:
            value: Value to validate
            name: Parameter name for error message
            min_value: Minimum allowed value (default: 0)

        Returns:
            Validated value

        Raises:
            ValidationError: If value is invalid
        """
        if not isinstance(value, int):
            raise ValidationError(f"{name} must be an integer", field=name)

        if value < min_value:
            raise ValidationError(
                f"{name} must be >= {min_value}",
                field=name,
                details={"value": value, "min_value": min_value},
            )

        return value

    @staticmethod
    def validate_float_range(
        value: float, name: str, min_value: float, max_value: float
    ) -> float:
        """
        Validate float value within range

        Args:
            value: Value to validate
            name: Parameter name for error message
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            Validated value

        Raises:
            ValidationError: If value is out of range
        """
        if not isinstance(value, (int, float)):
            raise ValidationError(f"{name} must be a number", field=name)

        if value < min_value or value > max_value:
            raise ValidationError(
                f"{name} must be between {min_value} and {max_value}",
                field=name,
                details={"value": value, "min": min_value, "max": max_value},
            )

        return float(value)

    @staticmethod
    def validate_string_not_empty(value: str, name: str) -> str:
        """
        Validate string is not empty

        Args:
            value: Value to validate
            name: Parameter name for error message

        Returns:
            Validated value

        Raises:
            ValidationError: If string is empty
        """
        if not isinstance(value, str):
            raise ValidationError(f"{name} must be a string", field=name)

        if not value or not value.strip():
            raise ValidationError(f"{name} cannot be empty", field=name)

        return value.strip()


class MimeTypeValidator:
    """Validator for MIME types"""

    # Allowed MIME types for file uploads
    ALLOWED_MIME_TYPES = [
        # Text documents
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "text/xml",
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # Code files
        "application/json",
        "application/javascript",
        "application/xml",
        "application/x-yaml",
        # Archives (if needed)
        "application/zip",
        "application/x-tar",
        "application/gzip",
        # Other
        "application/octet-stream",  # Generic binary
    ]

    # MIME type aliases
    MIME_ALIASES = {
        "text/x-markdown": "text/markdown",
        "text/x-yaml": "application/x-yaml",
    }

    @classmethod
    def validate_mime_type(
        cls,
        mime_type: str,
        allow_all: bool = False,
        custom_allowed: Optional[List[str]] = None,
    ) -> bool:
        """
        Validate MIME type

        Args:
            mime_type: MIME type to validate
            allow_all: If True, allow all MIME types
            custom_allowed: Optional list of custom allowed MIME types

        Returns:
            True if valid, False otherwise
        """
        if allow_all:
            return True

        # Normalize MIME type
        mime_type = mime_type.lower().split(";")[0].strip()

        # Check aliases
        mime_type = cls.MIME_ALIASES.get(mime_type, mime_type)

        # Check custom list first
        if custom_allowed and mime_type in custom_allowed:
            return True

        # Check default allowed list
        return mime_type in cls.ALLOWED_MIME_TYPES

    @classmethod
    def get_allowed_types(cls) -> List[str]:
        """Get list of allowed MIME types"""
        return cls.ALLOWED_MIME_TYPES.copy()


class ImageValidator:
    """Validator for image MIME types"""

    ALLOWED_IMAGE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
        "image/bmp",
    ]

    @classmethod
    def validate_image_type(cls, mime_type: str) -> bool:
        """Return True if MIME type is an allowed image type."""
        if not mime_type:
            return False
        normalized = mime_type.lower().split(";")[0].strip()
        return normalized in cls.ALLOWED_IMAGE_TYPES


# Helper functions for common validation scenarios
def validate_upload_file(
    filename: str, file_size: int, mime_type: str, max_size_mb: int
) -> Tuple[str, bool]:
    """
    Validate file upload parameters

    Args:
        filename: Original filename
        file_size: File size in bytes
        mime_type: MIME type
        max_size_mb: Maximum size in MB

    Returns:
        Tuple of (sanitized_filename, mime_type_valid)

    Raises:
        InvalidFilenameError: If filename is invalid
        FileSizeExceededError: If file size exceeds limit
    """
    # Validate and sanitize filename
    validated_filename = FilenameValidator.validate_filename(filename)

    # Validate file size
    FileSizeValidator.validate_file_size(file_size, max_size_mb, filename)

    # Validate MIME type (non-blocking, returns boolean)
    mime_valid = MimeTypeValidator.validate_mime_type(mime_type, allow_all=True)

    return validated_filename, mime_valid


def validate_search_request(
    query: str, max_results: Optional[int] = None
) -> Tuple[str, int]:
    """
    Validate search request parameters

    Args:
        query: Search query
        max_results: Optional maximum results limit

    Returns:
        Tuple of (validated_query, validated_max_results)

    Raises:
        EmptySearchQueryError: If query is empty
        InvalidSearchQueryError: If query is invalid
        ValidationError: If max_results is invalid
    """
    # Validate query
    validated_query = SearchQueryValidator.validate_query(query)

    # Validate max_results
    if max_results is not None:
        validated_max_results = ConfigValidator.validate_positive_int(
            max_results, "max_results", min_value=1
        )
        # Apply reasonable upper limit
        if validated_max_results > 100:
            validated_max_results = 100
    else:
        validated_max_results = 5  # Default

    return validated_query, validated_max_results
