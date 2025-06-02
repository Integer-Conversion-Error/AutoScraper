import pytest

# This file will serve as the main entry point for running all UI tests.
# Pytest automatically discovers tests in files named `test_*.py` or `*_test.py`
# within the specified directories.
# By organizing tests into subdirectories, we can run them all by simply
# executing `pytest` from the root `tests/` directory.

# No explicit imports of test functions are needed here, as pytest's discovery
# mechanism handles it. This file primarily serves as a placeholder or
# a central point if specific test collection logic were needed beyond
# standard pytest discovery.

# To run all tests:
# 1. Ensure your application is running at http://localhost:5000.
# 2. Navigate to the 'AutoScraper' root directory in your terminal.
# 3. Run: pytest tests/

# If you want to run tests from a specific file or directory:
# pytest tests/ui_elements/
# pytest tests/payload_management/test_payload_lifecycle.py
