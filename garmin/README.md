# Garmin Personal API – Weight Export

This module retrieves body-weight measurements from Garmin Connect using
Garmin's Personal API. The raw measurement history is stored as JSON at
`garmin/data/weight-measurements.json`.

## Data handling

The JSON contains Garmin's original measurement records, including their
timestamps/dates and measurement fields. We deliberately preserve the raw
weigh-ins at this stage rather than averaging or interpolating them.

A later processing step will produce one daily value:
- Multiple weigh-ins on one calendar day: arithmetic mean.
- Missing days between actual weigh-ins: linear interpolation between the
  neighbouring daily observations.
- Days before the first or after the last actual weigh-in: leave missing; do
  not extrapolate.

The daily series should retain metadata identifying measured, averaged, and
interpolated values, so derived values are never confused with actual weigh-ins.

## Security

This repository is public, and the user has explicitly chosen to publish the
weight history alongside the training archive. The Garmin API key and bearer
tokens remain private and must only be stored in GitHub Actions secrets.
Never commit credentials.

## GitHub setup

1. Open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `GARMIN_PERSONAL_API_KEY`.
3. Paste the Garmin Personal API key into the secret value.

## Run the export

The **Garmin Weight Export** workflow can be started manually from the Actions
tab. Its default start date is 2012-01-01; the end date defaults to today.
It also runs automatically once per day.

The workflow fetches bounded date windows, merges the raw records, and commits
the resulting JSON only when it changes.

## Local use

Install dependencies:

```bash
python -m pip install -r garmin/requirements.txt
```

Set `GARMIN_PERSONAL_API_KEY` in your environment, then run:

```bash
python garmin/export_weight.py --start-date 2012-01-01
```

By default, the output is written to
`garmin/data/weight-measurements.json`.
