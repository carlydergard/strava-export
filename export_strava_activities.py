import os
import json
import time
import requests
import reverse_geocoder as rg
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# ================= CONFIG =================

PROGRESS_FILE = "progress.json"
OUTPUT_JSON = "activities.json"
MAX_NEW_ACTIVITIES = None     # set to None to export everything
SAVE_EVERY = 25               # checkpoint frequency

START_TIME = time.time()
MAX_RUNTIME = 5.5 * 3600  # 5.5 timmar

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
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


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

# ================= PROGRESS TRACKING REBUILD =================

def save_page_progress(page):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"page": page}, f)

# ================= LOCATION =================

location_cache = {}
unknown_places = set()

try:
    with open("city_fixes.json", "r", encoding="utf-8") as f:
        CITY_FIXES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("⚠️ city_fixes.json missing or invalid - using empty fixes")
    CITY_FIXES = {}

def normalize_city_name(name):
    return CITY_FIXES.get(name, name)

def get_location_name(lat, lon):
    try:
        key = (round(lat, 3), round(lon, 3))

        if key not in location_cache:
            result = rg.search([(lat, lon)])[0]
            raw_city = result.get("name")
            if raw_city and ("oe" in raw_city or "ae" in raw_city or "aa" in raw_city):
                if raw_city not in unknown_places:
                    print(f"⚠️ Possible fix needed: {raw_city}")
                    unknown_places.add(raw_city)
            city = normalize_city_name(raw_city) if raw_city else None
            country = result.get("cc")

            if city and country:
                location_cache[key] = f"{city} {country}"
            elif country:
                location_cache[key] = country
            else:
                location_cache[key] = None

        return location_cache[key]

    except Exception as e:
        print(f"⚠️ Geocoding error: {e}")
        return None

# ================= FETCH =================

if os.path.exists(PROGRESS_FILE):
    try:
        with open(PROGRESS_FILE, "r") as f:
            progress = json.load(f)
        page = progress.get("page", 1)
        print(f"🔁 Resuming from page {page}")
    except Exception:
        print("⚠️ progress.json invalid, starting from page 1")
        page = 1
else:
    page = 1
    
per_page = 50
new_count = 0

print("📥 Exporting Strava activities…")

while True:

    if time.time() - START_TIME > MAX_RUNTIME:
        print("⏰ Max runtime reached, stopping early to allow commit...")
        save_progress()
        save_page_progress(page)
        break
    
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
        save_page_progress(page)

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

        print("🌙 Daily API limit reached, stopping for today...")

        save_progress()
        save_page_progress(page)

        break

    if short_u >= 95:

        save_progress()
        save_page_progress(page)

        reset_ts = int(r.headers.get("X-RateLimit-Reset", time.time() + 900))
        countdown(max(reset_ts - int(time.time()), 0))
        continue

    batch = r.json()

    if not batch:
        break

    for act in batch:

        if time.time() - START_TIME > MAX_RUNTIME:
            print("⏰ Max runtime reached mid-batch, stopping...")
            save_progress()
            save_page_progress(page)
            break

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
                save_page_progress(page)

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

        start_latlng = act.get("start_latlng")
        if start_latlng and len(start_latlng) == 2:
            lat, lon = start_latlng
            entry["startLat"] = lat
            entry["startLng"] = lon

            location_name = get_location_name(lat, lon)
            if location_name:
                entry["locationName"] = location_name
        
        activities.append(entry)
        exported_ids.add(act_id)
        new_count += 1

        print(f"✅ Exported {entry['activityName']} ({entry['startTimeLocal']})")

        if new_count % SAVE_EVERY == 0:
            save_progress()
            save_page_progress(page)

        time.sleep(1)

    if MAX_NEW_ACTIVITIES is not None and new_count >= MAX_NEW_ACTIVITIES:
        break
        
    page += 1
    save_page_progress(page)


# ================= FINAL SAVE =================

save_progress()

print("\n🎉 Done!")
print(f"   New activities added: {new_count}")
print(f"   Total activities: {len(activities)}")

if os.path.exists(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)
    print("🧹 Progress file cleared (export complete)")
