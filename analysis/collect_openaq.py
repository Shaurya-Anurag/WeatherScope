
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "analysis/output/openaq_coverage.csv"
RAW = ROOT / "data/openaq_daily_raw.csv"
CLEAN = ROOT / "data/openaq_daily_clean.csv"
CITY = ROOT / "data/openaq_city_daily.csv"
STATE = ROOT / "data/openaq_checkpoint.json"
SUMMARY = ROOT / "analysis/output/openaq_collection_summary.json"

BASE_URL = "https://api.openaq.org/v3"
DATE_FROM = "2024-05-16"
DATE_TO = "2026-10-13"

POLLUTANTS = {"pm25", "pm10", "no2", "so2", "o3", "co"}
MIN_COVERAGE = 75.0
PAGE_SIZE = 1000
DELAY = 0.25


def load_api_key():
    key = os.environ.get("OPENAQ_API_KEY")
    if key:
        return key

    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                if name.strip() == "OPENAQ_API_KEY":
                    return value.strip().strip('"').strip("'")

    raise RuntimeError("OPENAQ_API_KEY not found in .env")


API_KEY = load_api_key()


def save_state(completed, failures):
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "completed_sensor_ids": sorted(completed),
        "failures": failures
    }, indent=2))
    temporary.replace(STATE)


def api_get(path, params):
    url = BASE_URL + path + "?" + urlencode(params)
    request = Request(url, headers={"X-API-Key": API_KEY})

    for attempt in range(6):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read())

        except HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(60, 2 ** (attempt + 1))
                print(f"  HTTP {exc.code}; retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise

        except (URLError, TimeoutError):
            if attempt == 5:
                raise
            time.sleep(min(60, 2 ** (attempt + 1)))

    raise RuntimeError("API retries exhausted")


def fetch_sensor(sensor_id):
    records = []
    page = 1

    while True:
        payload = api_get(
            f"/sensors/{sensor_id}/days",
            {
                "date_from": DATE_FROM,
                "date_to": DATE_TO,
                "limit": PAGE_SIZE,
                "page": page
            }
        )

        batch = payload.get("results") or []
        records.extend(batch)

        found = (payload.get("meta") or {}).get("found")

        if not batch:
            break

        # If the API supplies the total, use it.
        if found is not None:
            if len(records) >= int(found):
                break
        # Otherwise, a short page means there are no more results.
        elif len(batch) < PAGE_SIZE:
            break

        page += 1
        time.sleep(DELAY)

    return records


def record_date(record):
    period = record.get("period") or {}
    start = period.get("datetimeFrom") or {}
    value = start.get("local") or start.get("utc")

    if not value:
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def make_rows(sensor, records):
    rows = []

    for record in records:
        parameter = record.get("parameter") or {}
        coverage = record.get("coverage") or {}
        flags = record.get("flagInfo") or {}
        summary = record.get("summary") or {}

        rows.append({
            "sensor_id": sensor["sensor_id"],
            "station_id": sensor.get("station_id"),
            "city": sensor.get("city"),
            "country": sensor.get("country"),
            "station_distance_m": sensor.get("station_distance_m"),
            "pollutant": parameter.get("name") or sensor.get("pollutant"),
            "unit": parameter.get("units") or sensor.get("unit"),
            "date": record_date(record),
            "value": record.get("value"),
            "coverage_pct": (
                coverage.get("percentComplete")
                if coverage.get("percentComplete") is not None
                else coverage.get("percentCoverage")
            ),
            "observed_count": coverage.get("observedCount"),
            "expected_count": coverage.get("expectedCount"),
            "has_flags": flags.get("hasFlags") is True,
            "summary_min": summary.get("min"),
            "summary_max": summary.get("max"),
            "summary_median": summary.get("median"),
            "summary_sd": summary.get("sd")
        })

    return rows


def main():
    inventory = pd.read_csv(INPUT)

    inventory = inventory[
        inventory["pollutant"].isin(POLLUTANTS)
        & inventory["sensor_id"].notna()
    ].copy()

    inventory["sensor_id"] = inventory["sensor_id"].astype("int64")
    inventory["station_distance_m"] = pd.to_numeric(
        inventory["station_distance_m"], errors="coerce"
    )

    # A sensor can be linked to multiple nearby city coordinates.
    # Choose its nearest city association to avoid duplicating its readings.
    inventory = inventory.sort_values(
        ["sensor_id", "station_distance_m"],
        na_position="last"
    )
    sensors = inventory.drop_duplicates("sensor_id")

    print("Unique sensors in inventory:", len(sensors))

    completed = set()
    failures = []

    if STATE.exists():
        saved = json.loads(STATE.read_text())
        completed = set(map(int, saved.get("completed_sensor_ids", [])))
        failures = saved.get("failures", [])


    remaining = sensors[~sensors["sensor_id"].isin(completed)]

    print("Already completed:", len(completed))
    print("Remaining:", len(remaining))

    columns = [
        "sensor_id", "station_id", "city", "country",
        "station_distance_m", "pollutant", "unit", "date",
        "value", "coverage_pct", "observed_count",
        "expected_count", "has_flags", "summary_min",
        "summary_max", "summary_median", "summary_sd"
    ]

    for number, (_, sensor_row) in enumerate(remaining.iterrows(), start=1):
        sensor = sensor_row.to_dict()
        sensor_id = int(sensor["sensor_id"])

        print(
            f"[{len(completed) + 1}/{len(sensors)}] "
            f"Sensor {sensor_id} ({sensor['pollutant']})",
            flush=True
        )

        try:
            records = fetch_sensor(sensor_id)
            rows = make_rows(sensor, records)

            if rows:
                frame = pd.DataFrame(rows, columns=columns)
                frame.to_csv(
                    RAW,
                    mode="a",
                    header=not RAW.exists(),
                    index=False
                )

            # Mark even sensors with zero records as completed.
            completed.add(sensor_id)
            failures = [
                item for item in failures
                if int(item["sensor_id"]) != sensor_id
            ]
            save_state(completed, failures)

        except Exception as exc:
            failures = [
                item for item in failures
                if int(item["sensor_id"]) != sensor_id
            ]
            failures.append({
                "sensor_id": sensor_id,
                "error": type(exc).__name__,
                "message": str(exc)[:300]
            })
            save_state(completed, failures)
            print("  FAILED:", type(exc).__name__, str(exc)[:150])

        time.sleep(DELAY)

    if not RAW.exists():
        raise RuntimeError("No raw measurements were collected.")

    print("\nCollection pass complete. Preparing datasets...")

    raw = pd.read_csv(RAW, on_bad_lines="skip")
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw["coverage_pct"] = pd.to_numeric(
        raw["coverage_pct"], errors="coerce"
    )
    raw["station_distance_m"] = pd.to_numeric(
        raw["station_distance_m"], errors="coerce"
    )

    # Remove duplicate rows that could occur if power failed between
    # writing the raw records and updating the checkpoint.
    raw = raw.drop_duplicates(
        subset=["sensor_id", "pollutant", "date"]
    )

    clean = raw[
        raw["date"].between(DATE_FROM, DATE_TO)
        & raw["value"].notna()
        & raw["value"].ge(0)
        & raw["coverage_pct"].ge(MIN_COVERAGE)
        & ~raw["has_flags"].fillna(False).astype(bool)
    ].copy()

    clean = clean.dropna(
        subset=["city", "country", "station_id", "pollutant", "unit"]
    )

    # First average sensors belonging to the same station.
    station_daily = (
        clean.groupby(
            ["city", "country", "station_id", "date", "pollutant", "unit"],
            dropna=False
        )
        .agg(
            value=("value", "mean"),
            sensor_count=("sensor_id", "nunique"),
            mean_coverage_pct=("coverage_pct", "mean"),
            mean_distance_m=("station_distance_m", "mean")
        )
        .reset_index()
    )

    # Then give each station equal weight in the city-day average.
    city_daily = (
        station_daily.groupby(
            ["city", "country", "date", "pollutant", "unit"],
            dropna=False
        )
        .agg(
            value=("value", "mean"),
            station_count=("station_id", "nunique"),
            sensor_count=("sensor_count", "sum"),
            mean_coverage_pct=("mean_coverage_pct", "mean"),
            mean_distance_m=("mean_distance_m", "mean")
        )
        .reset_index()
    )

    raw.to_csv(RAW, index=False)
    clean.to_csv(CLEAN, index=False)
    city_daily.to_csv(CITY, index=False)

    summary = {
        "source": "OpenAQ API v3",
        "period": [DATE_FROM, DATE_TO],
        "minimum_daily_coverage_pct": MIN_COVERAGE,
        "sensors_in_inventory": int(len(sensors)),
        "sensors_completed": int(len(completed)),
        "sensors_remaining": int(len(sensors) - len(completed)),
        "failed_sensors": int(len(failures)),
        "raw_daily_records": int(len(raw)),
        "quality_filtered_records": int(len(clean)),
        "city_daily_records": int(len(city_daily)),
        "matched_city_country_pairs": int(
            city_daily[["city", "country"]].drop_duplicates().shape[0]
        ),
        "pollutants": sorted(
            city_daily["pollutant"].dropna().unique().tolist()
        ),
        "units_by_pollutant": {
            str(name): sorted(group["unit"].dropna().unique().tolist())
            for name, group in city_daily.groupby("pollutant")
        },
        "failures": failures[:200]
    }

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2))

    print("\nCOLLECTION SUMMARY")
    print(json.dumps(summary, indent=2))
    print("\nSaved files:")
    print(RAW)
    print(CLEAN)
    print(CITY)
    print(SUMMARY)


if __name__ == "__main__":
    main()
