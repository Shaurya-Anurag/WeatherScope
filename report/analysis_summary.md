# WeatherScope — Automated Analysis Summary

- Source file: `GlobalWeatherRepository-selected-columns.csv`
- Rows in source: 170,928
- Rows after exact duplicate removal: 170,927
- Unique locations: 268
- Countries: 211
- Parsed timestamp range: 2024-05-16 to 2026-10-13
- Mean temperature: 21.44°C
- Mean humidity: unavailable
- Flagged anomalies: 3,124

## Forecast evaluation

- Location evaluated: Accra, Ghana
- Validation method: chronological inner validation for ensemble selection; final chronological test segment for reported model metrics.

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Ridge | 0.3809 | 0.5018 | 0.14462553779443388 |
| Random Forest | 0.3598 | 0.5021 | 0.14354394684532168 |
| Extra Trees | 0.3751 | 0.5218 | 0.07528243462662076 |
| HistGradientBoosting | 0.4226 | 0.5650 | -0.08451195055471272 |
| Persistence baseline | 0.4667 | 0.6126 | -0.2749094202898559 |
| Validation-selected ensemble | 0.3781 | 0.5172 | 0.09138590139131508 |

## Air quality
No recognizable air-quality/pollutant columns were found. The air-quality analysis remains unavailable; no substitute measurements were invented.

## Data and interpretation limitations
- Outlier flags identify statistical unusualness, not confirmed meteorological extremes or data errors.
- Correlation does not imply causation.
- A `lastupdated` column alone does not establish long-term climate history.
- Country comparisons reflect the observations present in this dataset and may not represent population-weighted or area-weighted climate conditions.

## Pipeline warnings
- Values outside broad physical sanity ranges were set to missing for derived summaries; raw source file remains unchanged.

## Figures
- `analysis/output/temperature_distribution.png` (when temperature is available)
- `analysis/output/correlation_heatmap.png` (when sufficient numeric features are available)
- `analysis/output/observed_trend.png` (when multiple monthly bins exist)
