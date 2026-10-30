import type { DashboardData } from './types';

const empty: DashboardData = {
  meta: { status: 'awaiting-data', source: 'Global Weather Repository.csv', generated_at: null, rows: 0, cities: 0, countries: 0, date_min: null, date_max: null, timestamp_note: 'Place the Kaggle CSV in data/ and run the analysis pipeline.', warnings: ['No dataset has been processed yet. Dashboard values are intentionally blank rather than fabricated.'] },
  kpis: { mean_temp_c: null, mean_humidity_pct: null, mean_wind_kph: null, precipitation_rows: 0, anomaly_count: 0 },
  map_points: [], trend: [], regions: [], correlations: [], anomalies: [],
  forecasts: { available: false, reason: 'Run the local Python analysis pipeline with the dataset. Forecasting requires enough repeated, timestamped observations for a location.', target: 'temperature', city: '', horizon_days: 7, models: [], series: [], feature_importance: [] },
  air_quality: { available: false, fields: [], correlations: [], note: 'Air-quality analysis activates only if relevant pollutant columns are present.' }, data_quality: []
};

export async function loadDashboardData(): Promise<DashboardData> {
  try {
    const fs = await import('node:fs/promises');
    const path = await import('node:path');
    const file = path.join(process.cwd(), 'public', 'data', 'dashboard.json');
    const raw = await fs.readFile(file, 'utf8');
    return { ...empty, ...JSON.parse(raw) } as DashboardData;
  } catch { return empty; }
}
