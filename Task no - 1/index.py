import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://jsonplaceholder.typicode.com/posts"
PAGE_SIZE = 10
OUTPUT_FILE = "aggregated_data.json"

MAX_RETRIES = 5
BACKOFF_BASE = 1.0        # seconds
BACKOFF_MAX = 30.0        # seconds
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class FetchConfig:
    base_url: str = BASE_URL
    page_size: int = PAGE_SIZE
    max_retries: int = MAX_RETRIES
    timeout: int = 10


def build_session() -> requests.Session:
    
    session = requests.Session()
    urllib3_retry = Retry(
        total=0,          # manual retry loop handles retries; keep urllib3 passive
        connect=0,
        read=0,
    )
    adapter = HTTPAdapter(max_retries=urllib3_retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "api-aggregator/1.0",
    })
    return session


def request_with_backoff(
    session: requests.Session,
    url: str,
    params: Dict[str, Any],
    config: FetchConfig,
) -> requests.Response:
   
    attempt = 0
    while True:
        try:
            response = session.get(url, params=params, timeout=config.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            attempt += 1
            if attempt > config.max_retries:
                logger.error("Max retries exceeded due to network error: %s", exc)
                raise
            sleep_for = _compute_backoff(attempt)
            logger.warning("Network error (%s). Retry %d/%d in %.1fs",
                            exc, attempt, config.max_retries, sleep_for)
            time.sleep(sleep_for)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            attempt += 1
            if attempt > config.max_retries:
                response.raise_for_status()
                return response  # unreachable if raise_for_status raises

            retry_after = response.headers.get("Retry-After")
            sleep_for = float(retry_after) if retry_after else _compute_backoff(attempt)
            logger.warning(
                "Received %s. Retry %d/%d in %.1fs",
                response.status_code, attempt, config.max_retries, sleep_for,
            )
            time.sleep(sleep_for)
            continue

        # Raise for any other non-2xx (4XX client errors we shouldn't retry)
        response.raise_for_status()
        return response


def _compute_backoff(attempt: int) -> float:
    """Exponential backoff with full jitter, capped at BACKOFF_MAX."""
    raw = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** (attempt - 1)))
    return random.uniform(0, raw)


def fetch_all_pages(config: FetchConfig) -> List[Dict[str, Any]]:

    session = build_session()
    all_items: List[Dict[str, Any]] = []
    page = 0

    try:
        while True:
            params = {
                "_start": page * config.page_size,
                "_limit": config.page_size,
            }
            logger.info("Fetching page %d ...", page + 1)
            response = request_with_backoff(session, config.base_url, params, config)
            batch = response.json()

            if not batch:
                logger.info("No more data. Stopping at page %d.", page + 1)
                break

            all_items.extend(batch)
            page += 1
    finally:
        session.close()

    return all_items


def extract_and_aggregate(raw_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    
    records = []
    for item in raw_items:
        try:
            record = {
                "id": item["id"],
                "user_id": item["userId"],
                "title": item["title"].strip(),
                "body_preview": item["body"][:80].strip(),
            }
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed record %s: %s", item, exc)
            continue
        records.append(record)

    posts_per_user: Dict[str, int] = {}
    for r in records:
        key = str(r["user_id"])
        posts_per_user[key] = posts_per_user.get(key, 0) + 1

    aggregated = {
        "total_records": len(records),
        "unique_users": len(posts_per_user),
        "posts_per_user": posts_per_user,
        "records": records,
    }
    return aggregated


def save_to_json(data: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved aggregated data to %s", path)


def main() -> None:
    config = FetchConfig()
    raw_items = fetch_all_pages(config)
    logger.info("Fetched %d raw records total.", len(raw_items))

    aggregated = extract_and_aggregate(raw_items)
    save_to_json(aggregated, OUTPUT_FILE)

    logger.info(
        "Done. %d records across %d users.",
        aggregated["total_records"], aggregated["unique_users"],
    )


if __name__ == "__main__":
    main()
