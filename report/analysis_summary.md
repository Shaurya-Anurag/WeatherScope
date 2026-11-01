# WeatherScope — Automated Analysis Summary

- Source file: `enriched_weather.csv`
- Rows in source: 170,928
- Rows after exact duplicate removal: 170,927
- Unique locations: 268
- Countries: 211
- Parsed timestamp range: 2024-05-16 to 2026-10-13
- Mean temperature: 20.73°C
- Mean humidity: 69.24%
- Flagged anomalies: 29,748

## Anomaly detection breakdown

| Detector | Flagged observations |
|---|---:|
| Physical Validity | 0 |
| Local Statistical | 6,231 |
| Multivariate | 28,868 |
| Combined | 5,351 |
| Total Unique | 29,748 |

Detector counts overlap; total_unique is the union of all detector flags.

## Forecast evaluation

- Location evaluated: Accra, Ghana
- Validation method: chronological inner validation for ensemble selection; final chronological test segment for reported model metrics.

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Ridge | 0.3908 | 0.4837 | 0.3548111879086139 |
| Random Forest | 0.4016 | 0.5010 | 0.30784360659662346 |
| Extra Trees | 0.3617 | 0.4431 | 0.4585427925235993 |
| HistGradientBoosting | 0.3894 | 0.5017 | 0.3059944690159119 |
| Persistence baseline | 0.4033 | 0.4923 | 0.3317195734771423 |
| Validation-selected ensemble | 0.3699 | 0.4576 | 0.42249527109556373 |

## Seasonal summaries
Seasonal means are descriptive summaries of available observations using meteorological seasons and latitude-based hemispheres; they are not climate normals.

| Hemisphere | Season | Observations | Mean temperature (°C) | Mean humidity (%) | Mean wind (km/h) | Mean precipitation (mm) |
|---|---|---:|---:|---:|---:|---:|
| Northern | Autumn | 34,325 | 20.47 | 71.85 | 9.27 | 3.67 |
| Northern | Spring | 30,485 | 19.82 | 65.31 | 10.21 | 2.65 |
| Northern | Summer | 41,721 | 25.27 | 66.54 | 10.14 | 4.04 |
| Northern | Winter | 27,257 | 13.70 | 70.69 | 10.12 | 1.97 |
| Southern | Autumn | 8,492 | 22.00 | 77.37 | 9.31 | 4.46 |
| Southern | Spring | 9,488 | 22.40 | 68.74 | 11.42 | 3.06 |
| Southern | Summer | 7,593 | 23.83 | 75.27 | 9.71 | 5.98 |
| Southern | Winter | 11,566 | 19.78 | 68.65 | 11.14 | 1.76 |

## Matched-location climate-pattern analysis
Temperature anomalies are relative to each location’s own calendar-month average over the available dataset. Year-over-year changes use only location-month pairs observed in both adjacent years. Precipitation is mean daily precipitation per location-month, not a monthly accumulated total. These short-record summaries are not climate normals or evidence of climate change.

| Year | Matched locations | Matched location-months | Mean temperature change (°C) | Median change (°C) |
|---:|---:|---:|---:|---:|
| 2025 | 196 | 1,511 | -0.16 | -0.16 |
| 2026 | 191 | 1,861 | 0.29 | 0.25 |

Temperature anomaly values are location-specific deviations from that location’s average for the same calendar month.

| Month | Mean anomaly (°C) | Median anomaly (°C) | Locations |
|---|---:|---:|---:|
| 2024-11 | -0.04 | 0.05 | 195 |
| 2024-12 | -0.06 | -0.02 | 195 |
| 2025-01 | 0.45 | 0.16 | 195 |
| 2025-02 | -0.35 | -0.16 | 195 |
| 2025-03 | 0.19 | 0.11 | 195 |
| 2025-04 | 0.17 | 0.06 | 195 |
| 2025-05 | -0.31 | -0.32 | 195 |
| 2025-06 | -0.10 | -0.16 | 195 |
| 2025-07 | -0.15 | -0.21 | 195 |
| 2025-08 | -0.46 | -0.37 | 208 |
| 2025-09 | -0.18 | -0.18 | 198 |
| 2025-10 | -0.50 | -0.29 | 196 |
| 2025-11 | 0.04 | -0.05 | 196 |
| 2025-12 | 0.06 | 0.00 | 199 |
| 2026-01 | -0.45 | -0.14 | 198 |
| 2026-02 | 0.34 | 0.11 | 201 |
| 2026-03 | -0.18 | -0.09 | 202 |
| 2026-04 | -0.17 | -0.04 | 202 |
| 2026-05 | -0.09 | 0.00 | 196 |
| 2026-06 | 0.15 | 0.09 | 230 |
| 2026-07 | 0.21 | 0.13 | 204 |
| 2026-08 | 0.53 | 0.43 | 204 |
| 2026-09 | 0.36 | 0.25 | 204 |
| 2026-10 | 0.72 | 0.58 | 204 |

Mean daily precipitation is aggregated within each location-month; it is not a monthly rainfall total.

| Month | Mean daily precipitation (mm) | Between-location SD (mm) | Locations |
|---|---:|---:|---:|
| 2024-11 | 3.30 | 4.20 | 195 |
| 2024-12 | 2.81 | 3.52 | 195 |
| 2025-01 | 2.80 | 3.53 | 195 |
| 2025-02 | 2.74 | 3.62 | 195 |
| 2025-03 | 2.83 | 3.25 | 195 |
| 2025-04 | 2.91 | 2.93 | 195 |
| 2025-05 | 3.30 | 3.37 | 195 |
| 2025-06 | 3.29 | 4.28 | 195 |
| 2025-07 | 3.78 | 5.16 | 195 |
| 2025-08 | 3.75 | 5.09 | 208 |
| 2025-09 | 3.51 | 3.99 | 198 |
| 2025-10 | 3.42 | 3.45 | 196 |
| 2025-11 | 3.40 | 3.67 | 196 |
| 2025-12 | 2.71 | 3.01 | 199 |
| 2026-01 | 3.09 | 3.85 | 198 |
| 2026-02 | 2.85 | 3.13 | 201 |
| 2026-03 | 3.09 | 3.20 | 202 |
| 2026-04 | 2.78 | 3.12 | 202 |
| 2026-05 | 2.93 | 3.41 | 196 |
| 2026-06 | 3.69 | 4.98 | 230 |
| 2026-07 | 3.44 | 4.92 | 204 |
| 2026-08 | 3.45 | 4.93 | 204 |
| 2026-09 | 3.52 | 4.25 | 204 |
| 2026-10 | 3.71 | 4.02 | 204 |

## Preprocessing and feature scaling
- Exact duplicate rows are removed.
- Weather fields are converted to numeric values; values outside broad physical sanity ranges are excluded from derived summaries and retained as anomaly flags.
- Missing values are handled per analysis/model; median imputation is used in model pipelines.
- StandardScaler is applied to Ridge only. Tree-based models do not require feature scaling.

## Geographic analysis
- Geographic grouping basis: country.
- Country comparisons reflect the observations present in this dataset and may not represent population-weighted or area-weighted climate conditions.

## Air quality
No recognizable air-quality/pollutant columns were found. The air-quality analysis remains unavailable; no substitute measurements were invented.

## Data and interpretation limitations
- Outlier flags identify statistical unusualness, not confirmed meteorological extremes or data errors.
- Correlation does not imply causation.
- A `lastupdated` column alone does not establish long-term climate history.

## Pipeline warnings

## Figures
- `analysis/output/temperature_distribution.png` (when temperature is available)
- `analysis/output/correlation_heatmap.png` (when sufficient numeric features are available)
- `analysis/output/observed_trend.png` (when multiple monthly bins exist)
