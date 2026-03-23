"""SciPy preload helper.

PySide6's shiboken feature loader can heavily slow down imports of large SciPy
submodules when SciPy is first imported *after* Qt/PySide has already been
loaded. Preloading the SciPy modules this app uses before importing PySide6
avoids that startup path.
"""

from __future__ import annotations

from importlib import import_module

_PRELOADED = False


def preload_scipy_dependencies() -> None:
    """Import the SciPy submodules used by MFClab exactly once."""
    global _PRELOADED
    if _PRELOADED:
        return

    for module_name in ("scipy.fft", "scipy.signal", "scipy.ndimage"):
        import_module(module_name)

    _PRELOADED = True
