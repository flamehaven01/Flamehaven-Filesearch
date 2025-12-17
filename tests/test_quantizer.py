"""
Unit tests for Vector Quantizer (Phase 3.5)
"""

# flake8: noqa

import sys
import unittest
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flamehaven_filesearch.quantizer import VectorQuantizer, get_quantizer

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class TestVectorQuantizer(unittest.TestCase):
    """Test vector quantization and dequantization"""

    def setUp(self):
        self.quantizer = VectorQuantizer()

    def test_quantize_dequantize_numpy(self):
        """Test quantization round-trip with NumPy"""
        if not NUMPY_AVAILABLE:
            self.skipTest("NumPy not available")

        # Create test vector
        original = np.random.randn(384).astype(np.float32)
        original /= np.linalg.norm(original)  # L2 normalize

        # Quantize
        quantized = self.quantizer.quantize(original)
        self.assertEqual(len(quantized), 384 + 8)  # 384 bytes + 8 metadata

        # Dequantize
        restored = self.quantizer.dequantize(quantized)

        # Check similarity (should be >99%)
        similarity = np.dot(original, restored) / (np.linalg.norm(restored))
        self.assertGreater(similarity, 0.99)

    def test_quantize_dequantize_pure_python(self):
        """Test quantization with pure Python fallback"""
        original = [float(i) / 384 for i in range(384)]

        # Normalize
        norm = sum(x * x for x in original) ** 0.5
        original = [x / norm for x in original]

        # Quantize
        quantized = self.quantizer.quantize(original)
        self.assertEqual(len(quantized), 384 + 8)

        # Dequantize
        restored = self.quantizer.dequantize(quantized)

        # Check reconstruction
        self.assertEqual(len(restored), 384)

    def test_quantized_cosine_similarity(self):
        """Test direct similarity calculation on quantized vectors"""
        vec1 = [1.0] * 384
        vec2 = [0.5] * 384

        q1 = self.quantizer.quantize(vec1)
        q2 = self.quantizer.quantize(vec2)

        similarity = self.quantizer.quantized_cosine_similarity(q1, q2)

        # Should be close to 1.0 (very similar)
        self.assertGreater(similarity, 0.95)

    def test_memory_reduction(self):
        """Verify memory savings (75% reduction)"""
        if not NUMPY_AVAILABLE:
            self.skipTest("NumPy not available")

        original = np.random.randn(384).astype(np.float32)
        quantized = self.quantizer.quantize(original)

        original_size = original.nbytes  # 384 * 4 = 1536 bytes
        quantized_size = len(quantized)  # 384 + 8 = 392 bytes

        reduction = 1 - (quantized_size / original_size)
        self.assertGreater(reduction, 0.74)  # At least 74% reduction

    def test_singleton(self):
        """Test singleton pattern"""
        q1 = get_quantizer()
        q2 = get_quantizer()
        self.assertIs(q1, q2)

    def test_stats(self):
        """Test statistics tracking"""
        vec = [1.0] * 384
        q = self.quantizer.quantize(vec)
        _ = self.quantizer.dequantize(q)

        stats = self.quantizer.get_stats()
        self.assertEqual(stats["quantized"], 1)
        self.assertEqual(stats["dequantized"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
