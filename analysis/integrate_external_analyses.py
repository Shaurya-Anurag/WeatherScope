
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis/output"
DASHBOARD = ROOT / "public/data/dashboard.json"


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    dashboard = read_json(DASHBOARD)

    # --------------------------------------------------
    # CONTINENT COMPARISON
    # --------------------------------------------------
    continent = read_json(
        OUT / "continent_analysis_summary.json"
    )

    observation_rows = continent["observation_weighted"]
    country_rows = continent["country_weighted"]

    dashboard["continent_regions"] = [
        {
            "name": row["continent"],
            "rows": int(row["observations"]),
            "locations": int(row["cities"]),
            "countries": int(row["countries"]),
            "temperature": row["temperature_2m_mean"],
            "humidity": row["relative_humidity_2m_mean"],
            "wind": row["wind_speed_10m_mean"],
            "precipitation": row["precipitation_sum"],
            "cloud_cover": row["cloud_cover_mean"],
            "aggregation_method": (
                "Observation-weighted means across available "
                "city-day observations."
            )
        }
        for row in observation_rows
    ]

    dashboard["continent_country_weighted"] = [
        {
            "name": row["continent"],
            "countries": int(row["countries"]),
            "temperature": row["temperature_2m_mean"],
            "humidity": row["relative_humidity_2m_mean"],
            "wind": row["wind_speed_10m_mean"],
            "precipitation": row["precipitation_sum"],
            "cloud_cover": row["cloud_cover_mean"],
        }
        for row in country_rows
    ]

    total_countries = continent["countries_in_source"]
    mapped_countries = continent["countries_mapped"]

    dashboard["continent_coverage"] = {
        "classified_rows": sum(
            int(row["observations"]) for row in observation_rows
        ),
        "unclassified_rows": 0,
        "classification_percentage": (
            100 * mapped_countries / total_countries
            if total_countries else 0
        ),
        "mapped_countries": mapped_countries,
        "total_countries": total_countries,
    }

    # --------------------------------------------------
    # AIR QUALITY RELATIONSHIPS
    # --------------------------------------------------
    air_summary = read_json(
        OUT / "air_quality_match_summary.json"
    )

    correlations = pd.read_csv(
        OUT / "air_quality_correlations.csv"
    )

    # Main dashboard: prioritize relationships with enough
    # city-day observations and geographic coverage.
    robust = correlations[
        (correlations["matched_city_days"] >= 1000)
        & (correlations["cities"] >= 20)
        & correlations["within_city_pearson"].notna()
    ].copy()

    robust["absolute_strength"] = (
        robust["within_city_pearson"].abs()
    )

    robust = robust.sort_values(
        "absolute_strength", ascending=False
    ).head(12)

    air_correlations = []

    for row in robust.to_dict("records"):
        air_correlations.append({
            "feature": row["weather_variable"],
            "pollutant": row["pollutant_label"],
            "unit": row["unit"],
            "correlation": float(row["within_city_pearson"]),
            "pooled_pearson": (
                float(row["pooled_pearson"])
                if pd.notna(row["pooled_pearson"]) else None
            ),
            "pooled_spearman": (
                float(row["pooled_spearman"])
                if pd.notna(row["pooled_spearman"]) else None
            ),
            "sample_size": int(row["matched_city_days"]),
            "cities": int(row["cities"]),
            "method": "Within-city Pearson correlation",
        })

    dashboard["air_quality"] = {
        "available": True,
        "fields": sorted(
            correlations["pollutant"].dropna().unique().tolist()
        ),
        "correlations": air_correlations,
        "note": (
            f"OpenAQ v3 observations matched with weather data: "
            f"{air_summary['matched_city_days']:,} matched city-days "
            f"({air_summary['city_day_match_rate_pct']}% of air-quality "
            f"city-days), across "
            f"{air_summary['matched_city_country_pairs']} "
            f"city-country pairs. Six pollutants analyzed. "
            "Correlations are observational, not causal. "
            "Within-city Pearson correlations remove city means but "
            "do not adjust for seasonality, time trends or serial "
            "dependence. Gas pollutant units are kept separate."
        ),
        "matched_city_days": air_summary["matched_city_days"],
        "matched_observation_rows": air_summary[
            "matched_observation_rows"
        ],
        "matched_cities": air_summary[
            "matched_city_country_pairs"
        ],
        "match_rate_pct": air_summary[
            "city_day_match_rate_pct"
        ],
        "method": "Within-city Pearson; pooled Pearson and Spearman retained in CSV.",
    }

    DASHBOARD.write_text(
        json.dumps(dashboard, indent=2, allow_nan=False),
        encoding="utf-8"
    )

    print("Dashboard integration complete.")
    print("Continents:", len(dashboard["continent_regions"]))
    print(
        "Country-weighted continent groups:",
        len(dashboard["continent_country_weighted"])
    )
    print(
        "Country mapping:",
        mapped_countries,
        "/",
        total_countries
    )
    print(
        "Air-quality correlations displayed:",
        len(air_correlations)
    )
    print(
        "Matched city-days:",
        air_summary["matched_city_days"]
    )
    print("Updated:", DASHBOARD)


if __name__ == "__main__":
    main()
