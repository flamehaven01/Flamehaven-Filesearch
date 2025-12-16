#!/usr/bin/env python
"""
Phase 3.5: Vector Quantization Test Suite
Tests memory efficiency and accuracy preservation
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from flamehaven_filesearch.engine.chronos_grid import ChronosGrid, ChronosConfig


@unittest.skipUnless(NUMPY_AVAILABLE, "NumPy required for quantization")
class TestVectorQuantization(unittest.TestCase):
    """Test Vector Quantization feature"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.config_quantized = ChronosConfig(enable_vector_quantization=True)
        self.config_unquantized = ChronosConfig(enable_vector_quantization=False)
        
    def test_quantization_enabled(self):
        """Test that quantization can be enabled"""
        grid = ChronosGrid(self.config_quantized)
        self.assertTrue(grid.config.enable_vector_quantization)
        
    def test_quantization_disabled(self):
        """Test that quantization can be disabled"""
        grid = ChronosGrid(self.config_unquantized)
        self.assertFalse(grid.config.enable_vector_quantization)
        
    def test_vector_storage_quantized(self):
        """Test that vectors are stored as int8 when quantized"""
        grid = ChronosGrid(self.config_quantized)
        
        # Create test vector
        test_vector = np.random.randn(384).astype(np.float32)
        test_vector /= np.linalg.norm(test_vector)  # Normalize
        
        # Inject
        grid.inject_essence('test_file.py', {'path': 'test_file.py'}, test_vector)
        
        # Check storage
        stored_vector = grid._vector_essences[0]
        self.assertEqual(stored_vector.dtype, np.int8, "Vector should be stored as int8")
        self.assertEqual(stored_vector.shape, (384,), "Vector dimension should be preserved")
        
    def test_vector_storage_unquantized(self):
        """Test that vectors are stored as float32 when not quantized"""
        grid = ChronosGrid(self.config_unquantized)
        
        # Create test vector
        test_vector = np.random.randn(384).astype(np.float32)
        test_vector /= np.linalg.norm(test_vector)
        
        # Inject
        grid.inject_essence('test_file.py', {'path': 'test_file.py'}, test_vector)
        
        # Check storage
        stored_vector = grid._vector_essences[0]
        self.assertEqual(stored_vector.dtype, np.float32, "Vector should be stored as float32")
        
    def test_memory_reduction(self):
        """Test that quantization reduces memory usage by ~75%"""
        # Quantized grid
        grid_q = ChronosGrid(self.config_quantized)
        
        # Unquantized grid
        grid_uq = ChronosGrid(self.config_unquantized)
        
        # Add 100 vectors
        for i in range(100):
            vec = np.random.randn(384).astype(np.float32)
            vec /= np.linalg.norm(vec)
            grid_q.inject_essence(f'file_{i}.py', {'id': i}, vec)
            grid_uq.inject_essence(f'file_{i}.py', {'id': i}, vec)
        
        # Calculate memory usage
        mem_q = sum(v.nbytes for v in grid_q._vector_essences)
        mem_uq = sum(v.nbytes for v in grid_uq._vector_essences)
        
        reduction_ratio = 1 - (mem_q / mem_uq)
        
        print(f"\n[*] Memory Reduction Test:")
        print(f"    Unquantized: {mem_uq} bytes")
        print(f"    Quantized:   {mem_q} bytes")
        print(f"    Reduction:   {reduction_ratio*100:.1f}%")
        
        self.assertGreater(reduction_ratio, 0.70, "Should reduce memory by at least 70%")
        self.assertLess(reduction_ratio, 0.80, "Reduction should be close to 75%")
        
    def test_search_accuracy_preservation(self):
        """Test that quantization preserves search accuracy"""
        # Setup both grids
        grid_q = ChronosGrid(self.config_quantized)
        grid_uq = ChronosGrid(self.config_unquantized)
        
        # Add identical data to both
        vectors = []
        for i in range(50):
            vec = np.random.randn(384).astype(np.float32)
            vec /= np.linalg.norm(vec)
            vectors.append(vec)
            grid_q.inject_essence(f'file_{i}.py', {'id': i, 'path': f'file_{i}.py'}, vec)
            grid_uq.inject_essence(f'file_{i}.py', {'id': i, 'path': f'file_{i}.py'}, vec)
        
        # Search with same query
        query = np.random.randn(384).astype(np.float32)
        query /= np.linalg.norm(query)
        
        results_q = grid_q.seek_vector_resonance(query, top_k_resonances=5)
        results_uq = grid_uq.seek_vector_resonance(query, top_k_resonances=5)
        
        # Extract IDs
        ids_q = [r[0]['id'] for r in results_q]
        ids_uq = [r[0]['id'] for r in results_uq]
        
        # Calculate overlap (how many results are the same)
        overlap = len(set(ids_q) & set(ids_uq))
        accuracy = overlap / 5.0
        
        print(f"\n[*] Search Accuracy Test:")
        print(f"    Quantized results:   {ids_q}")
        print(f"    Unquantized results: {ids_uq}")
        print(f"    Overlap: {overlap}/5 ({accuracy*100:.0f}%)")
        
        self.assertGreaterEqual(accuracy, 0.6, "At least 60% of results should match")
        
    def test_deterministic_quantization(self):
        """Test that quantization is deterministic"""
        grid1 = ChronosGrid(self.config_quantized)
        grid2 = ChronosGrid(self.config_quantized)
        
        test_vector = np.array([0.1] * 384, dtype=np.float32)
        
        q1 = grid1._quantize_vector(test_vector)
        q2 = grid2._quantize_vector(test_vector)
        
        np.testing.assert_array_equal(q1, q2, "Quantization should be deterministic")
        
    def test_roundtrip_accuracy(self):
        """Test quantize -> dequantize accuracy"""
        grid = ChronosGrid(self.config_quantized)
        
        original = np.random.randn(384).astype(np.float32)
        original /= np.linalg.norm(original)
        
        quantized = grid._quantize_vector(original)
        restored = grid._dequantize_vector(quantized)
        
        # Calculate relative error
        mse = np.mean((original - restored) ** 2)
        
        print(f"\n[*] Roundtrip Accuracy:")
        print(f"    MSE: {mse:.6f}")
        
        self.assertLess(mse, 0.01, "Quantization error should be minimal")


def suite():
    """Create test suite"""
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestVectorQuantization))
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())
    sys.exit(0 if result.wasSuccessful() else 1)
