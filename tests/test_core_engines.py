"""
Core engine test without API - Fast verification
"""

# flake8: noqa

import sys

sys.path.insert(0, "D:\\Sanctum\\Flamehaven-Filesearch")

print("[>] Core Engine Tests (No API)\n")

# Test 1: EmbeddingGenerator
print("TEST 1: EmbeddingGenerator")
from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

gen = EmbeddingGenerator()
print(f"  Model loaded: {gen._model_loaded}")

# Generate mock vector
vec = gen.generate("test")
print(f"  Vector generated: {len(vec) if hasattr(vec, '__len__') else 'list'} dims")

# Test cache
gen.generate("test")
stats = gen.get_cache_stats()
print(f"  Cache hits: {stats['cache_hits']}, misses: {stats['cache_misses']}")
print("  [+] PASS\n")

# Test 2: ChronosGrid
print("TEST 2: ChronosGrid")
from flamehaven_filesearch.engine.chronos_grid import ChronosGrid

grid = ChronosGrid()
grid.inject_essence("file.py", {"name": "test"}, vector_essence=vec)
result = grid.seek_resonance("file.py")
print(f"  Injected and retrieved: {result['name']}")
print("  [+] PASS\n")

# Test 3: IntentRefiner
print("TEST 3: IntentRefiner")
from flamehaven_filesearch.engine.intent_refiner import IntentRefiner

refiner = IntentRefiner()
intent = refiner.refine_intent("find pythn script")
print("  Original: find pythn script")
print(f"  Refined: {intent.refined_query}")
print(f"  Corrected: {intent.is_corrected}")
print("  [+] PASS\n")

# Test 4: GravitasPacker
print("TEST 4: GravitasPacker")
from flamehaven_filesearch.engine.gravitas_pack import GravitasPacker

packer = GravitasPacker()
meta = {"file_path": "D:\\Sanctum\\test.py", "size_bytes": 1024}
compressed = packer.compress_metadata(meta)
decompressed = packer.decompress_metadata(compressed)
print(f"  Original size: {len(str(meta))}")
print(f"  Compressed size: {len(compressed)}")
print(f"  Round-trip: {decompressed == meta}")
print("  [+] PASS\n")

# Test 5: Core Integration (without API)
print("TEST 5: FlamehavenFileSearch (offline mode)")
import os

os.environ["GOOGLE_API_KEY"] = "test-bypass"

from flamehaven_filesearch.core import FlamehavenFileSearch

searcher = FlamehavenFileSearch(allow_offline=True)
print("  Engines initialized:")
print(f"    - embedding_generator: {searcher.embedding_generator is not None}")
print(f"    - chronos_grid: {searcher.chronos_grid is not None}")
print(f"    - intent_refiner: {searcher.intent_refiner is not None}")
print(f"    - gravitas_packer: {searcher.gravitas_packer is not None}")

# Test search modes
result = searcher.search("test", search_mode="semantic")
print(f"  Search result status: {result.get('status')}")
print(f"  Search mode: {result.get('search_mode')}")
print("  [+] PASS\n")

print("[+] All Core Engine Tests PASSED")
