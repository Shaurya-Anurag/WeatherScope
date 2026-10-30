# WeatherScope — Global Weather Intelligence & Forecasting

A local-first weather analytics project built for the PM Accelerator technical assessment. The interface is a custom dark, map-centered dashboard; data cleaning, statistical analysis, anomaly detection, and forecasting run locally in Python. **No weather API, hosted LLM, or paid API is used.**

> Important: this project does not pretend that a `lastupdated` timestamp automatically gives us a historical time series. Forecasting is enabled only when a location has enough distinct timestamped temperature observations. If the downloaded CSV is a snapshot, the pipeline reports that limitation rather than inventing forecasts.

## What is implemented

- Schema-aware CSV loading and data audit
- Exact duplicate removal and timestamp parsing
- Conservative physical sanity checks for derived summaries (raw source is never overwritten)
- Missingness report and weather-feature summaries
- IQR outlier flags plus multivariate Isolation Forest flags
- Global map markers from latitude/longitude when available
- Country/region comparisons and numeric feature correlations
- Air-quality field discovery and weather-pollutant correlations when matching columns exist
- Conditional forecasting: persistence baseline, Ridge, Random Forest, Extra Trees, HistGradientBoosting, validation-selected ensemble, chronological holdout evaluation, and permutation feature importance
- Automated Markdown summary and local plots
- Dark Next.js dashboard showing the results JSON, without fabricated values

## Stack

- **Frontend:** Next.js, React, TypeScript, Recharts, React Simple Maps, World Atlas, Lucide
- **Analysis:** Python, pandas, NumPy, scikit-learn, statsmodels dependency available for future extensions, Matplotlib, Seaborn
- **Geography:** packaged `world-atlas` boundaries and coordinates already in the CSV; no map/geocoding API

## 1. Requirements

- Node.js 18+ and npm
- Python 3.10+
- The Kaggle file `Global Weather Repository.csv`

## 2. Put the data in place

Download the CSV from the [World Weather Repository Kaggle page](https://www.kaggle.com/datasets/nelgiriyewithana/global-weather-repository/code) and place it here:

```text
data/Global Weather Repository.csv
```

The dataset is ignored by Git so a large or license-sensitive raw file is not accidentally committed.

## 3. Run the local analysis

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python analysis/run_analysis.py --input "data/Global Weather Repository.csv"
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analysis/run_analysis.py --input "data/Global Weather Repository.csv"
```

Optional: choose a city/place label and forecast horizon if that location has sufficient repeated timestamps:

```bash
python analysis/run_analysis.py --input "data/Global Weather Repository.csv" --forecast-city "London, United Kingdom" --horizon 7
```

The pipeline writes:

- `public/data/dashboard.json` — data consumed by the dashboard
- `report/analysis_summary.md` — generated findings and caveats
- `analysis/output/` — locally generated plots

## 4. Run the dashboard

In a second terminal, from the project root:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

For a production build:

```bash
npm run build
npm start
```

The world boundary asset is bundled through the `world-atlas` npm package. After dependencies are installed, the dashboard does not call a weather API or geocoding service.

## Methodology and guardrails

1. **Time semantics:** `lastupdated` is treated as the observation timestamp only. It is not assumed to be a date-indexed history for each city.
2. **Outliers:** IQR and Isolation Forest output flags, not confirmed weather events. Investigate each flag before removing it.
3. **Forecasting:** The model requires at least 40 distinct timestamped observations for a location, then uses lagged features and chronological splits. The final holdout is never randomly shuffled. Metrics are specific to the selected location and dataset.
4. **Ensemble:** Two models are selected using an inner chronological validation segment, then averaged on the final test segment. The ensemble is compared with individual models and the persistence baseline; it is not presumed superior.
5. **Air quality:** Pollutant correlations are calculated only if matching pollutant fields are present. Correlation does not establish causation.
6. **Climate analysis:** Monthly summaries from short or cross-sectional coverage are not presented as long-term climate trends. Long-term claims require suitable historical coverage.
7. **Missingness and units:** The source schema is inspected dynamically. The script uses common field aliases, and unrecognized fields remain in the quality report rather than being silently reinterpreted.
8. **No fabricated results:** Before processing the CSV, dashboard metrics remain blank and the panels explain what is missing.

## Assessment coverage

| Assessment requirement | Implementation |
|---|---|
| Cleaning, missing values, outliers, normalization | Data audit, conservative sanity checks, missingness report; scaling in Ridge pipeline |
| EDA, temperature and precipitation | Descriptive summaries, trend panel when timestamps support it, local plots |
| Forecast using `lastupdated` | Conditional timestamp validation and forecasting path |
| Anomaly detection | IQR + Isolation Forest |
| Multiple models and ensemble | Ridge, Random Forest, Extra Trees, HistGradientBoosting, persistence baseline, validation-selected ensemble |
| Climate and regional analysis | Time-binned summaries and country/region comparisons, constrained by data coverage |
| Environmental impact | Dynamic pollutant discovery and correlations when available |
| Feature importance | Permutation importance on a chronological held-out set |
| Spatial analysis | Local world boundaries plus CSV coordinates |
| Mission statement | PM Accelerator mission displayed in dashboard and documented below |

## PM Accelerator mission

PM Accelerator states its mission is to launch 1,000+ AI products and empower professionals to become the next generation of AI product leaders, impacting millions of lives through real-world innovation. Source: [PM Accelerator — AI Product Management Certification](https://www.pmaccelerator.io/ai-product-management-certification).

## Known limitations / next improvements

- The real CSV must be run before there are empirical results to discuss.
- If the repository CSV is a one-time global snapshot, we must acquire a legitimate historical dataset for forecasting and long-term climate analysis. We must not synthesize history from unrelated cities.
- The dashboard's map uses observation markers, not interpolated continuous climate fields. That is intentional to avoid implying measurements where none exist.
- The forecasting code is a baseline research implementation; more rigorous rolling-origin backtesting, uncertainty calibration, and per-city batch evaluation can be added once the dataset's actual time coverage is known.
