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


def get_album_names(photo: Any) -> list[str]:
    """Return all album names exposed by osxphotos for a photo.

    `folder_album` preserves folder hierarchy for normal albums but may omit
    other album memberships such as shared albums. `albums` can expose those
    plain-title memberships, so combine both sources while preserving order.
    """

    names: list[str] = []
    for source in (
        as_list(getattr(photo, "folder_album", None)),
        as_list(getattr(photo, "albums", None)),
    ):
        for name in source:
            if not name or name == "_" or name in names:
                continue
            names.append(name)
    return names
