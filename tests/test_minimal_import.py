"""
Minimal import test - No dependencies, just syntax verification
"""

import sys
import os

# Add to path
sys.path.insert(0, "D:\\Sanctum\\Flamehaven-Filesearch")

print("[1/6] Testing embedding_generator import...")
try:
    from flamehaven_filesearch.engine import embedding_generator

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("[2/6] Testing chronos_grid import...")
try:
    from flamehaven_filesearch.engine import chronos_grid

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("[3/6] Testing intent_refiner import...")
try:
    from flamehaven_filesearch.engine import intent_refiner

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("[4/6] Testing gravitas_pack import...")
try:
    from flamehaven_filesearch.engine import gravitas_pack

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("[5/6] Testing config import...")
try:
    os.environ["GOOGLE_API_KEY"] = "test-key-bypass"
    from flamehaven_filesearch import config

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("[6/6] Testing api import...")
try:
    from flamehaven_filesearch import api

    print("  [+] PASS")
except Exception as e:
    print(f"  [-] FAIL: {e}")

print("\n[+] Import test complete")
