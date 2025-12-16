"""
Test Gravitas-Pack Integration in FileMetadataCache
Verifies Phase 3: Symbolic Compression in cache layer
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flamehaven_filesearch.cache import FileMetadataCache


class TestGravitasPackCacheIntegration(unittest.TestCase):
    """Test GravitasPacker integration in FileMetadataCache"""

    def setUp(self):
        """Set up fresh cache for each test"""
        self.cache = FileMetadataCache(maxsize=100)

    def test_compression_roundtrip(self):
        """Metadata survives compression-decompression roundtrip"""
        metadata = {
            "file_path": "D:\\Sanctum\\test\\example.py",
            "file_name": "example.py",
            "file_type": ".py",
            "size_bytes": 2048,
            "created_at": "2025-12-15T10:00:00Z",
            "modified_at": "2025-12-15T10:30:00Z",
            "lines_of_code": 50,
            "is_binary": False,
            "encoding": "utf-8",
            "tags": ["python", "test"],
        }

        # Set and get
        self.cache.set("test.py", metadata)
        retrieved = self.cache.get("test.py")

        # Verify data integrity
        self.assertEqual(retrieved, metadata)

    def test_compression_actually_compresses(self):
        """Compression reduces memory usage"""
        metadata = {
            "file_path": "D:\\Sanctum\\very\\long\\path\\to\\deeply\\nested\\directory\\file.py",
            "file_name": "file.py",
            "file_type": ".py",
            "size_bytes": 999999,
            "created_at": "2025-12-15T10:00:00Z",
            "modified_at": "2025-12-15T10:30:00Z",
            "accessed_at": "2025-12-15T11:00:00Z",
        }

        # Store metadata
        self.cache.set("test_file.py", metadata)

        # Get stats
        stats = self.cache.get_stats()

        # Verify compression happened
        self.assertGreater(stats["total_compressed"], 0)
        self.assertGreater(stats["bytes_saved"], 0)

        print(f"\n  Compression stats: {stats['bytes_saved']} bytes saved")

    def test_multiple_files_compression(self):
        """Compression works across multiple files"""
        files = [
            ("file1.py", {"file_path": "D:\\Sanctum\\file1.py", "size_bytes": 1024}),
            ("file2.pdf", {"file_path": "D:\\Sanctum\\file2.pdf", "size_bytes": 2048}),
            (
                "file3.docx",
                {"file_path": "D:\\Sanctum\\file3.docx", "size_bytes": 4096},
            ),
        ]

        # Store all files
        for filename, meta in files:
            self.cache.set(filename, meta)

        # Retrieve and verify all
        for filename, original_meta in files:
            retrieved = self.cache.get(filename)
            self.assertEqual(retrieved, original_meta)

        # Check compression happened
        stats = self.cache.get_stats()
        self.assertEqual(stats["total_compressed"], 3)
        self.assertEqual(stats["total_decompressed"], 3)

    def test_compression_can_be_disabled(self):
        """Compression can be toggled off"""
        metadata = {"file_path": "test.py", "size": 100}

        # Disable compression
        self.cache.enable_compression(False)
        self.cache.set("test.py", metadata)

        stats = self.cache.get_stats()
        self.assertFalse(stats["compression_enabled"])

        # Re-enable
        self.cache.enable_compression(True)
        self.assertTrue(self.cache.compression_enabled)

    def test_cache_invalidation_resets_stats(self):
        """Invalidating cache resets compression stats"""
        self.cache.set("file1.py", {"size": 100})
        self.cache.set("file2.py", {"size": 200})

        # Clear cache
        self.cache.invalidate()

        stats = self.cache.get_stats()
        self.assertEqual(stats["current_size"], 0)
        self.assertEqual(stats["total_compressed"], 0)

    def test_compression_ratio_calculation(self):
        """Compression ratio is calculated correctly"""
        large_metadata = {
            "file_path": "D:\\" + "very\\" * 20 + "deep\\path.py",
            "file_name": "path.py",
            "file_type": ".py",
            "size_bytes": 123456,
            "created_at": "2025-12-15T10:00:00Z",
            "modified_at": "2025-12-15T10:30:00Z",
            "accessed_at": "2025-12-15T11:00:00Z",
            "lines_of_code": 500,
            "is_binary": False,
            "encoding": "utf-8",
        }

        self.cache.set("large_file.py", large_metadata)
        retrieved = self.cache.get("large_file.py")

        # Verify data integrity
        self.assertEqual(retrieved, large_metadata)

        # Check compression achieved savings
        stats = self.cache.get_stats()
        self.assertGreater(stats["bytes_saved"], 0)
        self.assertGreater(stats["average_compression_ratio"], 0)

        print(f"\n  Average compression: {stats['average_compression_ratio']*100:.1f}%")

    def test_missing_file_returns_none(self):
        """Getting non-existent file returns None"""
        result = self.cache.get("nonexistent.py")
        self.assertIsNone(result)

    def test_partial_invalidation(self):
        """Can invalidate single file"""
        self.cache.set("file1.py", {"size": 100})
        self.cache.set("file2.py", {"size": 200})

        # Invalidate one file
        self.cache.invalidate("file1.py")

        self.assertIsNone(self.cache.get("file1.py"))
        self.assertIsNotNone(self.cache.get("file2.py"))


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 3: GRAVITAS-PACK CACHE INTEGRATION TEST")
    print("=" * 80)

    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromTestCase(
        TestGravitasPackCacheIntegration
    )
    result = runner.run(suite)

    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("[+] ALL TESTS PASSED - Phase 3 Integration Complete")
    else:
        print(f"[-] {len(result.failures) + len(result.errors)} TEST(S) FAILED")
    print("=" * 80)

    sys.exit(0 if result.wasSuccessful() else 1)
