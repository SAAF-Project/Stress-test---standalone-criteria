"""
File Organizer
===============
Purpose : Move files from a source folder into dated subfolders based on their modification date.
          Useful for organizing downloaded exports, audit evidence, or agent outputs.
Inputs  : SOURCE_DIR environment variable (folder to organize).
          TARGET_DIR environment variable (destination root; defaults to SOURCE_DIR/organized).
Outputs : Files moved into TARGET_DIR/YYYY-MM-DD/ subfolders.

Usage:
    SOURCE_DIR=~/Downloads/audit-exports python file_organizer.py
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_modification_date(path: Path) -> str:
    """Return the file's modification date as YYYY-MM-DD."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def organize(source_dir: Path, target_dir: Path) -> None:
    """Move files from source_dir into dated subfolders in target_dir."""
    files = [p for p in source_dir.iterdir() if p.is_file()]
    logger.info(f"Found {len(files)} file(s) in {source_dir}")

    for file in files:
        date_folder = target_dir / get_modification_date(file)
        date_folder.mkdir(parents=True, exist_ok=True)
        destination = date_folder / file.name

        # Avoid overwriting existing files by appending a counter
        counter = 1
        while destination.exists():
            destination = date_folder / f"{file.stem}_{counter}{file.suffix}"
            counter += 1

        shutil.move(str(file), str(destination))
        logger.info(f"Moved {file.name} -> {destination.relative_to(target_dir.parent)}")

    logger.info("Done.")


def main() -> None:
    source = os.environ.get("SOURCE_DIR")
    if not source:
        raise EnvironmentError("SOURCE_DIR environment variable is not set.")

    source_dir = Path(source).expanduser().resolve()
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {source_dir}")

    target_default = source_dir / "organized"
    target_dir = Path(os.environ.get("TARGET_DIR", str(target_default))).expanduser().resolve()

    organize(source_dir, target_dir)


if __name__ == "__main__":
    main()
