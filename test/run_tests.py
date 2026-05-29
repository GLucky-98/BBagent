#!/usr/bin/env python3
"""
Test runner for BBagent.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py unit          # Run unit tests only
    python run_tests.py integration   # Run integration tests only
    python run_tests.py builtin       # Run builtin tool/hook tests only
    python run_tests.py test_<name>   # Run specific test module
"""
import sys
import subprocess
from pathlib import Path

TEST_DIR = Path(__file__).parent

def run_python_script(script_path):
    """Run a Python test script and return success status."""
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=False
    )
    return result.returncode == 0

def run_unit_tests():
    """Run all unit tests."""
    print("=" * 60)
    print("Running UNIT tests...")
    print("=" * 60)
    unit_dir = TEST_DIR / "unit"
    passed = 0
    failed = 0
    for test_file in sorted(unit_dir.glob("test_*.py")):
        print(f"\n>>> {test_file.name}")
        if run_python_script(test_file):
            passed += 1
        else:
            failed += 1
    return passed, failed

def run_integration_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("Running INTEGRATION tests...")
    print("=" * 60)
    int_dir = TEST_DIR / "integration"
    passed = 0
    failed = 0
    for test_file in sorted(int_dir.glob("test_*.py")):
        print(f"\n>>> {test_file.name}")
        if run_python_script(test_file):
            passed += 1
        else:
            failed += 1
    return passed, failed

def run_builtin_tests():
    """Run all builtin tool/hook tests."""
    print("=" * 60)
    print("Running BUILTIN tests...")
    print("=" * 60)
    builtin_dir = TEST_DIR / "builtin"
    passed = 0
    failed = 0
    for test_file in sorted(builtin_dir.glob("test_*.py")):
        print(f"\n>>> {test_file.name}")
        if run_python_script(test_file):
            passed += 1
        else:
            failed += 1
    return passed, failed

def run_specific_test(test_name):
    """Run a specific test module by name."""
    # Check in all test directories
    for subdir in ["unit", "integration", "builtin"]:
        test_file = TEST_DIR / subdir / f"{test_name}.py"
        if test_file.exists():
            print(f"Running {test_file}...")
            success = run_python_script(test_file)
            return (1, 0) if success else (0, 1)
    print(f"Test file '{test_name}.py' not found.")
    return 0, 1

def main():
    if len(sys.argv) < 2:
        # Run all tests
        all_passed = 0
        all_failed = 0

        p, f = run_unit_tests()
        all_passed += p
        all_failed += f

        p, f = run_integration_tests()
        all_passed += p
        all_failed += f

        p, f = run_builtin_tests()
        all_passed += p
        all_failed += f

        print("\n" + "=" * 60)
        print(f"TOTAL: {all_passed} passed, {all_failed} failed")
        print("=" * 60)
        return all_failed == 0

    arg = sys.argv[1]

    if arg == "unit":
        passed, failed = run_unit_tests()
    elif arg == "integration":
        passed, failed = run_integration_tests()
    elif arg == "builtin":
        passed, failed = run_builtin_tests()
    elif arg.startswith("test_"):
        passed, failed = run_specific_test(arg)
    else:
        print(f"Unknown argument: {arg}")
        print("Usage: python run_tests.py [unit|integration|builtin|test_<name>]")
        return False

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)