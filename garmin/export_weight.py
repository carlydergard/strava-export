#!/usr/bin/env python3
"""Export Garmin Connect weight measurements to a date-stamped JSON archive.

The repository is public by user choice; credentials are never written to output.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

CHUNK_DAYS = 366


def describe_payload(value: Any) -> tuple[int, list[str]]:
    """Return a record count and top-level keys without exposing values."""
    if isinstance(value, list):
        return len(value), []
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())
        list_counts = [len(item) for item in value.values() if isinstance(item, list)]
        return (sum(list_counts) if list_counts else 1), keys
    return (0 if value is None else 1), []


def merge_payloads(payloads: list[Any]) -> Any:
    """Combine list-valued response fields while retaining first-chunk metadata."""
    if not payloads:
        return []
    first = payloads[0]
    if isinstance(first, list):
        return [entry for payload in payloads for entry in payload]
    if isinstance(first, dict):
        merged = dict(first)
        for key, first_value in first.items():
            values = [payload.get(key) for payload in payloads if isinstance(payload, dict)]
            if isinstance(first_value, list):
                merged[key] = [entry for value in values if isinstance(value, list) for entry in value]
            elif isinstance(first_value, dict):
                dict_values = [value for value in values if isinstance(value, dict)]
                merged[key] = merge_payloads(dict_values)
        return merged
    return first


def fetch_with_fallback(client: GarminPersonalApiClient, start: date, end: date) -> list[Any]:
    """Fetch a date window; halve it recursively if Garmin rejects the range."""
    try:
        print(f"  Fetching {start.isoformat()} to {end.isoformat()}")
        return [client.get_weight_measurements(start.isoformat(), end.isoformat())]
    except Exception as exc:
        # Only split server/response-size failures. Authentication and other
        # client errors should fail immediately rather than trigger many calls.
        message = str(exc)
        if not any(code in message for code in ("HTTP 500", "HTTP 413", "HTTP 504")):
            raise
        days = (end - start).days + 1
        if days <= 1:
            raise
        midpoint = start + timedelta(days=days // 2)
        print(f"  Range failed; retrying as smaller windows ({days} days)")
        return (
            fetch_with_fallback(client, start, midpoint - timedelta(days=1))
            + fetch_with_fallback(client, midpoint, end)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument(
        "--output",
        default="garmin/data/weight-measurements.json",
        help="JSON output path (default: garmin/data/weight-measurements.json)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    if not api_key:
        parser.error("Set the GARMIN_PERSONAL_API_KEY environment variable.")

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    if start > end:
        parser.error("--start-date must be on or before --end-date.")

    print(f"Requesting Garmin weight data: {start.isoformat()} to {end.isoformat()}")
    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(api_key)

    chunks: list[Any] = []
    with GarminPersonalApiClient(token.access_token) as client:
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), end)
            chunks.extend(fetch_with_fallback(client, cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)

    measurements = merge_payloads(chunks)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(measurements, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    count, keys = describe_payload(measurements)
    print("Garmin authentication: successful")
    print("Weight endpoint: successful")
    print(f"Successful request windows: {len(chunks)}")
    print(f"Records returned (estimated): {count}")
    if keys:
        print(f"Top-level response fields: {', '.join(keys)}")
    print(f"JSON saved to: {output_path}")
    print("Measurement values are intentionally not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
