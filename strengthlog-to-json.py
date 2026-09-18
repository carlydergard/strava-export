import os
import pandas as pd
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# ================= CONFIG =================
CSV_PATH = "strengthlog-export.csv"
ACTIVITIES_PATH = "activities.json"
PROGRESS_PATH = "progress.json"
CHINS_PATH = "chins_2018_2019.json"
HISTORICAL_CHINS_SOURCE = "historical_chins"

BODYWEIGHT = 75
BODYWEIGHT_EXERCISES = ["Chins", "Pullups", "Dips"]
STRENGTHLOG_HEADER = "=== Strengthlog ==="
# ==========================================


# ---------- CHECK REQUIRED FILES ----------

if not os.path.exists(CSV_PATH):
    print(f"StrengthLog file not found: {CSV_PATH}")
    print("Skipping StrengthLog merge.")
    raise SystemExit(0)

if not os.path.exists(ACTIVITIES_PATH):
    print(f"Activities file not found: {ACTIVITIES_PATH}")
    print("Skipping StrengthLog merge.")
    raise SystemExit(0)


# ---------- CHECK STRAVA EXPORT STATUS ----------

# progress.json exists while the Strava export is still incomplete.
# In that case we must NOT create synthetic StrengthLog activities,
# because Strava may simply not have reached those dates yet.

strava_export_incomplete = os.path.exists(PROGRESS_PATH)

if strava_export_incomplete:
    print("Strava export is still in progress.")
    print("StrengthLog will only merge with existing Strava activities.")
    print("No synthetic activities will be created this run.")
else:
    print("Strava export appears complete.")
    print("StrengthLog may create synthetic activities when no Strava activity exists.")


# ---------- LOAD CSV ----------

df = pd.read_csv(CSV_PATH)

df["start_dt"] = (
    pd.to_datetime(df["start"], unit="ms", utc=True)
    .dt.tz_convert("Europe/Stockholm")
)

df["end_dt"] = (
    pd.to_datetime(df["end"], unit="ms", utc=True)
    .dt.tz_convert("Europe/Stockholm")
)


# ---------- BUILD STRENGTHLOG WORKOUTS ----------

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

            if float(weight).is_integer():
                weight_list.append(str(int(weight)))
            else:
                weight_list.append(str(weight))

            total_volume += reps * weight

        # If no meaningful reps/weights → just show exercise name
        # (e.g. planks)
        if all(r == "0" for r in reps_list) and all(
            w in ["0", "0.0"] for w in weight_list
        ):
            summary_lines.append(exercise)
        else:
            reps_str = "-".join(reps_list) + " reps"
            weight_str = ", " + "-".join(weight_list) + " kg"
            summary_lines.append(f"{exercise} {reps_str}{weight_str}")

    summary_lines.append(f"Totalvolym: {int(total_volume)} kg")

    workouts.append({
        "date": start_dt.strftime("%Y-%m-%d"),
        "start_time": start_dt.strftime("%H:%M"),
        "duration_minutes": int(
            (end_dt - start_dt).total_seconds() / 60
        ),
        "name": workout_name,
        "summary": "\n".join(summary_lines)
    })


# Newest first
workouts.sort(
    key=lambda x: (x["date"], x["start_time"]),
    reverse=True
)


# ---------- LOAD ACTIVITIES ----------

with open(ACTIVITIES_PATH, "r", encoding="utf-8") as f:
    activities = json.load(f)
    
def is_strengthlog_activity(activity):
    """
    Identifies synthetic activities previously created by this script.
    These have activityId=None and contain the StrengthLog header.
    """
    return (
        activity.get("activityId") is None
        and STRENGTHLOG_HEADER in (activity.get("privateNote", "") or "")
    )


def is_real_strava_weight_activity(activity):
    """
    Identifies a real Strava WeightTraining activity.
    """
    return (
        activity.get("activityId") is not None
        and activity.get("sportType", "") == "WeightTraining"
    )


# ---------- LOAD HISTORICAL CHINS ----------

historical_chins = []

if os.path.exists(CHINS_PATH):
    with open(CHINS_PATH, "r", encoding="utf-8") as f:
        chins_data = json.load(f)

    historical_chins = chins_data.get("sessions", [])

    print(f"Loaded {len(historical_chins)} historical chin sessions.")
else:
    print("Historical chins file not found. Skipping.")

def get_date(dt_string):
    return dt_string.split(" ")[0]

def is_historical_chins_activity(activity):
    return activity.get("source") == HISTORICAL_CHINS_SOURCE

def has_chins_in_strengthlog(activity):
    """
    Checks whether a real Strava activity contains imported
    StrengthLog data with Chins as an exercise.
    """
    note = activity.get("privateNote", "") or ""

    if STRENGTHLOG_HEADER not in note:
        return False

    strengthlog_part = note.split(STRENGTHLOG_HEADER, 1)[1]

    return any(
        line.startswith("Chins ")
        or line == "Chins"
        for line in strengthlog_part.splitlines()
    )

activities = [
    activity
    for activity in activities
    if not is_historical_chins_activity(activity)
]

# ---------- MERGE HISTORICAL CHINS ----------

historical_chins_created = 0
historical_chins_skipped = 0

for session in historical_chins:
    date = session["date"]

    duplicate_strava_matches = [
        activity
        for activity in activities
        if (
            get_date(activity["startTimeLocal"]) == date
            and is_real_strava_weight_activity(activity)
            and has_chins_in_strengthlog(activity)
        )
    ]

    if duplicate_strava_matches:
        historical_chins_skipped += 1
        continue

    sets = session.get("sets", [])
    total_reps = session.get("total_reps")
    bodyweight = session.get("bodyweight_kg")

    set_text = "-".join(
        str(reps) for reps in sets if reps is not None
    )

    summary = (
        "Historiska chins från CHINS 2018_2019.xlsx\n\n"
        f"Chins: {set_text} reps\n"
        f"Totalt: {total_reps} reps\n"
        f"Kroppsvikt: {bodyweight} kg"
    )

    activities.append({
        "activityId": None,
        "activityName": "Chins",
        "startTimeLocal": date,
        "startTimeGMT": None,
        "type": "WeightTraining",
        "sportType": "WeightTraining",
        "workoutType": None,

        "distance": 0.0,
        "movingDuration": None,
        "elapsedDuration": None,

        "elevationGain": 0,
        "averageSpeed": 0.0,
        "averageHR": None,
        "maxHR": None,
        "sufferScore": None,
        "averageRunningCadenceInStepsPerMinute": None,

        "publicDescription": "",
        "privateNote": summary,

        "source": HISTORICAL_CHINS_SOURCE,

        "dateOnly": True,
        "calendarEligible": False,

        "flags": {
            "commute": False,
            "trainer": False,
            "manual": True,
            "private": False
        },

        "hasPhotos": False,
        "hasMap": False
    })

    historical_chins_created += 1

print("Historical chins:")
print(f"  Imported: {historical_chins_created}")
print(f"  Skipped as duplicate of Strava activity: {historical_chins_skipped}")


# ---------- MERGE ----------

merged_count = 0
created_count = 0
skipped_count = 0
replaced_synthetic_count = 0


for workout in workouts:
    workout_date = workout["date"]
    summary = workout["summary"]

    # Find all WeightTraining activities on this date.
    matches = []

    for activity in activities:
        activity_date = get_date(activity["startTimeLocal"])
        activity_type = activity.get("sportType", "")

        if (
            activity_date == workout_date
            and activity_type == "WeightTraining"
        ):
            matches.append(activity)

    # Separate real Strava activities from synthetic StrengthLog
    # activities that may have been created by an earlier run.
    real_matches = [
        activity
        for activity in matches
        if is_real_strava_weight_activity(activity)
    ]

    synthetic_matches = [
        activity
        for activity in matches
        if is_strengthlog_activity(activity)
    ]


    # ============================================================
    # CASE 1: EXACTLY ONE REAL STRAVA ACTIVITY
    # ============================================================

    if len(real_matches) == 1:

        activity = real_matches[0]
        existing_note = activity.get("privateNote", "") or ""

        # If StrengthLog has already been merged into the real
        # Strava activity, nothing more needs to be done.
        if STRENGTHLOG_HEADER in existing_note:
            skipped_count += 1

        else:
            if existing_note.strip():
                new_note = (
                    existing_note.strip()
                    + "\n\n"
                    + STRENGTHLOG_HEADER
                    + "\n"
                    + summary
                )
            else:
                new_note = (
                    STRENGTHLOG_HEADER
                    + "\n"
                    + summary
                )

            activity["privateNote"] = new_note
            merged_count += 1

        # --------------------------------------------------------
        # If an old synthetic StrengthLog activity exists for the
        # same workout, remove it now that the real Strava activity
        # has arrived.
        # --------------------------------------------------------

        if synthetic_matches:
            for synthetic in synthetic_matches:
                activities.remove(synthetic)
                replaced_synthetic_count += 1


    # ============================================================
    # CASE 2: NO REAL STRAVA ACTIVITY
    # ============================================================

    elif len(real_matches) == 0:

        # If a synthetic activity already exists, leave it alone.
        # This prevents duplicate synthetic activities.
        if synthetic_matches:
            skipped_count += 1
            continue

        # --------------------------------------------------------
        # If Strava export is incomplete, DO NOT create a synthetic
        # activity. Strava may simply not have reached this date yet.
        #
        # The next day's run will try again after Strava has
        # continued exporting.
        # --------------------------------------------------------

        if strava_export_incomplete:
            skipped_count += 1
            print(
                f"Waiting for Strava activity: "
                f"{workout_date} {workout['start_time']} "
                f"({workout['name']})"
            )
            continue

        # --------------------------------------------------------
        # Strava export is complete and no matching activity exists.
        # Now it is safe to create a synthetic StrengthLog activity.
        # --------------------------------------------------------

        activities.append({
            "activityId": None,
            "activityName": workout["name"],
            "startTimeLocal": (
                workout["date"]
                + " "
                + workout["start_time"]
                + ":00"
            ),
            "startTimeGMT": (
                workout["date"]
                + " "
                + workout["start_time"]
                + ":00"
            ),
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
            "privateNote": (
                STRENGTHLOG_HEADER
                + "\n"
                + summary
            ),
            "flags": {
                "commute": False,
                "trainer": False,
                "manual": True,
                "private": False
            },
            "hasPhotos": False,
            "hasMap": False
        })

        created_count += 1


    # ============================================================
    # CASE 3: MULTIPLE REAL STRAVA ACTIVITIES
    # ============================================================

    else:
        print(
            f"WARNING multiple real Strava matches: "
            f"{workout_date} ({len(real_matches)} activities)"
        )


# ---------- SORT ----------

def parse_dt(activity):
    value = activity["startTimeLocal"]

    if len(value) == 10:
        return datetime.strptime(value, "%Y-%m-%d")

    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


activities.sort(key=parse_dt, reverse=True)


# ---------- SAVE ----------

with open(ACTIVITIES_PATH, "w", encoding="utf-8") as f:
    json.dump(
        activities,
        f,
        indent=2,
        ensure_ascii=False
    )


# ---------- SUMMARY ----------

if (
    merged_count
    or created_count
    or replaced_synthetic_count
):
    print("StrengthLog merge summary:")
    print(f"Merged into Strava: {merged_count}")
    print(f"Created synthetic: {created_count}")
    print(f"Replaced synthetic with Strava: {replaced_synthetic_count}")
    print(f"Skipped: {skipped_count}")

print("Done merging StrengthLog into activities.json")
