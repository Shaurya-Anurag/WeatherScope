
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "GlobalWeatherRepository-selected-columns.csv"
CACHE = ROOT / "data" / "open_meteo_cache"
ENRICHED_CSV = ROOT / "data" / "enriched_weather.csv"
OUTPUT_JSON = ROOT / "public" / "data" / "weather_enrichment.json"

API_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARIABLES = [
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_mean",
    "precipitation_sum",
    "cloud_cover_mean",
]

# Keep requests paced and retry transient failures.
REQUEST_DELAY_SECONDS = 0.4
MAX_RETRIES = 5


def clean_number(value):
    if pd.isna(value):
        return None
    return float(value)


def fetch_location(lat, lon, start_date, end_date, timezone):
    key = hashlib.sha1(
        f"{lat:.4f}|{lon:.4f}|{start_date}|{end_date}".encode()
    ).hexdigest()
    cache_file = CACHE / f"{key}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if "daily" in cached and "time" in cached["daily"]:
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone if isinstance(timezone, str) and timezone else "auto",
        "wind_speed_unit": "kmh",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=60)
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                raise RuntimeError(result.get("reason", "API returned an error"))

            if not result.get("daily", {}).get("time"):
                raise RuntimeError("API response contained no daily records")

            cache_file.write_text(
                json.dumps(result), encoding="utf-8"
            )
            time.sleep(REQUEST_DELAY_SECONDS)
            return result

        except (requests.RequestException, ValueError, RuntimeError) as exc:
            if attempt == MAX_RETRIES:
                print(f"  FAILED after {MAX_RETRIES} attempts: {exc}")
                return None

            wait = min(2 ** attempt, 20)
            print(f"  Retry {attempt}/{MAX_RETRIES - 1} in {wait}s: {exc}")
            time.sleep(wait)

    return None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    print("Reading source dataset...")
    df = pd.read_csv(INPUT, low_memory=False)

    required = {
        "country", "location_name", "latitude",
        "longitude", "last_updated"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["last_updated"] = pd.to_datetime(df["last_updated"], errors="coerce")
    df["obs_date"] = df["last_updated"].dt.strftime("%Y-%m-%d")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    valid = df.dropna(
        subset=["country", "location_name", "latitude", "longitude", "obs_date"]
    ).copy()

    # One request per unique location, covering its observed date window.
    locations = (
        valid.groupby(
            ["country", "location_name", "latitude", "longitude"],
            dropna=False,
        )
        .agg(
            start_date=("obs_date", "min"),
            end_date=("obs_date", "max"),
            timezone=("timezone", "first"),
        )
        .reset_index()
    )

    daily_records = []
    failed = 0
    total = len(locations)

    print(f"Locations to enrich: {total}")

    for index, loc in locations.iterrows():
        country = str(loc["country"])
        city = str(loc["location_name"])
        lat = float(loc["latitude"])
        lon = float(loc["longitude"])

        print(
            f"[{index + 1}/{total}] {city}, {country} "
            f"({loc['start_date']} to {loc['end_date']})"
        )

        result = fetch_location(
            lat, lon,
            str(loc["start_date"]),
            str(loc["end_date"]),
            loc["timezone"],
        )

        if result is None:
            failed += 1
            continue

        daily = result["daily"]
        for i, date in enumerate(daily["time"]):
            row = {
                "country": country,
                "location_name": city,
                "latitude": lat,
                "longitude": lon,
                "date": date,
            }
            for variable in DAILY_VARIABLES:
                values = daily.get(variable, [])
                row[variable] = (
                    values[i]
                    if i < len(values)
                    else None
                )
            daily_records.append(row)

    if not daily_records:
        raise RuntimeError(
            "No weather data was retrieved. Check the connection and API errors."
        )

    weather = pd.DataFrame(daily_records)
    weather["date"] = pd.to_datetime(weather["date"]).dt.strftime("%Y-%m-%d")

    # Match the API's daily records only to dates present in the source CSV.
    merge_keys = [
        "country", "location_name", "latitude", "longitude", "obs_date"
    ]
    weather_keys = [
        "country", "location_name", "latitude", "longitude", "date"
    ]

    enriched = valid.merge(
        weather,
        left_on=merge_keys,
        right_on=weather_keys,
        how="left",
        suffixes=("", "_open_meteo"),
    )
    enriched.drop(columns=["date"], errors="ignore", inplace=True)
    enriched.to_csv(ENRICHED_CSV, index=False)

    # Country-level summaries for the dashboard.
    countries = {}

    for country, original in valid.groupby("country"):
        original = original.copy()
        matched = enriched[enriched["country"] == country]

        quality = []
        for column in df.columns:
            missing_pct = round(
                float(df.loc[original.index, column].isna().mean() * 100), 2
            )
            quality.append({
                "column": column,
                "missing_pct": missing_pct,
            })

        quality.sort(key=lambda item: item["missing_pct"], reverse=True)

        def mean_of(column):
            if column not in matched:
                return None
            values = pd.to_numeric(matched[column], errors="coerce").dropna()
            return round(float(values.mean()), 2) if len(values) else None

        def count_of(column):
            if column not in matched:
                return 0
            return int(pd.to_numeric(matched[column], errors="coerce").notna().sum())

        loc_rows = []
        for (city, lat, lon), group in matched.groupby(
            ["location_name", "latitude", "longitude"]
        ):
            loc_rows.append({
                "city": str(city),
                "latitude": float(lat),
                "longitude": float(lon),
                "observations": int(len(group)),
                "mean_temp_c": mean_of_from_group(group, "temperature_2m_mean"),
                "mean_humidity_pct": mean_of_from_group(
                    group, "relative_humidity_2m_mean"
                ),
                "mean_wind_kph": mean_of_from_group(
                    group, "wind_speed_10m_mean"
                ),
                "mean_precip_mm": mean_of_from_group(
                    group, "precipitation_sum"
                ),
                "precipitation_records": int(
                    pd.to_numeric(
                        group["precipitation_sum"], errors="coerce"
                    ).notna().sum()
                ),
            })

        countries[str(country)] = {
            "source_observations": int(len(original)),
            "locations": int(original["location_name"].nunique()),
            "date_min": str(original["obs_date"].min()),
            "date_max": str(original["obs_date"].max()),
            "source_mean_temp_c": round(
                float(pd.to_numeric(
                    original["temperature_celsius"], errors="coerce"
                ).mean()), 2
            ),
            "mean_humidity_pct": mean_of("relative_humidity_2m_mean"),
            "mean_wind_kph": mean_of("wind_speed_10m_mean"),
            "mean_precip_mm": mean_of("precipitation_sum"),
            "precipitation_records": count_of("precipitation_sum"),
            "mean_cloud_cover_pct": mean_of("cloud_cover_mean"),
            "data_quality": quality[:10],
            "location_details": loc_rows,
        }

    output = {
        "meta": {
            "source": "Global Weather Repository",
            "enrichment_source": "Open-Meteo Historical Weather API",
            "enrichment_method": "Daily reanalysis matched to source observation dates",
            "wind_speed_unit": "km/h",
            "precipitation_unit": "mm/day",
            "humidity_unit": "%",
            "locations_requested": int(total),
            "locations_failed": int(failed),
            "daily_records_downloaded": int(len(weather)),
            "matched_source_rows": int(
                enriched["temperature_2m_mean"].notna().sum()
            ),
            "note": (
                "Open-Meteo historical values are reanalysis estimates, "
                "not necessarily the original station observations. "
                "Summaries use source dates matched to daily records."
            ),
        },
        "countries": countries,
    }

    OUTPUT_JSON.write_text(
        json.dumps(output, indent=2, allow_nan=False),
        encoding="utf-8",
    )

    print("\nEnrichment finished.")
    print(f"CSV:  {ENRICHED_CSV}")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"Locations failed: {failed}/{total}")
    print(f"Matched source rows: {output['meta']['matched_source_rows']:,}")


def mean_of_from_group(group, column):
    if column not in group:
        return None
    values = pd.to_numeric(group[column], errors="coerce").dropna()
    return round(float(values.mean()), 2) if len(values) else None


if __name__ == "__main__":
    main()
