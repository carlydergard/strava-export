import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ================= CONFIG =================

OUTPUT_JSON = "activities.json"
MAX_NEW_ACTIVITIES = None     # set to None to export everything
SAVE_EVERY = 25               # checkpoint frequency

CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]
refresh_token = os.environ["STRAVA_REFRESH_TOKEN"]

access_token = None

# ==========================================

def refresh_access_token():
    global access_token, refresh_token

    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    )

    r.raise_for_status()
    data = r.json()

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    print("🔑 Tokens refreshed successfully.")

LOCAL_TZ = ZoneInfo("Europe/Stockholm")

def countdown(seconds):
    end_utc = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    end_local = end_utc.astimezone(LOCAL_TZ)
    mins = seconds // 60
    secs = seconds % 60
    print(f"⏳ Waiting {mins}m {secs}s (until {end_local:%H:%M:%S} local / {end_utc:%H:%M:%S} UTC)")
    time.sleep(seconds)

    print()


def iso_to_local(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")


def workout_type_label(v):
    return {
        1: "race",
        2: "long_run",
        3: "workout"
    }.get(v, None)


# ----------- SORTING HELPERS -----------

def sort_activities():
    activities.sort(
        key=lambda a: datetime.strptime(
            a["startTimeLocal"], "%Y-%m-%d %H:%M:%S"
        ),
        reverse=True
    )


def save_progress():
    sort_activities()

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(activities, f, ensure_ascii=False, indent=2)

    print(f"💾 Progress saved ({len(activities)} activities)")


# ================= LOAD STATE =================

refresh_access_token()

headers = {"Authorization": f"Bearer {access_token}"}

activities = []
exported_ids = set()

if os.path.exists(OUTPUT_JSON):

    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        activities = json.load(f)

    exported_ids = {str(a["activityId"]) for a in activities}

print(f"📂 Existing activities: {len(exported_ids)}")

# ================= FETCH =================

page = 1
per_page = 50
new_count = 0

print("📥 Exporting Strava activities…")

while True:

    r = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers=headers,
        params={"page": page, "per_page": per_page}
    )

    if r.status_code == 401:
        refresh_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        continue

    if r.status_code == 429:
        save_progress()

        reset_ts = int(r.headers.get("X-RateLimit-Reset", time.time() + 900))
        wait_time = max(reset_ts - int(time.time()), 0)

        print(f"⚠️ Rate limit hit on list fetch. Waiting {wait_time//60} min…")
        countdown(wait_time)
        continue

    r.raise_for_status()

    usage = r.headers.get("X-RateLimit-Usage", "0,0")
    short_u, daily_u = map(int, usage.split(","))

    print(f"🛑 API limits | short: {short_u}/100 | daily: {daily_u}/1000")

    if daily_u >= 950:

        save_progress()

        now = datetime.now(timezone.utc)
        reset = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)

        countdown(int((reset - now).total_seconds()))

        refresh_access_token()
        headers["Authorization"] = f"Bearer {access_token}"
        continue

    if short_u >= 95:

        save_progress()

        reset_ts = int(r.headers.get("X-RateLimit-Reset", time.time() + 900))
        countdown(max(reset_ts - int(time.time()), 0))
        continue

    batch = r.json()

    if not batch:
        break

    for act in batch:

        if MAX_NEW_ACTIVITIES is not None and new_count >= MAX_NEW_ACTIVITIES:
            print("🛑 Test limit reached, stopping early.")
            save_progress()
            break

        act_id = str(act["id"])

        if act_id in exported_ids:
            continue

        # ---------- DETAIL FETCH ----------

        while True:

            detail = requests.get(
                f"https://www.strava.com/api/v3/activities/{act_id}",
                headers=headers
            )

            if detail.status_code == 401:
                refresh_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                continue

            if detail.status_code == 429:

                save_progress()

                reset_ts = int(detail.headers.get("X-RateLimit-Reset", time.time() + 900))
                wait_time = max(reset_ts - int(time.time()), 0)

                print(f"⚠️ Rate limit hit on detail fetch. Waiting {wait_time//60} min…")
                countdown(wait_time)
                continue

            detail.raise_for_status()
            break

        d = detail.json()

        entry = {
            "activityId": act["id"],
            "activityName": act.get("name"),
            "startTimeLocal": iso_to_local(act["start_date_local"]),
            "startTimeGMT": iso_to_local(act["start_date"]),
            "type": act.get("type"),
            "sportType": act.get("sport_type"),
            "workoutType": workout_type_label(act.get("workout_type")),

            "distance": act.get("distance"),
            "movingDuration": act.get("moving_time"),
            "elapsedDuration": act.get("elapsed_time"),
            "elevationGain": act.get("total_elevation_gain"),
            "averageSpeed": act.get("average_speed"),

            "averageHR": act.get("average_heartrate"),
            "maxHR": act.get("max_heartrate"),
            "sufferScore": act.get("suffer_score"),

            "averageRunningCadenceInStepsPerMinute":
                int(act["average_cadence"] * 2) if act.get("average_cadence") else None,

            "publicDescription": d.get("description"),
            "privateNote": d.get("private_note"),

            "flags": {
                "commute": act.get("commute"),
                "trainer": act.get("trainer"),
                "manual": act.get("manual"),
                "private": act.get("private")
            },

            "hasPhotos": act.get("photo_count", 0) > 0,
            "hasMap": bool(act.get("map", {}).get("summary_polyline"))
        }

        activities.append(entry)
        exported_ids.add(act_id)
        new_count += 1

        print(f"✅ Exported {entry['activityName']} ({entry['startTimeLocal']})")

        if new_count % SAVE_EVERY == 0:
            save_progress()

        time.sleep(1)

    if MAX_NEW_ACTIVITIES is not None and new_count >= MAX_NEW_ACTIVITIES:
        break

    page += 1

# ================= FINAL SAVE =================

save_progress()

print("\n🎉 Done!")
print(f"   New activities added: {new_count}")
print(f"   Total activities: {len(activities)}")
