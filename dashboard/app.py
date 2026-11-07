from __future__ import annotations

"""Moil Bot dashboard entrypoint.

Implementation is split across app_part_a.py and app_part_b.py so the full
source can be versioned and restored reliably.
"""
from pathlib import Path

_PARTS = (
    Path(__file__).with_name("app_part_a.py"),
    Path(__file__).with_name("app_part_b.py"),
)
_source = "\n".join(path.read_text(encoding="utf-8") for path in _PARTS)
exec(compile(_source, str(Path(__file__).resolve()), "exec"), globals())
