"""
Fixture discovery for pytest-a11y.

This conftest.py ensures that the axe fixture is discoverable by pytest.
Pytest automatically loads conftest.py files in packages, making fixtures
defined here (or imported here) available to all tests.
"""

from __future__ import annotations

# Import the fixture to make it discoverable by pytest
# pytest automatically discovers fixtures in conftest.py
from pytest_a11y.axe.fixtures import axe  # noqa: F401
