"""blackboxctl - a command line tool for the M-Vave BlackBox.

An explicit package (not a namespace package), so that ``python -m blackboxctl``
and the ``blackboxctl`` console script both work.

GPL-3.0. See ../LICENSE and ../NOTICE for the full text and for attribution to
the upstream reverse engineering this is derived from.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__", "captures", "library", "protocol"]

from . import captures, library, protocol  # noqa: E402,F401

# transport is deliberately NOT imported here. It binds CoreMIDI at import time
# on macOS only, and every non-device command must work without it.
