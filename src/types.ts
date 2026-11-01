
export type DashboardData = {
  meta: {
    status: string;
    source: string;
    generated_at: string | null;
    rows: number;
    cities: number;
    countries: number;
    date_min: string | null;
    date_max: string | null;
    timestamp_note: string;
    warnings: string[];
  };

  kpis: {
    mean_temp_c: number | null;
    mean_humidity_pct: number | null;
    mean_wind_kph: number | null;
    precipitation_rows: number;
    anomaly_count: number;
  };

  map_points: {
    city: string;
    country: string;
    lat: number;
    lon: number;
    temp_c: number | null;
    humidity: number | null;
    wind_kph: number | null;
    precipitation_mm: number | null;
    anomaly: boolean;
  }[];

  trend: {
    label: string;
    temperature: number | null;
    precipitation: number | null;
    humidity: number | null;
  }[];

  regions: {
    name: string;
    temperature: number;
    humidity: number;
    wind: number;
    rows: number;
  }[];

  correlations: {
    x: string;
    y: string;
    value: number;
  }[];

  anomalies: {
    city: string;
    country: string;
    date: string;
    temperature: number | null;
    score: number;
    reason: string;
    category?: string;
  }[];

  anomaly_breakdown?: Record<string, number>;

  anomaly_reason_counts?: Record<string, number>;

  climate: ClimateData;

  forecasts: {
    available: boolean;
    reason: string;
    target: string;
    city: string;
    horizon_days: number;

    models: {
      name: string;
      mae: number;
      rmse: number;
      r2: number | null;
    }[];

    series: {
      date: string;
      actual: number | null;
      baseline: number | null;
      ensemble: number | null;
      lower: number | null;
      upper: number | null;
    }[];

    feature_importance: {
      feature: string;
      importance: number;
    }[];
  };



  air_quality: {
    available: boolean;
    fields: string[];
    correlations: {
      feature: string;
      pollutant: string;
      correlation: number;
      unit?: string;
      sample_size?: number;
      cities?: number;
      pooled_pearson?: number | null;
      pooled_spearman?: number | null;
      method?: string;
    }[];
    note: string;
    matched_city_days?: number;
    matched_observation_rows?: number;
    matched_cities?: number;
    match_rate_pct?: number;
    method?: string;
  };


  continent_regions?: {
    name: string;
    rows: number;
    locations: number;
    countries: number;
    temperature: number | null;
    humidity: number | null;
    wind: number | null;
    precipitation: number | null;
    cloud_cover: number | null;
    aggregation_method: string;
  }[];

  continent_country_weighted?: {
    name: string;
    countries: number;
    temperature: number | null;
    humidity: number | null;
    wind: number | null;
    precipitation: number | null;
    cloud_cover: number | null;
  }[];

  continent_coverage?: {
    classified_rows: number;
    unclassified_rows: number;
    classification_percentage: number;
    mapped_countries?: number;
    total_countries?: number;
  };


  data_quality: {
    column: string;
    missing_pct: number;
    unique: number;
  }[];
};


export type ClimateYearOverYear = {
  year: number;
  matched_location_months: number;
  matched_locations: number;
  temperature_change_c: number;
  median_temperature_change_c: number;
  precipitation_change_mm_per_day: number;
};

export type ClimateTemperatureAnomaly = {
  year: number;
  month: number;
  label: string;
  mean_anomaly_c: number;
  median_anomaly_c: number;
  locations: number;
};

export type ClimatePrecipitationVariability = {
  year: number;
  month: number;
  label: string;
  mean_daily_precipitation_mm: number;
  median_daily_precipitation_mm: number;
  between_location_std_mm: number;
  locations: number;
};

export type ClimateData = {
  available: boolean;
  method: string;
  year_over_year: ClimateYearOverYear[];
  temperature_anomalies: ClimateTemperatureAnomaly[];
  precipitation_variability: ClimatePrecipitationVariability[];
  coverage: {
    eligible_locations: number;
    matched_location_months: number;
    years: number[];
  };
  note: string;
};