import json
from pathlib import Path

import pandas as pd
import pycountry
import pycountry_convert as pc

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/enriched_weather.csv"
OUT = ROOT / "analysis/output"
OUT.mkdir(parents=True, exist_ok=True)

VARIABLES = [
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_mean",
    "precipitation_sum",
    "cloud_cover_mean",
]


def main():
    df = pd.read_csv(INPUT)

    # Aggregate repeated observations for each city and date.
    df["date"] = pd.to_datetime(
        df["obs_date"], errors="coerce"
    ).dt.date

    daily = (
        df.groupby(
            ["country", "location_name", "date"],
            dropna=False
        )[VARIABLES]
        .mean()
        .reset_index()
    )

    

    countries = daily["country"].dropna().unique().tolist()

    continent_map = {
        "AF": "Africa",
        "AS": "Asia",
        "EU": "Europe",
        "NA": "North America",
        "SA": "South America",
        "OC": "Oceania",
    }

  # Explicit aliases for names in the source dataset.
    COUNTRY_ALIASES = {
        "Bélgica": "BE",
        "Cape Verde": "CV",
        "Cote d'Ivoire": "CI",
        "Democratic Republic of Congo": "CD",
        "Estonie": "EE",
        "Fiji Islands": "FJ",
        "Inde": "IN",
        "Jemen": "YE",
        "Komoren": "KM",
        "Kosovo": "XK",
        "Kyrghyzstan": "KG",
        "Letonia": "LV",
        "Macedonia": "MK",
        "Malásia": "MY",
        "Marrocos": "MA",
        "Mexique": "MX",
        "Polônia": "PL",
        "Russia": "RU",
        "Saint-Vincent-et-les-Grenadines": "VC",
        "Saudi Arabien": "SA",
        "Seychelles Islands": "SC",
        "Swaziland": "SZ",
        "Südkorea": "KR",
        "Timor-Leste": "TL",
        "Turkey": "TR",
        "Turkménistan": "TM",
        "USA United States of America": "US",
        "Vatican City": "VA",
        "Гватемала": "GT",
        "Польша": "PL",
        "Турция": "TR",
        "كولومبيا": "CO",
        "火鸡": "TR",
    }

    def get_continent(country):
        try:
            special_cases = {
                "Micronesia": "Oceania",
                "Timor-Leste": "Asia",
                "Vatican City": "Europe",
            }
    
            if country in special_cases:
                return special_cases[country]
    
            if country in COUNTRY_ALIASES:
                alpha2 = COUNTRY_ALIASES[country]
            else:
                alpha2 = pycountry.countries.lookup(country).alpha_2
    
            # Kosovo is not in the standard ISO country database.
            if alpha2 == "XK":
                return "Europe"
    
            code = pc.country_alpha2_to_continent_code(alpha2)
            return continent_map.get(code)
    
        except Exception:
            return None
    

        except Exception:
            return None


    mapping = pd.DataFrame({
        "country": countries,
        "continent": [get_continent(c) for c in countries]
    })

    daily = daily.merge(mapping, on="country", how="left")

    unmapped = sorted(
        daily.loc[daily["continent"].isna(), "country"]
        .dropna().unique().tolist()
    )

    daily = daily.dropna(subset=["continent"])

    # Observation-weighted continent averages.
    observation_weighted = (
        daily.groupby("continent")
        .agg(
            observations=("date", "size"),
            countries=("country", "nunique"),
            cities=("location_name", "nunique"),
            **{
                variable: (variable, "mean")
                for variable in VARIABLES
            }
        )
        .reset_index()
    )

    # First calculate each country's average, then give
    # each country equal weight within its continent.
    country_means = (
        daily.groupby(["continent", "country"])
        [VARIABLES]
        .mean()
        .reset_index()
    )

    country_weighted = (
        country_means.groupby("continent")
        .agg(
            countries=("country", "nunique"),
            **{
                variable: (variable, "mean")
                for variable in VARIABLES
            }
        )
        .reset_index()
    )

    observation_weighted.to_csv(
        OUT / "continent_observation_weighted.csv",
        index=False
    )

    country_weighted.to_csv(
        OUT / "continent_country_weighted.csv",
        index=False
    )

    country_means.to_csv(
        OUT / "country_weather_averages.csv",
        index=False
    )

    summary = {
        "source": "enriched_weather.csv",
        "method": (
            "Descriptive continent comparisons using six continent "
            "categories. Observation-weighted averages and equal-country "
            "averages are reported separately."
        ),
        "countries_in_source": len(countries),
        "countries_mapped": int(daily["country"].nunique()),
        "unmapped_countries": unmapped,
        "continents_present": sorted(
            daily["continent"].dropna().unique().tolist()
        ),
        "date_range": [
            str(daily["date"].min()),
            str(daily["date"].max())
        ],
        "observation_weighted": observation_weighted.to_dict(
            orient="records"
        ),
        "country_weighted": country_weighted.to_dict(
            orient="records"
        )
    }

    (OUT / "continent_analysis_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )

    print("\n=== CONTINENT COMPARISON: OBSERVATION WEIGHTED ===")
    print(observation_weighted.round(2).to_string(index=False))

    print("\n=== CONTINENT COMPARISON: COUNTRY WEIGHTED ===")
    print(country_weighted.round(2).to_string(index=False))

    print("\n=== COUNTRY MAPPING ===")
    print("Countries in source:", len(countries))
    print("Countries mapped:", daily["country"].nunique())
    print("Unmapped:", unmapped)

    print("\nSaved continent analysis outputs.")


if __name__ == "__main__":
    main()
