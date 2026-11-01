
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]

AIR_FILE = ROOT / "data/openaq_city_daily.csv"
WEATHER_FILE = ROOT / "data/enriched_weather.csv"

OUTPUT_DIR = ROOT / "analysis/output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JOINED_FILE = OUTPUT_DIR / "air_quality_weather_join.csv"
CORRELATION_FILE = OUTPUT_DIR / "air_quality_correlations.csv"
COVERAGE_FILE = OUTPUT_DIR / "air_quality_match_summary.json"

WEATHER_VARIABLES = [
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_mean",
    "precipitation_sum",
    "cloud_cover_mean",
]

POLLUTANT_NAMES = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2",
    "so2": "SO2",
    "o3": "O3",
    "co": "CO",
}


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(
        c for c in value if not unicodedata.combining(c)
    )
    value = value.strip().lower()
    return re.sub(r"\s+", " ", value)


def safe_corr(x, y, method):
    valid = pd.DataFrame({"x": x, "y": y}).dropna()

    if len(valid) < 10:
        return np.nan

    if valid["x"].nunique() < 2 or valid["y"].nunique() < 2:
        return np.nan

    if method == "pearson":
        return float(pearsonr(valid["x"], valid["y"]).statistic)

    return float(spearmanr(valid["x"], valid["y"]).statistic)


def main():
    print("Loading datasets...")

    air = pd.read_csv(AIR_FILE)
    weather = pd.read_csv(WEATHER_FILE)

    air["date"] = pd.to_datetime(
        air["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    weather["date"] = pd.to_datetime(
        weather["obs_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    for frame, city_col in [
        (air, "city"),
        (weather, "location_name")
    ]:
        frame["city_key"] = frame[city_col].map(normalize)
        frame["country_key"] = frame["country"].map(normalize)

    # A small set of common country-name aliases.
    country_aliases = {
        "bélgica": "belgium",
        "belgica": "belgium",
        "kyrghyzstan": "kyrgyzstan",
        "kyrgyz republic": "kyrgyzstan",
        "usa": "united states",
        "united states of america": "united states",
        "uk": "united kingdom",
        "russian federation": "russia",
        "viet nam": "vietnam",
        "czech republic": "czechia",
        "republic of korea": "south korea",
        "iran (islamic republic of)": "iran",
        "syrian arab republic": "syria",
    }

    for frame in (air, weather):
        frame["country_key"] = frame["country_key"].replace(
            country_aliases
        )

    print("Aggregating duplicate weather city-days...")

    weather_daily = (
        weather.groupby(
            ["city_key", "country_key", "date"],
            dropna=False
        )[WEATHER_VARIABLES]
        .mean()
        .reset_index()
    )

    # Aggregate any repeated air-quality city-day records
    # within each pollutant and native unit.
    air_daily = (
        air.groupby(
            [
                "city_key", "country_key", "date",
                "pollutant", "unit"
            ],
            dropna=False
        )
        .agg(
            value=("value", "mean"),
            station_count=("station_count", "max"),
            sensor_count=("sensor_count", "max"),
            mean_coverage_pct=("mean_coverage_pct", "mean"),
            mean_distance_m=("mean_distance_m", "mean"),
            city=("city", "first"),
            country=("country", "first")
        )
        .reset_index()
    )

    print("Joining air quality to weather...")

    joined = air_daily.merge(
        weather_daily,
        on=["city_key", "country_key", "date"],
        how="inner",
        validate="many_to_one"
    )

    if joined.empty:
        raise RuntimeError(
            "No matching city-days. Check city/country naming."
        )

    joined["pollutant_label"] = joined["pollutant"].map(
        POLLUTANT_NAMES
    ).fillna(joined["pollutant"])

    joined.to_csv(JOINED_FILE, index=False)

    print("Matched rows:", len(joined))
    print(
        "Matched city-country pairs:",
        joined[["city_key", "country_key"]]
        .drop_duplicates().shape[0]
    )

    print("Calculating correlations...")

    results = []

    for (pollutant, unit), group in joined.groupby(
        ["pollutant", "unit"]
    ):
        for variable in WEATHER_VARIABLES:
            valid = group[
                ["value", variable, "city_key", "country_key"]
            ].dropna().copy()

            if len(valid) < 10:
                continue

            pooled_pearson = safe_corr(
                valid["value"], valid[variable], "pearson"
            )
            pooled_spearman = safe_corr(
                valid["value"], valid[variable], "spearman"
            )

            # Remove each city's mean to focus on changes
            # within a city rather than differences between cities.
            city_groups = valid.groupby(
                ["city_key", "country_key"]
            )

            valid["aq_within_city"] = city_groups["value"].transform(
                lambda s: s - s.mean()
            )
            valid["weather_within_city"] = city_groups[
                variable
            ].transform(lambda s: s - s.mean())

            within_city_pearson = safe_corr(
                valid["aq_within_city"],
                valid["weather_within_city"],
                "pearson"
            )

            results.append({
                "pollutant": pollutant,
                "pollutant_label": POLLUTANT_NAMES.get(
                    pollutant, pollutant
                ),
                "unit": unit,
                "weather_variable": variable,
                "matched_city_days": len(valid),
                "cities": valid[
                    ["city_key", "country_key"]
                ].drop_duplicates().shape[0],
                "pooled_pearson": pooled_pearson,
                "pooled_spearman": pooled_spearman,
                "within_city_pearson": within_city_pearson,
            })

    correlations = pd.DataFrame(results)

    correlations = correlations.sort_values(
        ["pollutant", "unit", "weather_variable"]
    )

    correlations.to_csv(CORRELATION_FILE, index=False)

    air_keys = air_daily[
        ["city_key", "country_key", "date"]
    ].drop_duplicates()

    weather_keys = weather_daily[
        ["city_key", "country_key", "date"]
    ].drop_duplicates()

    matched_keys = air_keys.merge(
        weather_keys,
        on=["city_key", "country_key", "date"],
        how="inner"
    )

    air_cities = air_daily[
        ["city_key", "country_key"]
    ].drop_duplicates()

    weather_cities = weather_daily[
        ["city_key", "country_key"]
    ].drop_duplicates()

    matched_cities = air_cities.merge(
        weather_cities,
        on=["city_key", "country_key"],
        how="inner"
    )

    summary = {
        "air_quality_city_days": int(len(air_keys)),
        "weather_city_days": int(len(weather_keys)),
        "matched_city_days": int(len(matched_keys)),
        "city_day_match_rate_pct": round(
            100 * len(matched_keys) / max(len(air_keys), 1), 2
        ),
        "air_quality_city_country_pairs": int(len(air_cities)),
        "matched_city_country_pairs": int(len(matched_cities)),
        "matched_observation_rows": int(len(joined)),
        "pollutants_analyzed": sorted(
            joined["pollutant"].unique().tolist()
        ),
        "weather_variables": WEATHER_VARIABLES,
        "correlation_methods": [
            "pooled Pearson",
            "pooled Spearman",
            "within-city Pearson after city-mean demeaning"
        ],
        "interpretation_warning": (
            "Correlations are observational associations, not causal "
            "effects. Pooled observations are repeated over time and "
            "within-city demeaning does not remove seasonality, "
            "time trends, or all confounding."
        )
    }

    COVERAGE_FILE.write_text(json.dumps(summary, indent=2))

    print("\n=== AIR QUALITY MATCH SUMMARY ===")
    print(json.dumps(summary, indent=2))

    print("\n=== STRONGEST WITHIN-CITY RELATIONSHIPS ===")
    print(
        correlations.assign(
            abs_corr=correlations["within_city_pearson"].abs()
        )
        .sort_values("abs_corr", ascending=False)
        .head(20)
        .drop(columns="abs_corr")
        .to_string(index=False)
    )

    print("\nSaved:")
    print(JOINED_FILE)
    print(CORRELATION_FILE)
    print(COVERAGE_FILE)


if __name__ == "__main__":
    main()
