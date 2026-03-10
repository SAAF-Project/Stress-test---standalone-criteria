"""
Example API Connector
======================
Purpose : Template for connecting to a REST API and paginating through results.
Inputs  : API_BASE_URL, API_KEY environment variables.
Outputs : JSON file written to outputs/api_results.json relative to the repo root.

Usage:
    API_BASE_URL=https://api.example.com API_KEY=your_key python example_api_connector.py
"""

import json
import logging
import os
from pathlib import Path

import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_headers() -> dict[str, str]:
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise EnvironmentError("API_KEY environment variable is not set.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


def fetch_page(base_url: str, endpoint: str, page: int, headers: dict) -> dict:
    """Fetch a single page from a paginated API endpoint."""
    url = f"{base_url}{endpoint}?page={page}&page_size=100"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP {e.code} fetching {url}: {e.reason}")
        raise


def fetch_all(base_url: str, endpoint: str, headers: dict) -> list[dict]:
    """Paginate through all results for the given endpoint."""
    results: list[dict] = []
    page = 1
    while True:
        logger.info(f"Fetching page {page} from {endpoint}")
        data = fetch_page(base_url, endpoint, page, headers)
        items = data.get("results", data.get("data", []))
        results.extend(items)
        if not data.get("next"):
            break
        page += 1
    logger.info(f"Total records fetched: {len(results)}")
    return results


def main() -> None:
    base_url = os.environ.get("API_BASE_URL")
    if not base_url:
        raise EnvironmentError("API_BASE_URL environment variable is not set.")

    headers = get_headers()

    # Replace "/users" with the actual endpoint you need
    records = fetch_all(base_url, "/users", headers)

    output_path = Path(__file__).parent.parent.parent / "outputs" / "api_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    logger.info(f"Results written to {output_path}")


if __name__ == "__main__":
    main()
