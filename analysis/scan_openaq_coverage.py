
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "enriched_weather.csv"
OUTPUT = ROOT / "analysis" / "output" / "openaq_coverage.csv"
SUMMARY = ROOT / "analysis" / "output" / "openaq_coverage_summary.json"

BASE_URL = "https://api.openaq.org/v3"
RADIUS = 25000
REQUEST_DELAY = 1.1

def load_key():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == "OPENAQ_API_KEY":
                return value.strip().strip('"').strip("'")
    raise RuntimeError("OPENAQ_API_KEY not found in .env")

API_KEY = load_key()

def api_get(path, params=None):
    url = BASE_URL + path
    if params:
        url += "?" + urlencode(params)

    req = Request(url, headers={"X-API-Key": API_KEY})

    for attempt in range(4):
        try:
            with urlopen(req, timeout=40) as response:
                return json.loads(response.read())

        except HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                time.sleep(3 * (attempt + 1))
                continue
            raise

        except (URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))

    raise RuntimeError("API retries exhausted")

def main():
    df = pd.read_csv(INPUT)

    cities = (
        df[["location_name", "country", "latitude", "longitude"]]
        .dropna()
        .drop_duplicates(subset=["location_name", "country"])
        .copy()
    )

    cities["latitude"] = cities["latitude"].round(4)
    cities["longitude"] = cities["longitude"].round(4)

    unique_coordinates = cities[
        ["latitude", "longitude"]
    ].drop_duplicates()

    print("City-country pairs:", len(cities))
    print("Unique coordinate pairs:", len(unique_coordinates))

    results = []
    cache = {}

    for number, (_, city) in enumerate(cities.iterrows(), start=1):
        lat = float(city["latitude"])
        lon = float(city["longitude"])
        coordinate_key = (lat, lon)

        print(
            f"[{number}/{len(cities)}] "
            f"{city['location_name']}, {city['country']}",
            flush=True
        )

        if coordinate_key not in cache:
            try:
                payload = api_get(
                    "/locations",
                    {
                        "coordinates": f"{lat},{lon}",
                        "radius": RADIUS,
                        "limit": 1000,
                        "page": 1
                    }
                )

                cache[coordinate_key] = payload.get("results", [])
                time.sleep(REQUEST_DELAY)

            except Exception as exc:
                cache[coordinate_key] = None
                print("  API ERROR:", type(exc).__name__, str(exc))

        stations = cache[coordinate_key]

        if stations is None:
            results.append({
                "city": city["location_name"],
                "country": city["country"],
                "latitude": lat,
                "longitude": lon,
                "status": "api_error"
            })
            continue

        if not stations:
            results.append({
                "city": city["location_name"],
                "country": city["country"],
                "latitude": lat,
                "longitude": lon,
                "station_count": 0,
                "status": "no_station_found"
            })
            continue

        for station in stations:
            first = station.get("datetimeFirst") or {}
            last = station.get("datetimeLast") or {}

            sensors = station.get("sensors", [])

            for sensor in sensors:
                parameter = sensor.get("parameter") or {}

                results.append({
                    "city": city["location_name"],
                    "country": city["country"],
                    "latitude": lat,
                    "longitude": lon,
                    "station_id": station.get("id"),
                    "station_name": station.get("name"),
                    "station_distance_m": station.get("distance"),
                    "sensor_id": sensor.get("id"),
                    "pollutant": parameter.get("name"),
                    "unit": parameter.get("units"),
                    "first_measurement": first.get("utc"),
                    "last_measurement": last.get("utc"),
                    "overlaps_weather_period": (
                        bool(first.get("utc"))
                        and bool(last.get("utc"))
                        and first["utc"][:10] <= "2026-10-13"
                        and last["utc"][:10] >= "2024-05-16"
                    ),
                    "status": "station_found"
                })

    output = pd.DataFrame(results)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)

    station_rows = output[
        output["station_id"].notna()
    ] if "station_id" in output else pd.DataFrame()

    overlap = (
        station_rows[station_rows["overlaps_weather_period"] == True]
        if not station_rows.empty
        else pd.DataFrame()
    )

    summary = {
        "city_country_pairs": int(len(cities)),
        "unique_coordinate_pairs": int(len(unique_coordinates)),
        "locations_with_stations": int(
            output.loc[
                output["status"] == "station_found",
                ["city", "country"]
            ].drop_duplicates().shape[0]
        ),
        "locations_without_stations": int(
            output.loc[
                output["status"] == "no_station_found",
                ["city", "country"]
            ].drop_duplicates().shape[0]
        ),
        "api_error_rows": int((output["status"] == "api_error").sum()),
        "station_sensor_rows": int(len(station_rows)),
        "sensors_overlapping_weather_period": int(len(overlap)),
        "pollutants_found": (
            sorted(station_rows["pollutant"].dropna().unique().tolist())
            if not station_rows.empty else []
        ),
        "weather_period": ["2024-05-16", "2026-10-13"],
        "radius_m": RADIUS
    }

    SUMMARY.write_text(json.dumps(summary, indent=2))

    print("\nCOVERAGE SUMMARY")
    print(json.dumps(summary, indent=2))
    print("\nSaved:", OUTPUT)
    print("Saved:", SUMMARY)

if __name__ == "__main__":
    main()
