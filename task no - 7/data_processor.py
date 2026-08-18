from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class DataExtractionError(Exception):
    pass


class DataValidationError(Exception):
    pass


@dataclass
class Record:
    id: int
    name: str
    value: float
    active: bool = True


def fetch_data_from_api(endpoint: str, timeout: int = 10) -> list[dict]:
    try:
        response = requests.get(endpoint, timeout=timeout)
    except requests.exceptions.Timeout:
        raise DataExtractionError(f"Request to {endpoint} timed out")
    except requests.exceptions.ConnectionError as exc:
        raise DataExtractionError(f"Connection to {endpoint} failed: {exc}")

    if response.status_code != 200:
        raise DataExtractionError(
            f"Received non-200 status code {response.status_code} from {endpoint}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise DataExtractionError(f"Response from {endpoint} is not valid JSON: {exc}")

    if not isinstance(data, list):
        raise DataExtractionError(
            f"Expected response to be a list but got {type(data).__name__}; must be a list"
        )

    return data


def parse_record(raw: Any) -> Record:
    if not isinstance(raw, dict):
        raise DataValidationError(f"Record must be a dict, got {type(raw).__name__}")

    for field_name in ("id", "name", "value"):
        if field_name not in raw:
            raise DataValidationError(f"Missing required field: '{field_name}'")

    try:
        record_id = int(raw["id"])
    except (ValueError, TypeError):
        raise DataValidationError(f"Invalid id: {raw['id']!r} cannot be converted to int")

    name = raw["name"]
    if not isinstance(name, str) or not name.strip():
        raise DataValidationError(f"Invalid name: {name!r} must be a non-empty string")
    name = name.strip()

    try:
        value = float(raw["value"])
    except (ValueError, TypeError):
        raise DataValidationError(f"Invalid value: {raw['value']!r} cannot be converted to float")

    active = bool(raw.get("active", True))

    return Record(id=record_id, name=name, value=value, active=active)


def parse_records(raw_list: list[Any]) -> list[Record]:
    return [parse_record(r) for r in raw_list]


def parse_records_lenient(raw_list: list[Any]) -> tuple[list[Record], list[str]]:
    records: list[Record] = []
    errors: list[str] = []
    for idx, raw in enumerate(raw_list):
        try:
            records.append(parse_record(raw))
        except DataValidationError as exc:
            errors.append(f"Record at index {idx}: {exc}")
    return records, errors


class DataProcessor:
    def __init__(self, endpoint: str, timeout: int = 10) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def extract(self) -> list[dict]:
        return fetch_data_from_api(self.endpoint, timeout=self.timeout)

    def process(self, strict: bool = True) -> list[Record]:
        raw = self.extract()
        if strict:
            return parse_records(raw)
        records, _ = parse_records_lenient(raw)
        return records

    def process_with_report(self) -> tuple[list[Record], list[str]]:
        raw = self.extract()
        return parse_records_lenient(raw)

    def summarize(self, records: list[Record] | None = None) -> dict:
        if records is None:
            records = self.process()
        if not records:
            return {"count": 0, "active_count": 0, "total_value": 0.0, "average_value": 0.0}
        total = sum(r.value for r in records)
        return {
            "count": len(records),
            "active_count": sum(1 for r in records if r.active),
            "total_value": total,
            "average_value": total / len(records),
        }
