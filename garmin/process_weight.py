#!/usr/bin/env python3
"""Create one daily weight value from Garmin's raw weight export.

Multiple weigh-ins on a day are averaged. Missing days are linearly
interpolated only when the two surrounding measured dates are at most
MAX_INTERPOLATION_GAP_DAYS apart. No extrapolation is performed.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_INPUT = Path("garmin/data/weight-measurements.json")
DEFAULT_OUTPUT = Path("garmin/data/daily-weight.json")
MAX_INTERPOLATION_GAP_DAYS = 14


def extract_daily_measurements(payload: dict[str, Any]) -> dict[date, list[float]]:
    """Extract all individual weights, converting Garmin grams to kilograms."""
    summaries = payload.get("dailyWeightSummaries", [])
    if not isinstance(summaries, list):
        raise ValueError("Expected dailyWeightSummaries to be a list")

    result: dict[date, list[float]] = {}
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        date_text = summary.get("summaryDate")
        if not date_text:
            latest = summary.get("latestWeight") or {}
            date_text = latest.get("calendarDate")
        if not date_text:
            continue
        day = date.fromisoformat(str(date_text))

        metrics = summary.get("allWeightMetrics")
        if not isinstance(metrics, list) or not metrics:
            latest = summary.get("latestWeight") or {}
            metrics = [latest] if latest else []

        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            grams = metric.get("weight")
            if isinstance(grams, (int, float)) and grams > 0:
                result.setdefault(day, []).append(float(grams) / 1000.0)

    if not result:
        raise ValueError("No weight measurements found in Garmin response")
    return result


def build_daily_series(measurements: dict[date, list[float]]) -> list[dict[str, Any]]:
    """Build a calendar-day series, retaining long gaps as null."""
    measured_days = sorted(measurements)
    daily: dict[date, dict[str, Any]] = {}

    for day in measured_days:
        values = measurements[day]
        daily[day] = {
            "date": day.isoformat(),
            "weightKg": round(mean(values), 3),
            "source": "measured" if len(values) == 1 else "averaged",
            "measurementCount": len(values),
        }

    for left, right in zip(measured_days, measured_days[1:]):
        span = (right - left).days
        if span <= 1 or span > MAX_INTERPOLATION_GAP_DAYS:
            continue

        left_weight = daily[left]["weightKg"]
        right_weight = daily[right]["weightKg"]
        for offset in range(1, span):
            day = left + timedelta(days=offset)
            fraction = offset / span
            interpolated = left_weight + (right_weight - left_weight) * fraction
            daily[day] = {
                "date": day.isoformat(),
                "weightKg": round(interpolated, 3),
                "source": "interpolated",
                "measurementCount": 0,
            }

    first, last = measured_days[0], measured_days[-1]
    output = []
    day = first
    while day <= last:
        output.append(daily.get(day, {
            "date": day.isoformat(),
            "weightKg": None,
            "source": "missing",
            "measurementCount": 0,
        }))
        day += timedelta(days=1)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    measurements = extract_daily_measurements(payload)
    series = build_daily_series(measurements)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(series, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    counts = {}
    for entry in series:
        counts[entry["source"]] = counts.get(entry["source"], 0) + 1
    print(f"Daily weight values written: {len(series)}")
    print(f"Measured dates: {len(measurements)}")
    print("Daily value types: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
