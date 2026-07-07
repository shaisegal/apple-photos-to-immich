from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v]
    return [str(value)] if value else []


def get_bool(photo: Any, *names: str) -> bool:
    for name in names:
        value = getattr(photo, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if isinstance(value, bool):
            return value
    return False
