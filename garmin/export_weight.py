#!/usr/bin/env python3
"""Export Garmin Connect weight measurements to a local JSON file.

The script never prints measurement values. Keep the output file private:
the parent repository is public.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator


def describe_payload(value: Any) -> tuple[int, list[str]]:
    """Return a record count and top-level keys without exposing values."""
    if isinstance(value, list):
        return len(value), []
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())
        list_counts = [
            len(item) for item in value.values() if isinstance(item, list)
        ]
        return (sum(list_counts) if list_counts else 1), keys
    return (0 if value is None else 1), []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument(
        "--output",
        default="garmin/data/weight-measurements.json",
        help="Private local output path (default: garmin/data/weight-measurements.json)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    if not api_key:
        parser.error("Set the GARMIN_PERSONAL_API_KEY environment variable.")

    # Validate date format before making an API request.
    date.fromisoformat(args.start_date)
    date.fromisoformat(args.end_date)

    print(f"Requesting Garmin weight data: {args.start_date} to {args.end_date}")
    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(api_key)

    with GarminPersonalApiClient(token.access_token) as client:
        measurements = client.get_weight_measurements(
            args.start_date, args.end_date
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(measurements, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    count, keys = describe_payload(measurements)
    print("Garmin authentication: successful")
    print("Weight endpoint: successful")
    print(f"Records returned (estimated): {count}")
    if keys:
        print(f"Top-level response fields: {', '.join(keys)}")
    print(f"JSON saved to: {output_path}")
    print("Measurement values are intentionally not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
