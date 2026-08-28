"""``python -m blackboxctl`` entry point. GPL-3.0; see ../LICENSE and ../NOTICE."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
