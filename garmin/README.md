# Garmin Personal API – Weight Export

This is a separate module from the Strava export pipeline. It retrieves body-weight
measurements from Garmin Connect using Garmin's Personal API.

## Security

The parent `strava-export` repository is public. **Never commit weight JSON,
Garmin API keys, or bearer tokens to this repository.** Local output is ignored by
Git. The GitHub Actions workflow writes its temporary output to the runner and
does not upload or commit it.

## GitHub setup

1. In the repository, open **Settings → Secrets and variables → Actions**.
2. Add a repository secret named `GARMIN_PERSONAL_API_KEY`.
3. Paste the Garmin Personal API key into the secret value. Do not put it in a
   workflow file, issue, commit, or chat.

## Run the test/export

1. Open **Actions → Garmin Weight Export → Run workflow**.
2. Choose a start date (default: 2020-01-01). The end date defaults to today.
3. Run the workflow.

The workflow reports whether authentication and the weight endpoint succeeded,
plus a record count. It deliberately does not print body measurements.

## Local use

Install the module dependencies:

```bash
python -m pip install -r garmin/requirements.txt
```

Set `GARMIN_PERSONAL_API_KEY` in your environment, then run:

```bash
python garmin/export_weight.py --start-date 2020-01-01
```

The JSON is written to `garmin/data/weight-measurements.json`, which is
Git-ignored. Keep that file private.

## Data persistence

The GitHub Actions run is currently a connection/extraction test. It does not
persist the JSON because this repository is public and weight is sensitive
personal data. Once the endpoint is verified, choose a private destination
before enabling automatic daily storage.
