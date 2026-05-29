#!/usr/bin/env python3
"""
gen_test_data.py - Generate test data files for BBagent tests.

This script creates sample files used by the test suite.
"""
import sys
from pathlib import Path

TEST_TEMP = Path(__file__).parent.parent / "temp"
TEST_DATA = Path(__file__).parent.parent / "test_data"


def create_text_files():
    """Create sample text files for read/edit/grep tests."""
    files = {
        "sample.txt": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n",
        "multiline.txt": "First line\nSecond line\nThird line\nFourth line\nFifth line\n",
        "code.py": "def hello():\n    print('Hello, World!')\n    return True\n",
        "numbers.txt": "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n",
    }

    for filename, content in files.items():
        filepath = TEST_TEMP / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
        print(f"Created: {filepath}")


def create_test_dirs():
    """Create sample directory structures for find/ls tests."""
    dirs = [
        "test_find_dir",
        "test_find_dir/subdir1",
        "test_find_dir/subdir2",
        "test_ls_dir",
        "test_ls_dir/nested",
    ]

    for dirname in dirs:
        dirpath = TEST_TEMP / dirname
        dirpath.mkdir(parents=True, exist_ok=True)

        # Create some files in these directories
        if "test_find_dir" in dirname:
            (dirpath / "file.txt").write_text("test")
        if "test_ls_dir" in dirname:
            (dirpath / "data.json").write_text("{}")

        print(f"Created directory: {dirpath}")


def create_json_files():
    """Create sample JSON files."""
    import json

    json_files = {
        "config.json": {"name": "test", "version": "1.0"},
        "data.json": {"items": [1, 2, 3], "active": True},
    }

    for filename, content in json_files.items():
        filepath = TEST_TEMP / filename
        filepath.write_text(json.dumps(content, indent=2))
        print(f"Created: {filepath}")


def main():
    print("Generating test data files...")
    print(f"Output directory: {TEST_TEMP}")

    TEST_TEMP.mkdir(parents=True, exist_ok=True)

    create_text_files()
    create_test_dirs()
    create_json_files()

    print("\nTest data generation complete!")
    print(f"Files are in: {TEST_TEMP}")


if __name__ == "__main__":
    main()