"""Conversion pipeline package with lazy public exports."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "BatchResult": ".converter",
    "RollbackResult": ".converter",
    "rollback_batch": ".converter",
    "run_batch": ".converter",
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    for export, export_module in _EXPORTS.items():
        if export_module == module_name and hasattr(module, export):
            globals()[export] = getattr(module, export)
    return globals()[name]
