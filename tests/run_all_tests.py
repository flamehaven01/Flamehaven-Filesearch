#!/usr/bin/env python
"""
Flamehaven FileSearch - Master Test Suite
Pure unittest, no pytest dependency
Runs all tests across the entire codebase
"""

import sys
import os
import unittest
from pathlib import Path
import time

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def discover_tests(start_dir="tests", pattern="test_*.py"):
    """Discover all unittest test files."""
    loader = unittest.TestLoader()

    # Exclude pytest-specific files
    exclude = {
        "test_semantic_search.py",  # pytest-specific fixtures
        "test_minimal_import.py",  # Not a unittest file
        "test_quick_phase2.py",  # Custom runner
        "test_core_engines.py",  # Direct execution style
        "test_vector_quality.py",  # Direct execution style
        "test_performance_benchmark.py",  # Separate benchmark suite
    }

    suite = unittest.TestSuite()

    # Load unittest_suite (Phase 2)
    try:
        from tests.test_unittest_suite import suite as semantic_suite

        suite.addTests(semantic_suite())
        print(f"[+] Loaded: test_unittest_suite.py (19 tests)")
    except Exception as e:
        print(f"[!] Failed to load test_unittest_suite.py: {e}")

    # Load Gravitas-Pack cache integration (Phase 3)
    try:
        from tests.test_gravitas_cache_integration import (
            TestGravitasPackCacheIntegration,
        )

        phase3_tests = loader.loadTestsFromTestCase(TestGravitasPackCacheIntegration)
        suite.addTests(phase3_tests)
        print(
            f"[+] Loaded: test_gravitas_cache_integration.py ({phase3_tests.countTestCases()} tests)"
        )
    except Exception as e:
        print(f"[!] Failed to load test_gravitas_cache_integration.py: {e}")

    # Discover other unittest-compatible tests
    test_dir = Path(__file__).parent / start_dir

    for test_file in test_dir.glob(pattern):
        if test_file.name in exclude:
            continue

        # Try to load as unittest module
        try:
            module_name = f"tests.{test_file.stem}"
            module = __import__(module_name, fromlist=[""])

            tests = loader.loadTestsFromModule(module)
            if tests.countTestCases() > 0:
                suite.addTests(tests)
                print(f"[+] Loaded: {test_file.name} ({tests.countTestCases()} tests)")
        except Exception as e:
            print(f"[!] Skipped {test_file.name}: {e}")

    return suite


class FlamehavenTestResult(unittest.TextTestResult):
    """Enhanced test result with timing and categorization."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_times = []
        self.current_test_start = None

    def startTest(self, test):
        super().startTest(test)
        self.current_test_start = time.time()

    def addSuccess(self, test):
        super().addSuccess(test)
        elapsed = time.time() - self.current_test_start
        self.test_times.append((str(test), elapsed, "PASS"))

    def addError(self, test, err):
        super().addError(test, err)
        elapsed = time.time() - self.current_test_start
        self.test_times.append((str(test), elapsed, "ERROR"))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        elapsed = time.time() - self.current_test_start
        self.test_times.append((str(test), elapsed, "FAIL"))


class FlamehavenTestRunner(unittest.TextTestRunner):
    """Custom test runner with enhanced reporting."""

    resultclass = FlamehavenTestResult

    def run(self, test):
        """Run tests with enhanced reporting."""
        print(
            """
================================================================================
                                                                               
   FLAMEHAVEN FILESEARCH - MASTER TEST SUITE                                  
   unittest Edition - Zero pytest dependency                                  
                                                                               
================================================================================
"""
        )

        start_time = time.time()
        result = super().run(test)
        total_time = time.time() - start_time

        # Print timing summary
        if hasattr(result, "test_times") and result.test_times:
            print("\n" + "=" * 80)
            print("TIMING SUMMARY (slowest tests)")
            print("=" * 80)

            sorted_times = sorted(result.test_times, key=lambda x: x[1], reverse=True)
            for test_name, elapsed, status in sorted_times[:10]:
                print(f"  [{status:5}] {elapsed:6.3f}s - {test_name}")

        # Print final summary
        print("\n" + "=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"Tests run: {result.testsRun}")
        print(
            f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}"
        )
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Total time: {total_time:.2f}s")

        if result.wasSuccessful():
            print("\n[+] ALL TESTS PASSED")
        else:
            print(f"\n[-] {len(result.failures) + len(result.errors)} TEST(S) FAILED")

        return result


def main(verbosity=2):
    """Run all tests."""

    # Set environment for offline testing
    os.environ["GOOGLE_API_KEY"] = "test-bypass-key"

    # Discover tests
    print("Discovering tests...\n")
    suite = discover_tests()

    total_tests = suite.countTestCases()
    print(f"\nTotal tests discovered: {total_tests}\n")

    if total_tests == 0:
        print("No tests found!")
        return 1

    # Run tests
    runner = FlamehavenTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Flamehaven Test Suite")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet output")

    args = parser.parse_args()

    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1

    sys.exit(main(verbosity))
