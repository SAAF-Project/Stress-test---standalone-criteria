"""
Example Data Extraction Script
================================
Purpose : Extract data from a CSV source file and apply basic filters for audit analysis.
Inputs  : SOURCE_FILE environment variable pointing to the input CSV file.
Outputs : Filtered CSV written to outputs/extracted_data.csv relative to this script.

Usage:
    SOURCE_FILE=path/to/data.csv python example_data_extract.py
"""

import csv
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_csv(file_path: Path) -> list[dict]:
    """Load a CSV file and return a list of row dicts."""
    logger.info(f"Loading data from {file_path}")
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    logger.info(f"Loaded {len(rows)} rows")
    return rows


def filter_rows(rows: list[dict], column: str, value: str) -> list[dict]:
    """Return rows where the given column matches the given value."""
    filtered = [row for row in rows if row.get(column) == value]
    logger.info(f"Filtered to {len(filtered)} rows where {column} = '{value}'")
    return filtered


def write_csv(rows: list[dict], output_path: Path) -> None:
    """Write a list of row dicts to a CSV file."""
    if not rows:
        logger.warning("No rows to write.")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Written {len(rows)} rows to {output_path}")


def main() -> None:
    source = os.environ.get("SOURCE_FILE")
    if not source:
        raise EnvironmentError("SOURCE_FILE environment variable is not set.")

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    rows = load_csv(source_path)

    # Example filter: replace "Status" and "Active" with your actual column and value
    filtered = filter_rows(rows, column="Status", value="Active")

    output_path = Path(__file__).parent.parent.parent / "outputs" / "extracted_data.csv"
    write_csv(filtered, output_path)


if __name__ == "__main__":
    main()
