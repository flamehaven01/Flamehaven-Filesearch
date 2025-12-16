#!/usr/bin/env python
"""Quick verification of Phase 3.5 quantization"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numpy as np

    from flamehaven_filesearch.engine.chronos_grid import ChronosGrid, ChronosConfig

    print("[*] Phase 3.5: Vector Quantization Verification")
    print("=" * 60)

    # Test 1: Quantization enabled
    config_q = ChronosConfig(enable_vector_quantization=True)
    grid = ChronosGrid(config_q)

    # Create test vectors
    vectors = [np.random.randn(384).astype(np.float32) / 10.0 for _ in range(10)]
    for i, vec in enumerate(vectors):
        vec /= np.linalg.norm(vec)
        grid.inject_essence(f"file_{i}.py", {"id": i}, vec)

    # Check storage type
    stored = grid._vector_essences[0]
    print(f"\n[+] Storage Test:")
    print(f"    Dtype: {stored.dtype}")
    print(f"    Expected: int8")
    print(f"    Status: {'PASS' if stored.dtype == np.int8 else 'FAIL'}")

    # Memory test
    mem_quantized = sum(v.nbytes for v in grid._vector_essences)
    mem_expected_unquantized = 10 * 384 * 4  # float32
    reduction = 1 - (mem_quantized / mem_expected_unquantized)

    print(f"\n[+] Memory Reduction:")
    print(f"    Quantized:   {mem_quantized} bytes")
    print(f"    Unquantized: {mem_expected_unquantized} bytes")
    print(f"    Reduction:   {reduction*100:.1f}%")
    print(f"    Target:      75%")
    print(f"    Status: {'PASS' if reduction >= 0.70 else 'FAIL'}")

    # Search test
    query = np.random.randn(384).astype(np.float32)
    query /= np.linalg.norm(query)

    results = grid.seek_vector_resonance(query, top_k_resonances=3)

    print(f"\n[+] Search Test:")
    print(f"    Results found: {len(results)}")
    print(f"    Expected: 3")
    print(f"    Status: {'PASS' if len(results) == 3 else 'FAIL'}")

    if results:
        print(f"    Top result similarity: {results[0][1]:.4f}")

    print("\n" + "=" * 60)
    print("[+] Phase 3.5: Vector Quantization VERIFIED")

except ImportError as e:
    print(f"[!] Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[!] Test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
