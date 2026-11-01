"""WeatherScope local-first analysis pipeline.



Usage: python analysis/run_analysis.py --input data/Global Weather Repository.csv

Writes: public/data/dashboard.json, report/analysis_summary.md, analysis/output/*.png

No weather API calls are made. All values derive from the local CSV.

"""

from __future__ import annotations

import argparse, json, re, warnings

from datetime import datetime, timezone

from pathlib import Path

import numpy as np

import pandas as pd

from sklearn.ensemble import IsolationForest, RandomForestRegressor, HistGradientBoostingRegressor, ExtraTreesRegressor

from sklearn.impute import SimpleImputer

from sklearn.inspection import permutation_importance

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from sklearn.pipeline import make_pipeline

from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import Ridge

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt

import seaborn as sns



ROOT = Path(__file__).resolve().parents[1]

OUT_JSON = ROOT / 'public' / 'data' / 'dashboard.json'

OUT_DIR = ROOT / 'analysis' / 'output'

REPORT = ROOT / 'report' / 'analysis_summary.md'

ALIASES = {

    'city': ['location_name', 'city', 'location', 'name'],

    'country': ['country', 'country_name'],

    'lat': ['latitude', 'lat'],

    'lon': ['longitude', 'lon', 'lng'],

    'date': ['obs_date', 'last_updated', 'lastupdated', 'last update', 'datetime', 'date', 'timestamp'],

    'temp': ['temperature_2m_mean', 'temperature_celsius', 'temp_c', 'temperature', 'temp', 'temperature (c)'],

    'humidity': ['relative_humidity_2m_mean', 'humidity', 'humidity_pct', 'relative_humidity'],

    'wind': ['wind_speed_10m_mean', 'wind_kph', 'wind_speed_kph', 'wind_speed', 'wind_mph'],

    'precip': ['precipitation_sum', 'precip_mm', 'precipitation_mm', 'precipitation', 'rain_mm'],

    'pressure': ['pressure_mb', 'pressure_hpa', 'pressure'],

    'cloud': ['cloud_cover_mean', 'cloud', 'cloud_cover', 'cloud_cover_pct'],

    'uv': ['uv_index', 'uv'],

}

POLLUTANT_TOKENS = ['pm2.5','pm2_5','pm10','nitrogen_dioxide','nitrogen dioxide','sulphur_dioxide','sulfur_dioxide','ozone','carbon_monoxide','epa-index','defra-index','aqi']

WEATHER_NUMERIC_TOKENS = ['temperature','temp','humidity','wind','precip','pressure','cloud','uv','visibility','gust','dewpoint','heatindex','feels_like','air_quality']



def norm(s): return re.sub(r'[^a-z0-9]+','_',str(s).strip().lower()).strip('_')

def find_col(df, key):

    cols = {norm(c):c for c in df.columns}

    for a in ALIASES[key]:

        if norm(a) in cols: return cols[norm(a)]

    for c in df.columns:

        n=norm(c)

        if key=='temp' and ('temperature_celsius' in n or n in ('temp_c','temperature_c')): return c

        if key=='date' and ('last_updated' in n or 'lastupdate' in n): return c

        if key=='wind' and ('wind_kph' in n or 'wind_speed' in n): return c

        if key=='precip' and ('precip_mm' in n or 'precipitation' in n): return c

    return None



def safe_num(series): return pd.to_numeric(series.astype(str).str.replace(',','',regex=False), errors='coerce')

def json_num(v): return None if pd.isna(v) or not np.isfinite(float(v)) else float(v)

def city_group(df, city_col, country_col):

    if city_col and country_col: return df[city_col].fillna('Unknown').astype(str)+', '+df[country_col].fillna('Unknown').astype(str)

    if city_col: return df[city_col].fillna('Unknown').astype(str)

    if country_col: return df[country_col].fillna('Unknown').astype(str)

    return pd.Series(['Unknown']*len(df), index=df.index)

def main():

    ap=argparse.ArgumentParser(); ap.add_argument('--input',default='data/Global Weather Repository.csv'); ap.add_argument('--forecast-city',default=None); ap.add_argument('--horizon',type=int,default=7); args=ap.parse_args()

    inp=Path(args.input); inp=inp if inp.is_absolute() else ROOT/inp

    if not inp.exists(): raise SystemExit(f'CSV not found: {inp}\nDownload the Kaggle dataset and place it at data/Global Weather Repository.csv, or pass --input.')

    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_DIR.mkdir(parents=True,exist_ok=True); (ROOT/'report').mkdir(exist_ok=True)

    raw=pd.read_csv(inp, low_memory=False)

    if raw.empty: raise SystemExit('CSV contains no rows.')

    original_rows=len(raw); raw.columns=[str(c).strip() for c in raw.columns]

    cols={k:find_col(raw,k) for k in ALIASES}

    date_col=cols['date']; city_col=cols['city']; country_col=cols['country']; temp_col=cols['temp']; lat_col=cols['lat']; lon_col=cols['lon']

    df=raw.copy(); df=df.drop_duplicates()

    warnings_list=[]

    if date_col:

        df['_date']=pd.to_datetime(df[date_col],errors='coerce',utc=True).dt.tz_convert(None)

        bad=int(df['_date'].isna().sum())

        if bad: warnings_list.append(f'{bad:,} rows have unparseable timestamps; excluded from time-series modelling but retained for cross-sectional summaries.')

    else:

        df['_date']=pd.NaT; warnings_list.append('No recognized lastupdated/timestamp column was found; time-series forecasting is disabled.')

    # standard numeric feature extraction; prefer Celsius/KPH fields where available

    numeric={}

    for c in df.columns:

        n=norm(c)

        if any(tok in n for tok in WEATHER_NUMERIC_TOKENS):

            x=safe_num(df[c])

            if x.notna().sum()>0: numeric[c]=x

    for key in ['temp','humidity','wind','precip','pressure','cloud','uv','lat','lon']:

        c=cols[key]

        if c and c in df.columns:

            df['_'+key]=safe_num(df[c])

    # fall back to a Celsius-like field if common aliases miss it

    if '_temp' not in df and temp_col: df['_temp']=safe_num(df[temp_col])

    # Use numeric physically plausible checks to flag, not silently delete, values.

    physical_ranges={'_temp':(-90,65),'_humidity':(0,100),'_wind':(0,500),'_precip':(0,2000),'_pressure':(800,1200),'_cloud':(0,100),'_uv':(0,30),'_lat':(-90,90),'_lon':(-180,180)}

    invalid_counts={}
    physical_invalid_mask = pd.Series(False, index=df.index)

    for c,(lo,hi) in physical_ranges.items():

        if c in df:

            mask=df[c].notna() & ~df[c].between(lo,hi)

            invalid_counts[c]=int(mask.sum())
            physical_invalid_mask |= mask

            if mask.any(): df.loc[mask,c]=np.nan

    if sum(invalid_counts.values()): warnings_list.append('Values outside broad physical sanity ranges were set to missing for derived summaries; raw source file remains unchanged.')

    if not city_group(df,city_col,country_col).nunique(): warnings_list.append('No location identifiers found.')

    df['_place']=city_group(df,city_col,country_col)

    # Location-aware anomaly detection.
    # Track each detector independently so overlaps remain visible.

    feature_cols = [
        c for c in ['_temp', '_humidity', '_wind', '_precip', '_pressure', '_cloud', '_uv']
        if c in df and df[c].notna().sum() > 10
    ]

    physical_flag = physical_invalid_mask.copy()
    local_stat_flag = pd.Series(False, index=df.index)
    multivariate_flag = pd.Series(False, index=df.index)
    reasons = pd.Series('', index=df.index, dtype=object)
    scores = pd.Series(0.0, index=df.index)

    # Physical flags were captured before invalid values were nulled for analysis.
    for idx in df.index[physical_flag]:
        reasons.loc[idx] = 'physical validity violation'

    # Local statistical and multivariate detection by display location.
    for place, group in df.groupby('_place', dropna=True):
        if len(group) < 100:
            continue

        # Local IQR for temperature, humidity and wind.
        for col in ['_temp', '_humidity', '_wind']:
            if col not in df:
                continue

            values = group[col].dropna()
            if len(values) < 100:
                continue

            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            if pd.isna(iqr) or iqr <= 0:
                continue

            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            flags = group.index[
                group[col].notna() & ((group[col] < lower) | (group[col] > upper))
            ]
            local_stat_flag.loc[flags] = True

            for idx in flags:
                reason = col.lstrip('_') + ' local IQR'
                reasons.loc[idx] = (reasons.loc[idx] + '; ' + reason) if reasons.loc[idx] else reason

        # Compare precipitation on wet days only to avoid zero-inflated IQR thresholds.
        if '_precip' in df:
            wet = group.loc[group['_precip'] > 0, '_precip']
            if len(wet) >= 30:
                threshold = wet.quantile(0.99)
                rain_flags = group.index[
                    group['_precip'].notna() & (group['_precip'] > threshold)
                ]
                local_stat_flag.loc[rain_flags] = True

                for idx in rain_flags:
                    reason = 'precipitation above local wet-day 99th percentile'
                    reasons.loc[idx] = (reasons.loc[idx] + '; ' + reason) if reasons.loc[idx] else reason

        # Fit one Isolation Forest per sufficiently sampled location.
        if len(group) >= 200 and len(feature_cols) >= 2:
            try:
                X = group[feature_cols].replace([np.inf, -np.inf], np.nan)
                X = X.loc[X.notna().any(axis=1)]

                if len(X) >= 200:
                    X_imputed = SimpleImputer(strategy='median').fit_transform(X)
                    iso = IsolationForest(
                        n_estimators=150,
                        contamination='auto',
                        random_state=42,
                        n_jobs=-1
                    )
                    labels = iso.fit_predict(X_imputed)
                    decisions = -iso.decision_function(X_imputed)
                    flagged = X.index[labels == -1]
                    multivariate_flag.loc[flagged] = True
                    scores.loc[X.index] = decisions

                    for idx in flagged:
                        reason = 'local Isolation Forest'
                        reasons.loc[idx] = (reasons.loc[idx] + '; ' + reason) if reasons.loc[idx] else reason

            except Exception as e:
                warnings_list.append(
                    f'Local Isolation Forest skipped for {place}: {type(e).__name__}.'
                )

    # Union of all detectors. Individual detector counts intentionally overlap.
    anomaly_mask = physical_flag | local_stat_flag | multivariate_flag
    combined_flag = (
        physical_flag.astype(int) + local_stat_flag.astype(int) + multivariate_flag.astype(int)
    ) >= 2

    anomaly_category_counts = {
        'physical_validity': int(physical_flag.sum()),
        'local_statistical': int(local_stat_flag.sum()),
        'multivariate': int(multivariate_flag.sum()),
        'combined': int(combined_flag.sum()),
        'total_unique': int(anomaly_mask.sum())
    }

    anomaly_reason_counts = {}
    for reason in reasons[anomaly_mask]:
        for item in str(reason).split(';'):
            item = item.strip()
            if item:
                anomaly_reason_counts[item] = anomaly_reason_counts.get(item, 0) + 1

    # descriptive summaries

    def mean_of(k): return json_num(df['_'+k].mean()) if '_'+k in df else None

    date_min=df['_date'].min(); date_max=df['_date'].max()

    cities=int(df[city_col].nunique()) if city_col else int(df['_place'].nunique())

    countries=int(df[country_col].nunique()) if country_col else 0

    # sample map markers by location; median/mean aggregation avoids drawing every repeated observation

    map_points=[]

    if lat_col and lon_col and '_lat' in df and '_lon' in df:

        agg={'_lat':'median','_lon':'median'}

        for c in ['_temp','_humidity','_wind','_precip']:

            if c in df: agg[c]='mean'

        loc=df.groupby('_place',dropna=False).agg(agg).reset_index()

        loc=loc[loc['_lat'].between(-90,90)&loc['_lon'].between(-180,180)].head(2500)

        an_places=set(df.loc[anomaly_mask,'_place'].astype(str))

        for _,r in loc.iterrows():

            p=str(r['_place']); parts=p.split(', ',1)

            map_points.append({'city':parts[0],'country':parts[1] if len(parts)>1 else '', 'lat':float(r['_lat']),'lon':float(r['_lon']),'temp_c':json_num(r.get('_temp')),'humidity':json_num(r.get('_humidity')),'wind_kph':json_num(r.get('_wind')),'precipitation_mm':json_num(r.get('_precip')),'anomaly':p in an_places})

    else: warnings_list.append('Latitude/longitude columns were not recognized; geographic map cannot show observation markers.')

    # monthly or date-binned trends: cross-sectional timestamps are not labelled as climate history

    trend=[]

    valid_date=df['_date'].notna()

    if valid_date.any():

        dated=df.loc[valid_date].copy(); dated['_period']=dated['_date'].dt.to_period('M').astype(str)

        if dated['_period'].nunique()>1:

            agg={}

            for c,k in [('_temp','temperature'),('_precip','precipitation'),('_humidity','humidity')]:

                if c in dated: agg[c]='mean'

            t=dated.groupby('_period').agg(agg).tail(36).reset_index()

            for _,r in t.iterrows(): trend.append({'label':r['_period'],'temperature':json_num(r.get('_temp')),'precipitation':json_num(r.get('_precip')),'humidity':json_num(r.get('_humidity'))})

        else: warnings_list.append('Timestamp coverage spans one month or less; no long-term trend is inferred.')

    # Seasonal summaries use meteorological seasons and latitude-based hemispheres.
    # These are descriptive summaries of available observations, not climate normals.
    seasonal = []
    if valid_date.any() and '_temp' in df:
        seasonal_df = df.loc[valid_date & df['_temp'].notna()].copy()
        if len(seasonal_df):
            seasonal_df['_month'] = seasonal_df['_date'].dt.month
            if '_lat' in seasonal_df:
                seasonal_df = seasonal_df.loc[seasonal_df['_lat'].notna()].copy()
                seasonal_df['_hemisphere'] = np.where(
                    seasonal_df['_lat'].ge(0), 'Northern', 'Southern'
                )
            else:
                seasonal_df = seasonal_df.iloc[0:0].copy()
            north_season = {
                12: 'Winter', 1: 'Winter', 2: 'Winter',
                3: 'Spring', 4: 'Spring', 5: 'Spring',
                6: 'Summer', 7: 'Summer', 8: 'Summer',
                9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
            }
            south_season = {
                12: 'Summer', 1: 'Summer', 2: 'Summer',
                3: 'Autumn', 4: 'Autumn', 5: 'Autumn',
                6: 'Winter', 7: 'Winter', 8: 'Winter',
                9: 'Spring', 10: 'Spring', 11: 'Spring'
            }
            seasonal_df['_season'] = seasonal_df.apply(
                lambda row: (north_season if row['_hemisphere'] == 'Northern' else south_season)[int(row['_month'])],
                axis=1
            )
            season_agg = {'_temp': 'mean'}
            for col in ['_humidity', '_wind', '_precip']:
                if col in seasonal_df:
                    season_agg[col] = 'mean'
            season_groups = seasonal_df.groupby(['_hemisphere', '_season'], dropna=True)
            for (hemisphere, season_name), group in season_groups:
                seasonal.append({
                    'hemisphere': str(hemisphere),
                    'season': str(season_name),
                    'observations': int(len(group)),
                    'temperature': json_num(group['_temp'].mean()),
                    'humidity': json_num(group['_humidity'].mean()) if '_humidity' in group else None,
                    'wind': json_num(group['_wind'].mean()) if '_wind' in group else None,
                    'precipitation': json_num(group['_precip'].mean()) if '_precip' in group else None
                })
    if not seasonal:
        warnings_list.append('Seasonal summaries unavailable: valid timestamped temperature observations were not found.')

    # Matched-location climate-pattern analysis.
    # Each location contributes equally after monthly aggregation, preventing cities
    # with more rows from dominating the cross-location summaries.
    climate = {
        'available': False,
        'method': 'Location-month means; equal-weight aggregation across matched locations. Descriptive only.',
        'year_over_year': [],
        'temperature_anomalies': [],
        'precipitation_variability': [],
        'coverage': {'eligible_locations': 0, 'matched_location_months': 0, 'years': []},
        'note': 'Requires repeated observations for the same locations across multiple years.'
    }

    climate_cols = ['_temp'] + (['_precip'] if '_precip' in df else [])
    climate_base = df.loc[valid_date & df['_temp'].notna(), ['_place', '_date'] + climate_cols].copy() if '_temp' in df else pd.DataFrame()
    if not climate_base.empty:
        climate_base['_year'] = climate_base['_date'].dt.year
        climate_base['_month'] = climate_base['_date'].dt.month
        monthly_agg = {'_temp': 'mean'}
        if '_precip' in climate_base:
            monthly_agg['_precip'] = 'mean'
        loc_month = (climate_base.groupby(['_place', '_year', '_month'], as_index=False)
                     .agg(monthly_agg))

        # Year-over-year comparisons only include a location-month observed in
        # both years being compared (matched panel, not changing city composition).
        yoy_rows = []
        years = sorted(int(y) for y in loc_month['_year'].unique())
        for year in years[1:]:
            prev = loc_month.loc[loc_month['_year'] == year - 1].set_index(['_place', '_month'])
            curr = loc_month.loc[loc_month['_year'] == year].set_index(['_place', '_month'])
            common = prev.index.intersection(curr.index)
            if len(common) == 0:
                continue
            p = prev.loc[common]
            c = curr.loc[common]
            temp_delta = c['_temp'].to_numpy() - p['_temp'].to_numpy()
            row = {
                'year': year,
                'matched_location_months': int(len(common)),
                'matched_locations': int(len(set(idx[0] for idx in common))),
                'temperature_change_c': json_num(float(np.mean(temp_delta))),
                'median_temperature_change_c': json_num(float(np.median(temp_delta)))
            }
            if '_precip' in loc_month:
                pp = p['_precip'].to_numpy(dtype=float)
                cp = c['_precip'].to_numpy(dtype=float)
                valid_pair = np.isfinite(pp) & np.isfinite(cp)
                row['precipitation_change_mm_per_day'] = json_num(float(np.mean(cp[valid_pair] - pp[valid_pair]))) if valid_pair.any() else None
            yoy_rows.append(row)

        # Anomaly = location's monthly mean minus that same location's
        # average for the same calendar month across all available years.
        baseline = loc_month.groupby(['_place', '_month'])['_temp'].mean().rename('_baseline')
        anomaly_df = loc_month.join(baseline, on=['_place', '_month'])
        anomaly_df['_temp_anomaly'] = anomaly_df['_temp'] - anomaly_df['_baseline']
        anomaly_summary = (anomaly_df.groupby(['_year', '_month'])['_temp_anomaly']
                           .agg(['mean', 'median', 'count']).reset_index())
        anomaly_rows = [{
            'year': int(r['_year']), 'month': int(r['_month']),
            'label': f"{int(r['_year'])}-{int(r['_month']):02d}",
            'mean_anomaly_c': json_num(r['mean']),
            'median_anomaly_c': json_num(r['median']),
            'locations': int(r['count'])
        } for _, r in anomaly_summary.iterrows()]

        precip_rows = []
        if '_precip' in loc_month:
            precip_summary = (loc_month.groupby(['_year', '_month'])['_precip']
                              .agg(['mean', 'median', 'std', 'count']).reset_index())
            precip_rows = [{
                'year': int(r['_year']), 'month': int(r['_month']),
                'label': f"{int(r['_year'])}-{int(r['_month']):02d}",
                'mean_daily_precipitation_mm': json_num(r['mean']),
                'median_daily_precipitation_mm': json_num(r['median']),
                'between_location_std_mm': json_num(r['std']),
                'locations': int(r['count'])
            } for _, r in precip_summary.iterrows()]

        eligible_locations = int(loc_month.groupby('_place')['_year'].nunique().ge(2).sum())
        climate.update({
            'available': bool(yoy_rows or anomaly_rows),
            'year_over_year': yoy_rows,
            'temperature_anomalies': anomaly_rows,
            'precipitation_variability': precip_rows,
            'coverage': {
                'eligible_locations': eligible_locations,
                'matched_location_months': int(sum(r['matched_location_months'] for r in yoy_rows)),
                'years': years
            },
            'note': ('Temperature anomalies are relative to each location’s own calendar-month average over the available dataset. '
                     'Year-over-year changes use only location-month pairs observed in both adjacent years. '
                     'Precipitation is mean daily precipitation per location-month, not a monthly accumulated total. '
                     'These short-record summaries are not climate normals or evidence of climate change.')
        })

    # Geographic comparison is by country unless a continent/region field exists.

    region_col=next((c for c in df.columns if norm(c) in ('continent','region','country')),country_col)

    regions=[]

    if region_col:

        group=df.groupby(region_col,dropna=True)

        for name,g in group:

            row={'name':str(name),'rows':int(len(g)),'temperature':json_num(g['_temp'].mean()) if '_temp' in g else 0.0,'humidity':json_num(g['_humidity'].mean()) if '_humidity' in g else 0.0,'wind':json_num(g['_wind'].mean()) if '_wind' in g else 0.0}

            regions.append(row)

        regions=sorted(regions,key=lambda r:r['rows'],reverse=True)[:15]

    # correlations among numeric weather fields

    corr_cols=[c for c in feature_cols if df[c].nunique(dropna=True)>1]

    correlations=[]

    if len(corr_cols)>=2:

        corr=df[corr_cols].corr(numeric_only=True)

        for i,a in enumerate(corr.columns):

            for b in corr.columns[i+1:]:

                v=corr.loc[a,b]

                if pd.notna(v): correlations.append({'x':a.lstrip('_'),'y':b.lstrip('_'),'value':float(v)})

    # air quality: recognize pollutant fields and correlate with weather fields

    pollutant_cols=[c for c in df.columns if any(tok in norm(c).replace('_',' ') or tok in norm(c) for tok in POLLUTANT_TOKENS)]

    air_corr=[]

    for p in pollutant_cols:

        px=safe_num(df[p])

        for w in feature_cols:

            v=pd.concat([px,df[w]],axis=1).corr().iloc[0,1]

            if pd.notna(v): air_corr.append({'feature':w.lstrip('_'),'pollutant':str(p),'correlation':float(v)})

    air_corr=sorted(air_corr,key=lambda x:abs(x['correlation']),reverse=True)[:12]

    # Forecast: only run if one location has enough repeated timestamped records. Daily aggregation + lag features.

    forecasts={'available':False,'reason':'Forecasting requires at least 40 valid, distinct timestamped observations for one location. A single snapshot cannot support honest time-series evaluation.','target':'temperature','city':'','horizon_days':int(max(1,min(args.horizon,30))),'models':[],'series':[],'feature_importance':[],'tree_feature_importance':[],'scaling_note':'StandardScaler is applied to Ridge only; tree-based models use unscaled features.'}

    target_col='_temp' if '_temp' in df else None

    if date_col and target_col and df['_date'].notna().sum()>0:

        loc_counts=df.loc[df['_date'].notna() & df[target_col].notna()].groupby('_place')['_date'].nunique()

        eligible=loc_counts[loc_counts>=40]

        if len(eligible):

            selected=args.forecast_city if args.forecast_city in eligible.index else eligible.sort_values(ascending=False).index[0]

            city_df=df[(df['_place']==selected)&df['_date'].notna()&df[target_col].notna()].sort_values('_date').copy()

            city_df=city_df.drop_duplicates(subset=['_date']).set_index('_date')

            # Daily means only if data supports multiple dates; avoid inventing daily continuity.

            ts=city_df[target_col].resample('D').mean().dropna()

            if len(ts)>=40:

                series=pd.DataFrame({'y':ts})

                for lag in [1,2,3,7,14]: series[f'lag_{lag}']=series['y'].shift(lag)

                series['rolling_mean_7']=series['y'].shift(1).rolling(7,min_periods=4).mean()

                series['rolling_std_7']=series['y'].shift(1).rolling(7,min_periods=4).std()

                series['dayofyear_sin']=np.sin(2*np.pi*series.index.day_of_year/365.25)

                series['dayofyear_cos']=np.cos(2*np.pi*series.index.day_of_year/365.25)

                series=series.dropna()

                if len(series)>=35:

                    test_n=max(7,min(30,int(np.ceil(len(series)*.2))))

                    train=series.iloc[:-test_n]; test=series.iloc[-test_n:]

                    feats=[c for c in series.columns if c!='y']; Xtr=train[feats]; ytr=train['y']; Xte=test[feats]; yte=test['y']

                    models={'Ridge':make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),Ridge(alpha=1.0)), 'Random Forest':make_pipeline(SimpleImputer(strategy='median'),RandomForestRegressor(n_estimators=250,min_samples_leaf=2,random_state=42,n_jobs=-1)), 'Extra Trees':make_pipeline(SimpleImputer(strategy='median'),ExtraTreesRegressor(n_estimators=250,min_samples_leaf=2,random_state=42,n_jobs=-1)), 'HistGradientBoosting':make_pipeline(SimpleImputer(strategy='median'),HistGradientBoostingRegressor(max_iter=150,l2_regularization=1.0,random_state=42))}

                    results=[]; predictions={}

                    baseline=np.roll(ytr.to_numpy(),1)[-len(yte):] if len(ytr) else np.repeat(float(ytr.iloc[-1]),len(yte))

                    # Persistence baseline predicts each test day's temperature from the previous observed value.

                    baseline_values=[]; previous=float(train['y'].iloc[-1])

                    for idx in test.index:

                        baseline_values.append(previous); previous=float(test.loc[idx,'y'])

                    predictions['Persistence baseline']=np.array(baseline_values)

                    for name,model in models.items():

                        try:

                            model.fit(Xtr,ytr); pred=model.predict(Xte); predictions[name]=pred

                            results.append({'name':name,'mae':float(mean_absolute_error(yte,pred)),'rmse':float(np.sqrt(mean_squared_error(yte,pred))),'r2':json_num(r2_score(yte,pred))})

                        except Exception as e: warnings_list.append(f'{name} model skipped: {type(e).__name__}.')

                    results.append({'name':'Persistence baseline','mae':float(mean_absolute_error(yte,predictions['Persistence baseline'])),'rmse':float(np.sqrt(mean_squared_error(yte,predictions['Persistence baseline']))),'r2':json_num(r2_score(yte,predictions['Persistence baseline']))})

                    # Simple equal-weight ensemble across top 2 ML models by validation/test MAE is not ideal; use training-tail validation.

                    # For honest selection, choose top two by a chronological inner validation, then evaluate on final test.

                    val_n=max(5,int(len(train)*.15)); inner_train=train.iloc[:-val_n]; inner_val=train.iloc[-val_n:]

                    val_scores=[]

                    for name,model in models.items():

                        try:

                            m=model.__class__ if False else model

                            # fit a fresh estimator through sklearn clone

                            from sklearn.base import clone

                            m=clone(model); m.fit(inner_train[feats],inner_train['y']); pv=m.predict(inner_val[feats]); val_scores.append((float(mean_absolute_error(inner_val['y'],pv)),name))

                        except Exception: pass

                    best_names=[x[1] for x in sorted(val_scores)[:2] if x[1] in predictions]

                    if len(best_names)>=2:

                        ens=np.mean(np.vstack([predictions[n] for n in best_names]),axis=0)

                        results.append({'name':'Validation-selected ensemble','mae':float(mean_absolute_error(yte,ens)),'rmse':float(np.sqrt(mean_squared_error(yte,ens))),'r2':json_num(r2_score(yte,ens))})

                    else: ens=predictions.get(best_names[0],predictions.get('Persistence baseline'))

                    forecast_rows=[]

                    for i,dt in enumerate(test.index): forecast_rows.append({'date':dt.strftime('%Y-%m-%d'),'actual':float(yte.iloc[i]),'baseline':float(predictions['Persistence baseline'][i]),'ensemble':float(ens[i]),'lower':None,'upper':None})

                    # Produce a recursive future forecast after the test evaluation. These future rows have actual=null.

                    # Fit selected models on all available history, then feed each prediction into subsequent lag features.

                    future_models=[]

                    from sklearn.base import clone

                    for name in (best_names or []):

                        if name in models:

                            try:

                                fm=clone(models[name]); fm.fit(series[feats],series['y']); future_models.append((name,fm))

                            except Exception: pass

                    history=list(series['y'].astype(float).values)

                    future_dates=pd.date_range(series.index[-1]+pd.Timedelta(days=1),periods=max(1,min(args.horizon,30)),freq='D')

                    for fdate in future_dates:

                        if len(history)<14: break

                        fr={'lag_1':history[-1],'lag_2':history[-2],'lag_3':history[-3],'lag_7':history[-7],'lag_14':history[-14], 'rolling_mean_7':float(np.mean(history[-7:])), 'rolling_std_7':float(np.std(history[-7:],ddof=1)) if len(history[-7:])>1 else 0.0, 'dayofyear_sin':float(np.sin(2*np.pi*fdate.day_of_year/365.25)), 'dayofyear_cos':float(np.cos(2*np.pi*fdate.day_of_year/365.25))}

                        fx=pd.DataFrame([{f:fr.get(f,np.nan) for f in feats}],columns=feats)

                        f_preds=[]

                        for name,fm in future_models:

                            try: f_preds.append(float(fm.predict(fx)[0]))

                            except Exception: pass

                        future_ens=float(np.mean(f_preds)) if f_preds else float(history[-1])

                        future_base=float(history[-1])

                        forecast_rows.append({'date':fdate.strftime('%Y-%m-%d'),'actual':None,'baseline':future_base,'ensemble':future_ens,'lower':None,'upper':None})

                        history.append(future_ens)

                    # Feature importance is measured on the chronological holdout, not training fit.

                    fi=[]

                    candidates=[r for r in results if r['name'] not in ('Persistence baseline','Validation-selected ensemble')]

                    if candidates:

                        best=sorted(candidates,key=lambda r:r['mae'])[0]['name']; best_model=models[best]

                        try:

                            best_model.fit(Xtr,ytr); pi=permutation_importance(best_model,Xte,yte,n_repeats=5,random_state=42,scoring='neg_mean_absolute_error')

                            raw_imp=np.maximum(0,pi.importances_mean); total=raw_imp.sum()

                            fi=[{'feature':f,'importance':float(v/total if total else 0)} for f,v in sorted(zip(feats,raw_imp),key=lambda z:z[1],reverse=True)[:10]]

                        except Exception as e: warnings_list.append(f'Permutation importance unavailable: {type(e).__name__}.')

                    # Model-native importance is reported separately from permutation importance.
                    # It is available for tree estimators and is not directly comparable to permutation scores.
                    tree_fi=[]
                    try:
                        fitted_steps = getattr(best_model, 'named_steps', {})
                        estimator = fitted_steps.get('extratreesregressor') or fitted_steps.get('randomforestregressor') or fitted_steps.get('histgradientboostingregressor')
                        native_values = getattr(estimator, 'feature_importances_', None) if estimator is not None else None
                        if native_values is not None:
                            native_values = np.maximum(0, np.asarray(native_values, dtype=float))
                            native_total = native_values.sum()
                            tree_fi = [
                                {'feature': feature, 'importance': float(value / native_total if native_total else 0)}
                                for feature, value in sorted(zip(feats, native_values), key=lambda item: item[1], reverse=True)[:10]
                            ]
                    except Exception as e:
                        warnings_list.append(f'Model-native feature importance unavailable: {type(e).__name__}.')

                    forecasts={'available':True,'reason':'Forecast metrics use a chronological held-out test segment. Results describe this location and dataset only.','target':'temperature','city':str(selected),'horizon_days':int(args.horizon),'models':results,'series':forecast_rows,'feature_importance':fi,'tree_feature_importance':tree_fi,'scaling_note':'StandardScaler is applied to Ridge only; tree-based models use unscaled features.'}

                else: forecasts['reason']='Enough timestamps were found, but lag-feature construction left too few valid rows for evaluation.'

        else: forecasts['reason']='No location has at least 40 distinct timestamped temperature observations. Forecasting is disabled rather than fabricating a time series.'

    # anomaly list, sorted by score when available

    anom=[]

    ids=df.index[anomaly_mask]

    if len(ids):

        sub=df.loc[ids].copy(); sub['_score']=scores.loc[ids].values; sub=sub.sort_values('_score',ascending=False).head(30)

        for idx,r in sub.iterrows():
            place=str(r['_place']).split(', ',1)
            detector_count = sum([
                bool(physical_flag.loc[idx]),
                bool(local_stat_flag.loc[idx]),
                bool(multivariate_flag.loc[idx])
            ])
            category = (
                'combined' if detector_count >= 2
                else 'physical_validity' if physical_flag.loc[idx]
                else 'local_statistical' if local_stat_flag.loc[idx]
                else 'multivariate'
            )
            anom.append({
                'city':place[0],
                'country':place[1] if len(place)>1 else '',
                'date':r['_date'].strftime('%Y-%m-%d') if pd.notna(r['_date']) else '',
                'temperature':json_num(r.get('_temp')),
                'score':json_num(r.get('_score')) or 0.0,
                'category':category,
                'reason':str(reasons.loc[idx]) or 'IQR / multivariate outlier'
            })

    quality=[]

    for c in raw.columns:

        quality.append({'column':str(c),'missing_pct':float(raw[c].isna().mean()*100),'unique':int(raw[c].nunique(dropna=True))})

    quality=sorted(quality,key=lambda q:q['missing_pct'],reverse=True)[:20]

    if not pollutant_cols: air_note='No recognizable air-quality/pollutant columns were found. The air-quality analysis remains unavailable; no substitute measurements were invented.'

    else: air_note=f'Found {len(pollutant_cols)} possible pollutant fields. Correlations are descriptive and do not establish causation.'

    if not temp_col: warnings_list.append('No recognized Celsius temperature field was found; temperature metrics and forecasting may be unavailable.')



    dashboard = {

        'meta': {

            'status': 'ready',

            'source': inp.name,

            'generated_at': datetime.now(timezone.utc).isoformat(),

            'rows': int(len(df)),

            'cities': cities,

            'countries': countries,

            'date_min': date_min.strftime('%Y-%m-%d') if pd.notna(date_min) else None,

            'date_max': date_max.strftime('%Y-%m-%d') if pd.notna(date_max) else None,

            'timestamp_note': 'lastupdated is treated as observation time; it is not assumed to represent a continuous historical series.',

            'warnings': warnings_list[:12]

        },



        'kpis': {

            'mean_temp_c': mean_of('temp'),

            'mean_humidity_pct': mean_of('humidity'),

            'mean_wind_kph': mean_of('wind'),

            'precipitation_rows': int(df['_precip'].notna().sum()) if '_precip' in df else 0,

            'anomaly_count': int(anomaly_mask.sum())

        },



        'anomaly_breakdown': anomaly_category_counts,

        'anomaly_reason_counts': anomaly_reason_counts,



        'map_points': map_points,

        'trend': trend,
        'seasonal': seasonal,
        'climate': climate,
        'region_basis': 'continent/region field' if region_col and norm(region_col) in ('continent', 'region') else 'country',

        'regions': regions,

        'correlations': correlations,

        'anomalies': anom,

        'forecasts': forecasts,



        'air_quality': {

            'available': bool(pollutant_cols),

            'fields': [str(c) for c in pollutant_cols],

            'correlations': air_corr,

            'note': air_note

        },



        'data_quality': quality

    }







    OUT_JSON.write_text(json.dumps(dashboard,indent=2,allow_nan=False),encoding='utf-8')

    # static figures for report and GitHub

    sns.set_theme(style='darkgrid'); plt.rcParams.update({'figure.facecolor':'#080d0c','axes.facecolor':'#0b1211','axes.edgecolor':'#263632','text.color':'#dce8e4','axes.labelcolor':'#9bb0a8','xtick.color':'#8ca199','ytick.color':'#8ca199'})

    if '_temp' in df and df['_temp'].notna().any():

        fig,ax=plt.subplots(figsize=(9,4)); sns.histplot(df['_temp'].dropna(),bins=35,kde=True,ax=ax,color='#29b8ec'); ax.set_title('Observed temperature distribution'); ax.set_xlabel('Temperature (source units; Celsius expected)'); fig.tight_layout(); fig.savefig(OUT_DIR/'temperature_distribution.png',dpi=150); plt.close(fig)

    if len(corr_cols)>=2:

        fig,ax=plt.subplots(figsize=(8,6)); sns.heatmap(df[corr_cols].corr(),annot=True,fmt='.2f',cmap='coolwarm',center=0,ax=ax); ax.set_title('Weather feature correlation'); fig.tight_layout(); fig.savefig(OUT_DIR/'correlation_heatmap.png',dpi=150); plt.close(fig)

    if trend:

        tt=pd.DataFrame(trend); fig,ax=plt.subplots(figsize=(9,4)); ax.plot(tt['label'],tt['temperature'],color='#29b8ec',label='Mean temperature'); ax.tick_params(axis='x',rotation=45); ax.set_title('Observed monthly temperature summary (not a climate normal)'); ax.legend(); fig.tight_layout(); fig.savefig(OUT_DIR/'observed_trend.png',dpi=150); plt.close(fig)

    summary=['# WeatherScope — Automated Analysis Summary','',f'- Source file: `{inp.name}`',f'- Rows in source: {original_rows:,}',f'- Rows after exact duplicate removal: {len(df):,}',f'- Unique locations: {cities:,}',f'- Countries: {countries:,}',f'- Parsed timestamp range: {dashboard["meta"]["date_min"] or "unavailable"} to {dashboard["meta"]["date_max"] or "unavailable"}',f'- Mean temperature: {fmt_md(mean_of("temp"), "°C")}',f'- Mean humidity: {fmt_md(mean_of("humidity"), "%")}',f'- Flagged anomalies: {int(anomaly_mask.sum()):,}','', '## Anomaly detection breakdown','', '| Detector | Flagged observations |','|---|---:|']
    for detector, count in anomaly_category_counts.items():
        summary.append(f'| {detector.replace("_", " ").title()} | {count:,} |')
    summary += ['', 'Detector counts overlap; total_unique is the union of all detector flags.', '', '## Forecast evaluation', '']

    if forecasts['available']:

        summary += [f"- Location evaluated: {forecasts['city']}", '- Validation method: chronological inner validation for ensemble selection; final chronological test segment for reported model metrics.', '', '| Model | MAE | RMSE | R² |','|---|---:|---:|---:|']

        for m in forecasts['models']: summary.append(f"| {m['name']} | {m['mae']:.4f} | {m['rmse']:.4f} | {m['r2'] if m['r2'] is not None else 'N/A'} |")

    else: summary += [f"Forecasting not run: {forecasts['reason']}",'','This is a valid limitation, not a model failure. A snapshot dataset cannot support a reliable future forecast without repeated observations.']

    summary += ['', '## Seasonal summaries', 'Seasonal means are descriptive summaries of available observations using meteorological seasons and latitude-based hemispheres; they are not climate normals.']
    if seasonal:
        summary += ['', '| Hemisphere | Season | Observations | Mean temperature (°C) | Mean humidity (%) | Mean wind (km/h) | Mean precipitation (mm) |', '|---|---|---:|---:|---:|---:|---:|']
        for item in seasonal:
            summary.append(f"| {item['hemisphere']} | {item['season']} | {item['observations']:,} | {fmt_md(item['temperature'])} | {fmt_md(item['humidity'])} | {fmt_md(item['wind'])} | {fmt_md(item['precipitation'])} |")
    else:
        summary.append('Seasonal summaries unavailable for this input.')
    summary += ['', '## Matched-location climate-pattern analysis', climate['note']]
    if climate['year_over_year']:
        summary += ['', '| Year | Matched locations | Matched location-months | Mean temperature change (°C) | Median change (°C) |', '|---:|---:|---:|---:|---:|']
        for item in climate['year_over_year']:
            summary.append(f"| {item['year']} | {item['matched_locations']} | {item['matched_location_months']:,} | {fmt_md(item['temperature_change_c'])} | {fmt_md(item['median_temperature_change_c'])} |")
    else:
        summary.append('Year-over-year comparison unavailable: no adjacent-year location-month pairs were found.')
    summary += ['', 'Temperature anomaly values are location-specific deviations from that location’s average for the same calendar month.']
    if climate['temperature_anomalies']:
        summary += ['', '| Month | Mean anomaly (°C) | Median anomaly (°C) | Locations |', '|---|---:|---:|---:|']
        for item in climate['temperature_anomalies'][-24:]:
            summary.append(f"| {item['label']} | {fmt_md(item['mean_anomaly_c'])} | {fmt_md(item['median_anomaly_c'])} | {item['locations']:,} |")
    if climate['precipitation_variability']:
        summary += ['', 'Mean daily precipitation is aggregated within each location-month; it is not a monthly rainfall total.', '', '| Month | Mean daily precipitation (mm) | Between-location SD (mm) | Locations |', '|---|---:|---:|---:|']
        for item in climate['precipitation_variability'][-24:]:
            summary.append(f"| {item['label']} | {fmt_md(item['mean_daily_precipitation_mm'])} | {fmt_md(item['between_location_std_mm'])} | {item['locations']:,} |")
    summary += ['', '## Preprocessing and feature scaling', '- Exact duplicate rows are removed.', '- Weather fields are converted to numeric values; values outside broad physical sanity ranges are excluded from derived summaries and retained as anomaly flags.', '- Missing values are handled per analysis/model; median imputation is used in model pipelines.', '- StandardScaler is applied to Ridge only. Tree-based models do not require feature scaling.', '', '## Geographic analysis', f"- Geographic grouping basis: {dashboard['region_basis']}.", '- Country comparisons reflect the observations present in this dataset and may not represent population-weighted or area-weighted climate conditions.', '', '## Air quality', air_note, '', '## Data and interpretation limitations', '- Outlier flags identify statistical unusualness, not confirmed meteorological extremes or data errors.', '- Correlation does not imply causation.', '- A `lastupdated` column alone does not establish long-term climate history.', '', '## Pipeline warnings'] + [f'- {w}' for w in warnings_list] + ['', '## Figures', '- `analysis/output/temperature_distribution.png` (when temperature is available)', '- `analysis/output/correlation_heatmap.png` (when sufficient numeric features are available)', '- `analysis/output/observed_trend.png` (when multiple monthly bins exist)', '']

    REPORT.write_text('\n'.join(summary),encoding='utf-8')

    print(f'Wrote {OUT_JSON.relative_to(ROOT)}'); print(f'Wrote {REPORT.relative_to(ROOT)}'); print(f'Rows: {len(df):,}; locations: {cities:,}; anomaly flags: {int(anomaly_mask.sum()):,}; forecast available: {forecasts["available"]}')



def fmt_md(v,suffix=''):

    return 'unavailable' if v is None else f'{v:.2f}{suffix}'

if __name__=='__main__':

    warnings.filterwarnings('ignore', category=FutureWarning)

    main()
