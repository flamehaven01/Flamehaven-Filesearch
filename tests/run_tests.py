#!/usr/bin/env python
"""
Flamehaven Test Runner - pytest Alternative
Pure Python test execution without heavy dependencies
"""

import sys
import os
import time
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_test_file(filepath):
    """Run a single test file and return results."""
    print(f"\n{'='*80}")
    print(f"Running: {filepath}")
    print('='*80)
    
    start = time.time()
    
    try:
        # Execute test file
        with open(filepath) as f:
            code = compile(f.read(), filepath, 'exec')
            exec(code, {'__name__': '__main__'})
        
        elapsed = time.time() - start
        print(f"\n[+] PASSED in {elapsed:.2f}s")
        return True, elapsed
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n[-] FAILED in {elapsed:.2f}s")
        print(f"Error: {e}")
        return False, elapsed


def main():
    """Run all Flamehaven tests."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   FLAMEHAVEN TEST RUNNER v1.0                                                ║
║   Pure Python - No pytest, No timeout, No bloat                              ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")
    
    test_dir = Path(__file__).parent
    
    # Test files to run (in order)
    test_files = [
        'test_core_engines.py',
        'test_vector_quality.py',
        'test_quick_phase2.py',
    ]
    
    results = []
    total_time = 0
    
    for test_file in test_files:
        filepath = test_dir / test_file
        if filepath.exists():
            passed, elapsed = run_test_file(str(filepath))
            results.append((test_file, passed, elapsed))
            total_time += elapsed
        else:
            print(f"\n[!] Skipped: {test_file} (not found)")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    
    for name, passed, elapsed in results:
        status = "[+] PASS" if passed else "[-] FAIL"
        print(f"{status} {name:40} ({elapsed:.2f}s)")
    
    print(f"\n{passed_count}/{total_count} test files passed")
    print(f"Total time: {total_time:.2f}s")
    
    if passed_count == total_count:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
