"""Shared, deterministic file boundary. Target code is never imported or run."""
import os
from pathlib import Path

SKIP_PARTS = frozenset({".git", ".github", ".venv", "venv", "__pycache__", ".tox",
                        "site-packages", "node_modules", "reports", "dist", "build"})
SOURCE_EXTENSIONS = frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})


def check_path(path: Path) -> None:
    if any(p.is_symlink() for p in (path.absolute(), *path.absolute().parents)):
        raise OSError(f"Symlink is outside the supported scan boundary: {path}")


def project_files(root: Path) -> list[Path]:
    check_path(root)
    if not root.is_dir():
        raise OSError(f"Not a project directory: {root}")
    files = []

    def fail(error):
        raise error

    for current, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_PARTS)
        for name in dirs:
            check_path(Path(current) / name)
        for name in sorted(names):
            path = Path(current) / name
            check_path(path)
            # Refuse sockets/devices/FIFOs: reads must not block or access devices.
            if not path.is_file():
                raise OSError(f"Not a regular file: {path}")
            files.append(path)
    return files


def source_files(root: Path) -> list[Path]:
    return [p for p in project_files(root) if p.suffix in SOURCE_EXTENSIONS]


def read_source(path: Path) -> str:
    check_path(path)
    if not path.is_file():
        raise OSError(f"Not a regular file: {path}")
    return path.read_text(encoding="utf-8")
