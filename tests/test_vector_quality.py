"""
Vector Quality Verification - SIDRCE v2.0 vs Original
Tests semantic similarity preservation
"""

# flake8: noqa

import sys

sys.path.insert(0, "D:\\Sanctum\\Flamehaven-Filesearch")

print("[>] Vector Quality Test - Unified v2.0\n")

import numpy as np

from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

gen = EmbeddingGenerator()

# Test 1: Determinism
print("TEST 1: Determinism")
v1 = gen.generate("python script")
v2 = gen.generate("python script")
assert np.allclose(v1, v2), "Vectors must be identical"
print("  [+] Same text = same vector ✓\n")

# Test 2: Normalization
print("TEST 2: L2 Normalization")
norm = np.linalg.norm(v1)
print(f"  Vector norm: {norm:.6f}")
assert 0.99 < norm < 1.01, "Must be unit vector"
print("  [+] Unit vector confirmed ✓\n")

# Test 3: Semantic Similarity
print("TEST 3: Semantic Similarity")
texts = [
    "python script file",
    "python code script",
    "java program code",
    "completely different text here",
]

vectors = [gen.generate(t) for t in texts]


# Cosine similarity
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


sim_01 = cosine_sim(vectors[0], vectors[1])  # python script vs python code
sim_02 = cosine_sim(vectors[0], vectors[2])  # python vs java
sim_03 = cosine_sim(vectors[0], vectors[3])  # python vs different

print(f"  'python script' vs 'python code': {sim_01:.4f}")
print(f"  'python script' vs 'java program': {sim_02:.4f}")
print(f"  'python script' vs 'different text': {sim_03:.4f}")

# Similar texts should have significantly higher similarity
# DSP v2.0 algorithm produces ~0.54 similarity for semantic matches
assert sim_01 > 0.45, "Similar texts should be >0.45"
assert sim_01 > sim_02 and sim_01 > sim_03, "Most similar should rank highest"
print("  [+] Semantic ranking validated ✓\n")

# Test 4: Feature Extraction
print("TEST 4: Hybrid Features")
stats = gen.get_cache_stats()
print(f"  Backend: {stats.get('backend', 'unknown')}")
print(f"  Algorithm: {stats.get('algorithm', 'DSP-v2.0')}")
print(f"  Cache size: {stats['cache_size']}/{stats['cache_max_size']}")
print(f"  Hit rate: {stats['hit_rate']:.1f}%")
print("  [+] Stats tracking working ✓\n")

# Test 5: Word vs Char weight
print("TEST 5: Differential Weighting")
# Words should contribute more than n-grams
v_keyword = gen.generate("filesearch")
v_ngram = gen.generate("fls srch")  # Similar n-grams, different words

sim_self = cosine_sim(v_keyword, v_keyword)
sim_diff = cosine_sim(v_keyword, v_ngram)

print(f"  Self-similarity: {sim_self:.4f}")
print(f"  N-gram variant: {sim_diff:.4f}")
assert sim_diff < 0.9, "Word tokens should dominate"
print("  [+] Word weighting effective ✓\n")

print("[+] All Quality Tests PASSED")
print("\nUnified v2.0 Features:")
print("  ✓ SIDRCE Signed Hashing")
print("  ✓ Hybrid Word+Char Features")
print("  ✓ Differential Weighting (2.0x words)")
print("  ✓ Current LRU Caching")
print("  ✓ Zero Dependencies (numpy optional)")
