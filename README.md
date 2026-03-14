# Strava Training Export

Automated export of my training data from **Strava + StrengthLog** to:

* JSON archive
* HTML training log
* ICS calendar feed

Runs automatically every night via **GitHub Actions**.

Main goal: keep a **complete personal training archive outside Strava** and display activities in **Google Calendar**.

---

# Overview

Pipeline:

```
Strava API
    ↓
export_strava_activities.py
    ↓
activities.json (training archive)
    ↓
strengthlog-to-json.py
    ↓
json-to-html.py
json-to-ics.py
    ↓
activities.html (training log)
activities.ics (calendar feed)
```

GitHub Actions runs the pipeline nightly and commits updated files back to the repository.

---

# Files in this repository

## export_strava_activities.py

Exports activities from the **Strava API**.

Features:

* refreshes OAuth token automatically
* handles API rate limits
* waits if limit is reached
* incremental export (only adds missing activities)
* saves progress every 25 activities

Output:

```
activities.json
```

This file becomes the **main training database**.

---

## strengthlog-to-json.py

Imports **StrengthLog CSV export** and merges strength workouts into the JSON dataset.

Strength sessions then appear in:

* HTML log
* calendar feed

---

## json-to-html.py

Generates a readable training log:

```
activities.html
```

Features:

* activity icons
* stats
* public + private notes
* basic formatting

Available at:

```
https://carlydergard.github.io/strava-export/activities.html
```

---

## json-to-ics.py

Creates an iCalendar feed:

```
activities.ics
```

Used to show all training sessions in **Google Calendar**.

Calendar URL:

```
https://raw.githubusercontent.com/carlydergard/strava-export/main/activities.ics
```

---

# Strava API Setup

The script uses the **Strava API**.

Authentication requires:

```
CLIENT_ID
CLIENT_SECRET
REFRESH_TOKEN
```

These are stored securely as **GitHub repository secrets**.

Secrets used:

```
STRAVA_CLIENT_ID
STRAVA_CLIENT_SECRET
STRAVA_REFRESH_TOKEN
```

Flow:

```
refresh_token
    ↓
request new access_token
    ↓
use access_token for API calls
```

Access tokens expire quickly, but refresh tokens remain valid.

---

# API Rate Limits

Strava limits:

```
100 requests / 15 minutes
1000 requests / day
```

The script:

* tracks API usage
* waits automatically if limits are reached
* resumes when allowed

This prevents pipeline failures.

---

# Updating StrengthLog Data

StrengthLog workouts are **not available via API**, so they must be exported manually.

Steps:

1. Open StrengthLog
2. Request CSV export
3. Download file
4. Replace:

```
strengthlog.csv
```

in the repository.

The next GitHub Actions run will automatically include the new data.

---

# GitHub Automation

Automation is handled by:

```
.github/workflows/strava.yml
```

Runs:

```
daily at 03:00 UTC
```

Pipeline:

```
export_strava_activities.py
strengthlog-to-json.py
json-to-html.py
json-to-ics.py
```

Updated files are committed automatically.

---

# Data Outputs

Training archive:

```
https://raw.githubusercontent.com/carlydergard/strava-export/main/activities.json
```

Calendar feed:

```
https://raw.githubusercontent.com/carlydergard/strava-export/main/activities.ics
```

Training log:

```
https://carlydergard.github.io/strava-export/activities.html
```

---

# Notes

* Designed primarily for **personal use**
* Built to avoid losing training notes if Strava changes APIs
* Allows viewing training history in **Google Calendar**

---

# Credits

Initial implementation created with help from **ChatGPT**.
