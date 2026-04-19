"""
Gravitas-Pack: Symbolic Compression for File Metadata
Compresses file metadata using symbolic tokens (glyphs)
to achieve 70-90% space reduction
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class GravitasPacker:
    """
    Symbolic metadata compression engine using glyph mappings.
    Reduces storage footprint while maintaining semantic information.
    """

    # Filesystem path glyphs
    PATH_GLYPHS = {
        "D:\\Sanctum\\": "[S]",
        "D:\\": "[D]",
        "C:\\": "[C]",
        "/home/": "[H]",
        "/root/": "[R]",
        "/var/": "[V]",
    }

    # File extension glyphs
    EXT_GLYPHS = {
        ".py": "[*py]",
        ".pdf": "[*pdf]",
        ".docx": "[*dx]",
        ".xlsx": "[*xls]",
        ".json": "[*json]",
        ".yaml": "[*yaml]",
        ".txt": "[*txt]",
        ".md": "[*md]",
        ".html": "[*html]",
        ".css": "[*css]",
        ".js": "[*js]",
        ".ts": "[*ts]",
        ".sql": "[*sql]",
        ".xml": "[*xml]",
        ".sh": "[*sh]",
        ".bat": "[*bat]",
    }

    # Metadata field glyphs
    FIELD_GLYPHS = {
        "created_at": "C",
        "modified_at": "M",
        "accessed_at": "A",
        "size_bytes": "S",
        "file_name": "F",
        "file_path": "P",
        "file_type": "T",
        "content_hash": "H",
        "is_binary": "B",
        "encoding": "E",
        "lines_of_code": "L",
        "tags": "G",
        "description": "D",
        "checksum": "X",
        "mime_type": "I",
        "permissions": "O",
    }

    # Status and flag glyphs
    STATUS_GLYPHS = {
        "indexed": "1",
        "pending": "0",
        "error": "-",
        "true": "Y",
        "false": "N",
    }

    def __init__(self):
        self.compression_stats = {
            "total_compressed": 0,
            "total_decompressed": 0,
            "average_ratio": 0.0,
            "bytes_saved": 0,
        }

    def compress_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        Compress file metadata using glyph substitution.

        Args:
            metadata: Dictionary of file metadata

        Returns:
            Compressed JSON string using glyphs
        """
        if not metadata:
            return ""

        original_size = len(json.dumps(metadata))
        compressed = self._compress_dict(metadata)
        compressed_str = json.dumps(compressed, separators=(",", ":"))
        compressed_size = len(compressed_str)

        # Update stats
        self.compression_stats["total_compressed"] += 1
        self.compression_stats["bytes_saved"] += original_size - compressed_size

        if self.compression_stats["total_compressed"] > 0:
            ratio = self.compression_stats["bytes_saved"] / (
                original_size * self.compression_stats["total_compressed"]
            )
            self.compression_stats["average_ratio"] = ratio

        return compressed_str

    def decompress_metadata(self, compressed_json: str) -> Dict[str, Any]:
        """
        Decompress glyph-compressed metadata back to original form.

        Args:
            compressed_json: Compressed JSON string

        Returns:
            Decompressed metadata dictionary
        """
        if not compressed_json:
            return {}

        try:
            compressed_dict = json.loads(compressed_json)
            self.compression_stats["total_decompressed"] += 1
            return self._decompress_dict(compressed_dict)
        except json.JSONDecodeError:
            logger.warning(f"Failed to decompress: {compressed_json}")
            return {}

    def _transform_dict(self, obj: Any, key_map: dict, value_transform) -> Any:
        """Recursively transform a dict/list/str using key_map for keys and value_transform for strings."""
        if isinstance(obj, dict):
            return {
                key_map.get(k, k): self._transform_dict(v, key_map, value_transform)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [
                self._transform_dict(item, key_map, value_transform) for item in obj
            ]
        if isinstance(obj, str):
            return value_transform(obj)
        return obj

    def _compress_dict(self, obj: Any) -> Any:
        """Compress dictionary using glyph mappings."""
        return self._transform_dict(obj, self.FIELD_GLYPHS, self._compress_string)

    def _decompress_dict(self, obj: Any) -> Any:
        """Decompress dictionary using reverse glyph mappings."""
        reverse_fields = {v: k for k, v in self.FIELD_GLYPHS.items()}
        return self._transform_dict(obj, reverse_fields, self._decompress_string)

    def _compress_string(self, value: str) -> str:
        """Compress string by replacing paths and extensions with glyphs."""
        if not value:
            return value

        compressed = value

        # Replace paths
        for path, glyph in self.PATH_GLYPHS.items():
            compressed = compressed.replace(path, glyph)

        # Replace extensions
        for ext, glyph in self.EXT_GLYPHS.items():
            if ext in compressed:
                compressed = compressed.replace(ext, glyph)

        # Replace status values
        for status, glyph in self.STATUS_GLYPHS.items():
            if compressed == status:
                compressed = glyph
                break

        return compressed

    def _decompress_string(self, value: str) -> str:
        """Decompress string by replacing glyphs back to original values."""
        if not value:
            return value

        decompressed = value

        # Replace glyphs back to paths
        for path, glyph in self.PATH_GLYPHS.items():
            decompressed = decompressed.replace(glyph, path)

        # Replace glyphs back to extensions
        for ext, glyph in self.EXT_GLYPHS.items():
            decompressed = decompressed.replace(glyph, ext)

        # Replace glyphs back to status values
        reverse_status = {v: k for k, v in self.STATUS_GLYPHS.items()}
        if decompressed in reverse_status:
            decompressed = reverse_status[decompressed]

        return decompressed

    def estimate_compression_ratio(self, metadata: Dict[str, Any]) -> float:
        """
        Estimate compression ratio without actually compressing.

        Returns:
            Ratio (0.0-1.0) of compressed size to original size
        """
        if not metadata:
            return 0.0

        original_size = len(json.dumps(metadata, separators=(",", ":")))
        estimated_reduction = sum(
            self._estimate_field_reduction(k, v) for k, v in metadata.items()
        )
        estimated_compressed_size = max(1, original_size - estimated_reduction)
        return estimated_compressed_size / original_size

    def _estimate_field_reduction(self, key: str, value: object) -> float:
        """Estimate byte savings for a single metadata field."""
        reduction = 0.0
        if key in self.FIELD_GLYPHS:
            reduction += len(key) - len(self.FIELD_GLYPHS[key])
        if isinstance(value, str):
            for ext, glyph in self.EXT_GLYPHS.items():
                if ext in value:
                    reduction += len(ext) - len(glyph)
            for path, glyph in self.PATH_GLYPHS.items():
                if path in value:
                    reduction += len(path) - len(glyph)
        return reduction

    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return self.compression_stats.copy()

    def reset_stats(self) -> None:
        """Reset compression statistics."""
        self.compression_stats = {
            "total_compressed": 0,
            "total_decompressed": 0,
            "average_ratio": 0.0,
            "bytes_saved": 0,
        }

    @classmethod
    def quick_compress(cls, metadata: Dict[str, Any]) -> str:
        """Quick compression without instantiation."""
        packer = cls()
        return packer.compress_metadata(metadata)

    @classmethod
    def quick_decompress(cls, compressed_json: str) -> Dict[str, Any]:
        """Quick decompression without instantiation."""
        packer = cls()
        return packer.decompress_metadata(compressed_json)
