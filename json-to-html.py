import json
import html
import reverse_geocoder as rg
from datetime import datetime

INPUT_JSON = "activities.json"
OUTPUT_HTML = "activities.html"


def seconds_to_hms(seconds):
    if seconds is None:
        return ""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def pace_min_per_km(distance_m, seconds):
    if not distance_m or not seconds or distance_m == 0:
        return ""
    pace_sec = seconds / (distance_m / 1000)
    m = int(pace_sec // 60)
    s = int(pace_sec % 60)
    return f"{m}:{s:02d} min/km"


def format_datetime(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d · %H:%M")


def activity_icon_and_label(sport_type):
    if not sport_type:
        return "❓", "Other"

    t = sport_type.lower()

    if t == "run":
        return "🏃", "Run"
    if t == "ride":
        return "🚴", "Ride"
    if t == "weighttraining":
        return "🏋️", "Strength training"
    if t == "workout":
        return "💪", "Workout"
    if t in ("walk", "hike"):
        return "🥾", "Walk / Hike"
    if t == "swim":
        return "🏊", "Swim"
    if t == "nordicski":
        return "🎿", "Cross-country ski"
    if t == "alpineski":
        return "⛷", "Alpine ski"

    return "❓", sport_type

def get_location_name(lat, lon):
    try:
        result = rg.search((lat, lon))[0]
        city = result.get("name")
        country = result.get("cc")

        if city and country:
            return f"{city} {country}"
        elif country:
            return country
        else:
            return None
    except:
        return None

print("Reading JSON…")
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    activities = json.load(f)

print(f"✍ Writing HTML for {len(activities)} activities…")

html_lines = []

# ---------- HTML HEADER ----------
html_lines.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Training Log</title>
<style>
body {
    font-family: Arial, Helvetica, sans-serif;
    width: 100%;
    margin: 0;
    padding: 16px;
    box-sizing: border-box;
    line-height: 1.6;
    color: #111;
    overflow-x: hidden;
}

@media (min-width: 900px) {
    body {
        max-width: 900px;
        margin: 0 auto;
    }
}

.activity {
    margin-bottom: 48px;
    padding-bottom: 12px;
    border-bottom: 1px solid #ddd;
}

h1 {
    margin-top: 0;
}

h2 {
    margin-bottom: 2px;
}

.type {
    font-style: italic;
    margin-bottom: 6px;
}

.meta {
    font-weight: bold;
    margin-bottom: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.section {
    margin-top: 12px;
}

.private {
    background: #f7f7f7;
    padding: 10px;
    border-left: 4px solid #999;
}

.metrics ul {
    margin: 6px 0 0 18px;
    padding-left: 16px;
}

p {
    white-space: pre-wrap;
}

.meta, p {
    word-break: break-word;
    overflow-wrap: break-word;
}

hr {
    margin-top: 24px;
}

@media (prefers-color-scheme: dark) {

body {
    background: #121212;
    color: #e0e0e0;
}

.private {
    background: #1e1e1e;
    border-left: 4px solid #666;
}

.activity {
    border-bottom: 1px solid #333;
}

a {
    color: #8ab4f8;
}

}
</style>
</head>
<body>

<h1>Training Log</h1>
<hr>
""")

# ---------- ACTIVITIES ----------
location_cache = {}
for act in activities:
    name = html.escape(act.get("activityName", "Untitled"))
    activity_id = act.get("activityId")
    strava_link = None
    if activity_id:
        strava_link = f"https://www.strava.com/activities/{activity_id}"
    start = act.get("startTimeLocal")
    distance = act.get("distance")
    moving = act.get("movingDuration")

    public_note = act.get("publicDescription")
    private_note = act.get("privateNote")

    avg_hr = act.get("averageHR")
    max_hr = act.get("maxHR")
    cadence = act.get("averageRunningCadenceInStepsPerMinute")
    elev = act.get("elevationGain")
    suffer = act.get("sufferScore")

    # ✅ FIX: use sportType / type
    sport_type = act.get("sportType") or act.get("type")
    icon, type_label = activity_icon_and_label(sport_type)
    
    html_lines.append('<div class="activity">')
    
# Titel  
    if strava_link:
        html_lines.append(
            f'<h2>{icon} {name} '
            f'<a href="{strava_link}" target="_blank" style="font-size:0.7em">🔗</a></h2>'
        )
    else:
        html_lines.append(f"<h2>{icon} {name}</h2>")

    lat = act.get("startLat")
    lon = act.get("startLng")
    
# Location + Type
    location_text = None

    if lat is not None and lon is not None:
        key = (round(lat, 3), round(lon, 3))

        if key not in location_cache:
            location_cache[key] = get_location_name(lat, lon)

        location_text = location_cache[key]

    if location_text:
        html_lines.append(f'<div class="type">{type_label}, {location_text}</div>')
    else:
        html_lines.append(f'<div class="type">{type_label}</div>')
    
    if start:
        html_lines.append(f'<div class="meta">📅 {format_datetime(start)}</div>')

    stats = []

    elapsed = act.get("elapsedDuration")
    has_distance = distance is not None and distance > 0
    has_moving = moving is not None and moving > 0

    # Distance → bara om det finns på riktigt
    if has_distance:
        stats.append(f"📏 {distance/1000:.2f} km")

    # Time
    if has_distance:
        # typ löpning/cykel
        if has_moving:
            stats.append(f"⏱ {seconds_to_hms(moving)} moving")
    else:
        # gym, yoga, osv
        if elapsed:
            stats.append(f"⏱ {seconds_to_hms(elapsed)}")

    # Pace → bara om det är meningsfullt
    pace = pace_min_per_km(distance, moving)
    if pace and has_distance:
        stats.append(f"⚡ {pace}")
    
    if stats:
        html_lines.append(f'<div class="meta">{" · ".join(stats)}</div>')

    if public_note:
        html_lines.append('<div class="section">')
        html_lines.append("<strong>📝 Public note</strong><br>")
        html_lines.append(f"<p>{html.escape(public_note).replace(chr(10), '<br>')}</p>")
        html_lines.append("</div>")

    if private_note:
        html_lines.append('<div class="section private">')
        html_lines.append("<strong>🔒 Private note</strong><br>")
        html_lines.append(f"<p>{html.escape(private_note).replace(chr(10), '<br>')}</p>")
        html_lines.append("</div>")

    metrics = []
    elapsed = act.get("elapsedDuration")
    if elapsed is not None:
        metrics.append(f"Elapsed time: {seconds_to_hms(elapsed)}")
    if avg_hr is not None:
        metrics.append(f"Avg HR: {int(avg_hr)} bpm")
    if max_hr is not None:
        metrics.append(f"Max HR: {int(max_hr)} bpm")
    if cadence is not None:
        metrics.append(f"Cadence: {cadence} spm")
    if elev is not None:
        metrics.append(f"Elevation gain: {int(elev)} m")
    if suffer is not None:
        metrics.append(f"Suffer score: {int(suffer)}")

    if metrics:
        html_lines.append('<div class="section metrics">')
        html_lines.append("<strong>📊 Metrics</strong>")
        html_lines.append("<ul>")
        for m in metrics:
            html_lines.append(f"<li>{m}</li>")
        html_lines.append("</ul>")
        html_lines.append("</div>")

    html_lines.append("<hr>")
    html_lines.append("</div>")

# ---------- HTML FOOTER ----------
html_lines.append("""
</body>
</html>
""")

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write("\n".join(html_lines))

print("✅ Done!")
print(f"   Output file: {OUTPUT_HTML}")
