import pandas as pd
import json

# ================= CONFIG =================
CSV_PATH = "strengthlog-export.csv"
ACTIVITIES_PATH = "activities.json"
BODYWEIGHT = 75
BODYWEIGHT_EXERCISES = ["Chins", "Pullups", "Dips"]
STRENGTHLOG_HEADER = "=== Strengthlog ==="
# ==========================================

# ---------- LOAD CSV ----------
df = pd.read_csv(CSV_PATH)
df["start_dt"] = pd.to_datetime(df["start"], unit="ms")
df["end_dt"] = pd.to_datetime(df["end"], unit="ms")

workouts = []

for start_time, workout_df in df.groupby("start"):
    workout_name = workout_df["workout"].iloc[0]
    start_dt = workout_df["start_dt"].iloc[0]
    end_dt = workout_df["end_dt"].iloc[0]

    summary_lines = []
    summary_lines.append("Exporterat från Strengthlog:")
    summary_lines.append("")
    summary_lines.append(workout_name)

    total_volume = 0

    for exercise, ex_df in workout_df.groupby("exercise"):
        ex_df = ex_df.sort_values("checked")

        reps_list = []
        weight_list = []

        for _, row in ex_df.iterrows():
            reps = int(row["reps"]) if not pd.isna(row["reps"]) else 0
            weight = row["weight"]

            if pd.isna(weight):
                weight = BODYWEIGHT if exercise in BODYWEIGHT_EXERCISES else 0
            else:
                weight = float(str(weight).replace(",", "."))

            reps_list.append(str(reps))
            weight_list.append(str(int(weight)) if weight.is_integer() else str(weight))

            total_volume += reps * weight

        # If no meaningful reps/weights → just show exercise name (e.g. planks)
        if all(r == "0" for r in reps_list) and all(w in ["0", "0.0"] for w in weight_list):
            summary_lines.append(exercise)
        else:
            reps_str = "-".join(reps_list) + " reps"
            weight_str = ", " + "-".join(weight_list) + " kg"
            summary_lines.append(f"{exercise} {reps_str}{weight_str}")

    summary_lines.append(f"Totalvolym: {int(total_volume)} kg")

    workouts.append({
        "date": start_dt.strftime("%Y-%m-%d"),
        "start_time": start_dt.strftime("%H:%M"),
        "duration_minutes": int((end_dt - start_dt).total_seconds() / 60),
        "name": workout_name,
        "summary": "\n".join(summary_lines)
    })

# Newest first
workouts.sort(key=lambda x: (x["date"], x["start_time"]), reverse=True)

merged_count = 0
created_count = 0
skipped_count = 0

# ---------- LOAD ACTIVITIES ----------
with open(ACTIVITIES_PATH, "r", encoding="utf-8") as f:
    activities = json.load(f)

def get_date(dt_string):
    return dt_string.split(" ")[0]

# ---------- MERGE ----------
for workout in workouts:
    workout_date = workout["date"]
    summary = workout["summary"]
    matches = []

    for activity in activities:
        activity_date = get_date(activity["startTimeLocal"])
        activity_type = activity.get("sportType", "")
        if activity_date == workout_date and activity_type == "WeightTraining":
            matches.append(activity)

    if len(matches) == 1:
        activity = matches[0]
        existing_note = activity.get("privateNote", "") or ""

        if STRENGTHLOG_HEADER in existing_note:
            skipped_count += 1
            continue

        if existing_note.strip():
            new_note = existing_note.strip() + "\n\n" + STRENGTHLOG_HEADER + "\n" + summary
        else:
            new_note = STRENGTHLOG_HEADER + "\n" + summary

        activity["privateNote"] = new_note
        merged_count += 1

    elif len(matches) == 0:
        activities.append({
            "activityId": None,
            "activityName": workout["name"],
            "startTimeLocal": workout["date"] + " " + workout["start_time"] + ":00",
            "startTimeGMT": workout["date"] + " " + workout["start_time"] + ":00",
            "type": "WeightTraining",
            "sportType": "WeightTraining",
            "workoutType": None,
            "distance": 0.0,
            "movingDuration": workout["duration_minutes"] * 60,
            "elapsedDuration": workout["duration_minutes"] * 60,
            "elevationGain": 0,
            "averageSpeed": 0.0,
            "averageHR": None,
            "maxHR": None,
            "sufferScore": None,
            "averageRunningCadenceInStepsPerMinute": None,
            "publicDescription": "",
            "privateNote": STRENGTHLOG_HEADER + "\n" + summary,
            "flags": {"commute": False, "trainer": False, "manual": True, "private": False},
            "hasPhotos": False,
            "hasMap": False
        })
        created_count += 1

    else:
        print(f"WARNING multiple matches: {workout_date}")

from datetime import datetime

def parse_dt(a):
    return datetime.strptime(a["startTimeLocal"], "%Y-%m-%d %H:%M:%S")

activities.sort(key=parse_dt, reverse=True)

# ---------- SAVE ----------
with open(ACTIVITIES_PATH, "w", encoding="utf-8") as f:
    json.dump(activities, f, indent=2, ensure_ascii=False)

if merged_count or created_count:
    print("Strengthlog merge summary:")
    print(f"Merged: {merged_count}")
    print(f"Created: {created_count}")
print("Done merging Strengthlog into activities.json")