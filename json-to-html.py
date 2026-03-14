import json
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
    if t in ("weighttraining", "workout"):
        return "🏋️", "Strength training"
    if t in ("walk", "hike"):
        return "🥾", "Walk / Hike"
    if t == "swim":
        return "🏊", "Swim"
    if t == "nordicski":
        return "🎿", "Cross-country ski"
    if t == "alpineski":
        return "⛷", "Alpine ski"

    return "❓", sport_type


print("Reading JSON…")
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    activities = json.load(f)

print(f"✍ Writing HTML for {len(activities)} activities…")

html = []

# ---------- HTML HEADER ----------
html.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Training Log</title>
<style>
body {
    font-family: Arial, Helvetica, sans-serif;
    max-width: 900px;
    margin: 40px auto;
    line-height: 1.6;
    color: #111;
}
.activity {
    margin-bottom: 48px;
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
}
.section {
    margin-top: 12px;
}
.private {
    background: #f4f4f4;
    padding: 10px;
    border-left: 4px solid #999;
}
.metrics ul {
    margin: 6px 0 0 18px;
}
hr {
    margin-top: 24px;
}
</style>
</head>
<body>

<h1>Training Log</h1>
<hr>
""")

# ---------- ACTIVITIES ----------
for act in activities:
    name = act.get("activityName", "Untitled")
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

    html.append('<div class="activity">')
    html.append(f"<h2>{icon} {name}</h2>")
    html.append(f'<div class="type">{type_label}</div>')

    if start:
        html.append(f'<div class="meta">📅 {format_datetime(start)}</div>')

    stats = []
    if distance:
        stats.append(f"📏 {distance/1000:.2f} km")
    if moving:
        stats.append(f"⏱ {seconds_to_hms(moving)}")
    pace = pace_min_per_km(distance, moving)
    if pace:
        stats.append(f"⚡ {pace}")

    if stats:
        html.append(f'<div class="meta">{" · ".join(stats)}</div>')

    if public_note:
        html.append('<div class="section">')
        html.append("<strong>📝 Public note</strong><br>")
        html.append(f"<p>{public_note.replace(chr(10), '<br>')}</p>")
        html.append("</div>")

    if private_note:
        html.append('<div class="section private">')
        html.append("<strong>🔒 Private note</strong><br>")
        html.append(f"<p>{private_note.replace(chr(10), '<br>')}</p>")
        html.append("</div>")

    metrics = []
    if avg_hr:
        metrics.append(f"Avg HR: {int(avg_hr)} bpm")
    if max_hr:
        metrics.append(f"Max HR: {int(max_hr)} bpm")
    if cadence:
        metrics.append(f"Cadence: {cadence} spm")
    if elev:
        metrics.append(f"Elevation gain: {int(elev)} m")
    if suffer is not None:
        metrics.append(f"Suffer score: {int(suffer)}")

    if metrics:
        html.append('<div class="section metrics">')
        html.append("<strong>📊 Metrics</strong>")
        html.append("<ul>")
        for m in metrics:
            html.append(f"<li>{m}</li>")
        html.append("</ul>")
        html.append("</div>")

    html.append("<hr>")
    html.append("</div>")

# ---------- HTML FOOTER ----------
html.append("""
</body>
</html>
""")

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print("✅ Done!")
print(f"   Output file: {OUTPUT_HTML}")
