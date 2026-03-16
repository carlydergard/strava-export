import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event

TIMEZONE = ZoneInfo("Europe/Stockholm")

INPUT_JSON = "activities.json"
OUTPUT_ICS = "activities.ics"

EMOJI_BY_SPORT = {
    "Run": "🏃",
    "WeightTraining": "🏋️",
    "Ride": "🚴",
    "VirtualRide": "🚴",
    "Swim": "🏊",
    "Walk": "🚶",
    "Hike": "🥾",
    "NordicSki": "🎿",
    "AlpineSki": "⛷️",
}


def seconds_to_hhmmss(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def mps_to_min_per_km(speed):
    if not speed or speed <= 0:
        return None
    pace_sec = 1000 / speed
    m = int(pace_sec // 60)
    s = int(round(pace_sec % 60))
    return f"{m}:{s:02d} min/km"


def build_description(a):
    lines = []

    if a.get("publicDescription"):
        lines.append("Notes:")
        lines.append(a["publicDescription"].strip())
        lines.append("")

    if a.get("privateNote"):
        lines.append("Private:")
        lines.append(a["privateNote"].strip())
        lines.append("")

    lines.append("Stats:")

    if a.get("distance", 0) > 0:
        lines.append(f"Distance: {a['distance'] / 1000:.2f} km")

    lines.append(f"Time: {seconds_to_hhmmss(a['elapsedDuration'])}")

    pace = mps_to_min_per_km(a.get("averageSpeed"))
    if pace:
        lines.append(f"Avg pace: {pace}")

    if a.get("averageHR"):
        lines.append(f"Avg HR: {int(a['averageHR'])} bpm")

    if a.get("elevationGain"):
        lines.append(f"Elevation gain: {int(a['elevationGain'])} m")

    if a.get("sufferScore") is not None:
        lines.append(f"Suffer score: {int(a['sufferScore'])}")

    return "\n".join(lines)


def main():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        activities = json.load(f)

    cal = Calendar()
    cal.add("prodid", "-//Strava Calendar//EN")
    cal.add("version", "2.0")

    for a in activities:
        start = datetime.strptime(
            a["startTimeLocal"], "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=TIMEZONE)

        duration = a.get("elapsedDuration", 0)
        end = start + timedelta(seconds=duration)

        sport = a.get("sportType")
        emoji = EMOJI_BY_SPORT.get(sport, "❓")

        event = Event()
        uid = a.get("activityId")

        if uid:
            uid = f"strava-{uid}@carlydergard"
        else:
            safe_time = a["startTimeLocal"].replace(" ", "T")
            safe_name = a["activityName"].replace(" ", "_")
            uid = f"strengthlog-{safe_time}-{safe_name}@carlydergard"
        event.add("uid", uid)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("summary", f"{emoji} {a['activityName']}")
        event.add("description", build_description(a))

        cal.add_component(event)

    with open(OUTPUT_ICS, "wb") as f:
        f.write(cal.to_ical())


if __name__ == "__main__":
    main()
