export type DashboardData = {
  meta: { status: string; source: string; generated_at: string | null; rows: number; cities: number; countries: number; date_min: string | null; date_max: string | null; timestamp_note: string; warnings: string[] };
  kpis: { mean_temp_c: number | null; mean_humidity_pct: number | null; mean_wind_kph: number | null; precipitation_rows: number; anomaly_count: number };
  map_points: { city: string; country: string; lat: number; lon: number; temp_c: number | null; humidity: number | null; wind_kph: number | null; precipitation_mm: number | null; anomaly: boolean }[];
  trend: { label: string; temperature: number | null; precipitation: number | null; humidity: number | null }[];
  regions: { name: string; temperature: number; humidity: number; wind: number; rows: number }[];
  correlations: { x: string; y: string; value: number }[];
  anomalies: { city: string; country: string; date: string; temperature: number | null; score: number; reason: string }[];
  forecasts: { available: boolean; reason: string; target: string; city: string; horizon_days: number; models: { name: string; mae: number; rmse: number; r2: number | null }[]; series: { date: string; actual: number | null; baseline: number | null; ensemble: number | null; lower: number | null; upper: number | null }[]; feature_importance: { feature: string; importance: number }[] };
  air_quality: { available: boolean; fields: string[]; correlations: { feature: string; pollutant: string; correlation: number }[]; note: string };
  data_quality: { column: string; missing_pct: number; unique: number }[];
};
