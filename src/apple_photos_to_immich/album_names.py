from __future__ import annotations


def build_album_title(name: str) -> str:
    return name.strip("/")


def build_system_album_title(name: str, system_album_prefix: str) -> str:
    name = name.strip("/")
    prefix = system_album_prefix.strip("/")
    if prefix:
        return f"{prefix}: {name}"
    return name


def legacy_user_album_title(name: str, album_prefix: str) -> str:
    name = name.strip("/")
    prefix = album_prefix.strip("/")
    return f"{prefix}/Albums/{name}" if prefix else f"Albums/{name}"


def legacy_system_album_title(name: str, album_prefix: str) -> str:
    name = name.strip("/")
    prefix = album_prefix.strip("/")
    return f"{prefix}/System/{name}" if prefix else f"System/{name}"
