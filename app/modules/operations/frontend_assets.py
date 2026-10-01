"""Resolve reviewed React build assets; never accept paths from a request."""

import json
from pathlib import Path, PurePosixPath


def react_assets(directory: Path) -> dict[str, str] | None:
    try:
        manifest = json.loads((directory / ".vite" / "manifest.json").read_text())
        entry = manifest["frontend/react/entry.ts"]
        if entry.get("isEntry") is not True:
            return None
        script = entry["file"]
        styles = entry["css"]
        if len(styles) != 1:
            return None
        paths = [script, *styles]
        pending = list(entry.get("imports", []))
        visited = set()
        while pending:
            key = pending.pop()
            if key in visited:
                continue
            visited.add(key)
            chunk = manifest[key]
            paths.append(chunk["file"])
            paths.extend(chunk.get("css", []))
            pending.extend(chunk.get("imports", []))
        for value in paths:
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or ":" in value or "\\" in value:
                return None
            resolved = (directory / value).resolve()
            if not resolved.is_relative_to(directory.resolve()) or not resolved.is_file():
                return None
        if not script.endswith(".js") or not styles[0].endswith(".css"):
            return None
        return {"script": f"dist/react/{script}", "style": f"dist/react/{styles[0]}"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
