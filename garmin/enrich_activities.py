#!/usr/bin/env python3
"""Add the daily Garmin weight estimate to each activity by local calendar date."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ACTIVITIES = Path("activities.json")
DEFAULT_DAILY_WEIGHT = Path("garmin/data/daily-weight.json")


def activity_date(activity: dict[str, Any]) -> str | None:
    """Use the activity's local start date, matching Garmin's calendar dates."""
    value = activity.get("startTimeLocal")
    if not isinstance(value, str) or len(value) < 10:
        return None
    return value[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activities", type=Path, default=DEFAULT_ACTIVITIES)
    parser.add_argument("--daily-weight", type=Path, default=DEFAULT_DAILY_WEIGHT)
    args = parser.parse_args()

    activities = json.loads(args.activities.read_text(encoding="utf-8"))
    daily_series = json.loads(args.daily_weight.read_text(encoding="utf-8"))
    if not isinstance(activities, list):
        raise ValueError("activities.json must contain a JSON array")
    if not isinstance(daily_series, list):
        raise ValueError("daily-weight.json must contain a JSON array")

    weight_by_date = {
        entry["date"]: entry
        for entry in daily_series
        if isinstance(entry, dict) and isinstance(entry.get("date"), str)
    }

    matched = 0
    interpolated = 0
    missing = 0
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        day = activity_date(activity)
        weight = weight_by_date.get(day) if day else None
        if weight is None:
            activity["weightKg"] = None
            activity["weightSource"] = "missing"
            activity["weightMeasurementCount"] = 0
            missing += 1
            continue

        activity["weightKg"] = weight.get("weightKg")
        activity["weightSource"] = weight.get("source", "missing")
        activity["weightMeasurementCount"] = weight.get("measurementCount", 0)
        if activity["weightSource"] in ("measured", "averaged"):
            matched += 1
        elif activity["weightSource"] == "interpolated":
            interpolated += 1
        else:
            missing += 1

    args.activities.write_text(
        json.dumps(activities, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Activities enriched: {len(activities)}")
    print(f"Measured/averaged weight: {matched}")
    print(f"Interpolated weight: {interpolated}")
    print(f"Missing weight: {missing}")
    print(f"Updated: {args.activities}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
