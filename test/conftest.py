"""
Test configuration and setup.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from env import get_env

# Global test environment
ENV = get_env()

# Test data directory
TEST_TEMP = Path(__file__).parent / "temp"
TEST_TEMP.mkdir(exist_ok=True)

# Test data source directory
TEST_DATA = Path(__file__).parent / "test_data"