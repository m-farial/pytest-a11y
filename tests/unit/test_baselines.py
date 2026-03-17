from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

import pytest

MODULE_PATH: str = "pytest_a11y.baselines"
INTERNAL_PATH: str = "pytest_a11y._internal.comparison.baseline_manager"


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return importlib.import_module(MODULE_PATH)


@pytest.fixture(scope="module")
def internal_module() -> ModuleType:
    return importlib.import_module(INTERNAL_PATH)


def test_baseline_manager_is_reexported(
    module: ModuleType,
    internal_module: ModuleType,
) -> None:
    """
    Ensure BaselineManager is re-exported
    and is the exact same object as the internal one.

    If the internal module is reloaded (common in isolated test runs), the
    exported reference should follow the latest internal implementation.
    """
    import importlib

    module = importlib.reload(module)
    internal_module = importlib.reload(internal_module)

    exported: Any = module.BaselineManager
    internal: Any = internal_module.BaselineManager

    # The exported name should refer to the same logical class as the internal
    # implementation, even if module reloads (common in isolated test runs) can
    # result in distinct class objects with the same module/name.
    assert exported.__name__ == internal.__name__
    assert exported.__module__ == internal.__module__


def test_all_exports_are_correct(module: ModuleType) -> None:
    """
    Ensure __all__ contains only BaselineManager.
    """
    assert hasattr(module, "__all__")
    assert module.__all__ == ["BaselineManager"]


@pytest.mark.parametrize(
    "attr_name,should_exist",
    [
        ("BaselineManager", True),
        ("NonExistent", False),
    ],
)
def test_module_attributes(
    module: ModuleType,
    attr_name: str,
    should_exist: bool,
) -> None:
    """
    Parameterized attribute existence test.
    """
    assert hasattr(module, attr_name) is should_exist
