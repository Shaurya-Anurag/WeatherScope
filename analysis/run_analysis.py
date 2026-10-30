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
 'city':['location_name','city','location','name'], 'country':['country','country_name'],
 'lat':['latitude','lat'], 'lon':['longitude','lon','lng'],
 'date':['last_updated','lastupdated','last update','datetime','date','timestamp'],
 'temp':['temperature_celsius','temp_c','temperature','temp','temperature (c)'],
 'humidity':['humidity','humidity_pct','relative_humidity'], 'wind':['wind_kph','wind_speed_kph','wind_speed','wind_mph'],
 'precip':['precip_mm','precipitation_mm','precipitation','rain_mm'], 'pressure':['pressure_mb','pressure_hpa','pressure'],
 'cloud':['cloud','cloud_cover','cloud_cover_pct'], 'uv':['uv_index','uv'],
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
    for c,(lo,hi) in physical_ranges.items():
        if c in df:
            mask=df[c].notna() & ~df[c].between(lo,hi)
            invalid_counts[c]=int(mask.sum())
            if mask.any(): df.loc[mask,c]=np.nan
    if sum(invalid_counts.values()): warnings_list.append('Values outside broad physical sanity ranges were set to missing for derived summaries; raw source file remains unchanged.')
    if not city_group(df,city_col,country_col).nunique(): warnings_list.append('No location identifiers found.')
    df['_place']=city_group(df,city_col,country_col)
    # IQR anomaly flags per available city/region feature; Isolation Forest is supplementary.
    feature_cols=[c for c in ['_temp','_humidity','_wind','_precip','_pressure','_cloud','_uv'] if c in df and df[c].notna().sum()>10]
    anomaly_mask=pd.Series(False,index=df.index); reasons=pd.Series('',index=df.index,dtype=object); scores=pd.Series(0.0,index=df.index)
    for c in feature_cols:
        q1,q3=df[c].quantile([.25,.75]); iqr=q3-q1
        if pd.notna(iqr) and iqr>0:
            m=df[c].notna() & ((df[c]<q1-1.5*iqr)|(df[c]>q3+1.5*iqr))
            anomaly_mask |= m
            reasons.loc[m]=reasons.loc[m].apply(lambda s: (s+', ' if s else '')+c[1:]+' IQR')
    if len(feature_cols)>=2 and len(df)>=50:
        try:
            X=df[feature_cols].replace([np.inf,-np.inf],np.nan)
            X=SimpleImputer(strategy='median').fit_transform(X)
            iso=IsolationForest(n_estimators=150,contamination='auto',random_state=42,n_jobs=-1)
            labels=iso.fit_predict(X); dec=-iso.decision_function(X)
            # Keep IF as a distinct multivariate flag; no claim that every flagged point is erroneous.
            if_flag=pd.Series(labels==-1,index=df.index); anomaly_mask |= if_flag
            scores=pd.Series(dec,index=df.index)
            reasons.loc[if_flag & (reasons=='')]='multivariate Isolation Forest'
        except Exception as e: warnings_list.append(f'Isolation Forest skipped: {type(e).__name__}.')
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
    # region comparison is by country unless a continent field exists; no external geo lookup.
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
    forecasts={'available':False,'reason':'Forecasting requires at least 40 valid, distinct timestamped observations for one location. A single snapshot cannot support honest time-series evaluation.','target':'temperature','city':'','horizon_days':int(max(1,min(args.horizon,30))),'models':[],'series':[],'feature_importance':[]}
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
                series['dayofyear_sin']=np.sin(2*np.pi*series.index.dayofyear/365.25)
                series['dayofyear_cos']=np.cos(2*np.pi*series.index.dayofyear/365.25)
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
                        fr={'lag_1':history[-1],'lag_2':history[-2],'lag_3':history[-3],'lag_7':history[-7],'lag_14':history[-14], 'rolling_mean_7':float(np.mean(history[-7:])), 'rolling_std_7':float(np.std(history[-7:],ddof=1)) if len(history[-7:])>1 else 0.0, 'dayofyear_sin':float(np.sin(2*np.pi*fdate.dayofyear/365.25)), 'dayofyear_cos':float(np.cos(2*np.pi*fdate.dayofyear/365.25))}
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
                    forecasts={'available':True,'reason':'Forecast metrics use a chronological held-out test segment. Results describe this location and dataset only.','target':'temperature','city':str(selected),'horizon_days':int(args.horizon),'models':results,'series':forecast_rows,'feature_importance':fi}
                else: forecasts['reason']='Enough timestamps were found, but lag-feature construction left too few valid rows for evaluation.'
        else: forecasts['reason']='No location has at least 40 distinct timestamped temperature observations. Forecasting is disabled rather than fabricating a time series.'
    # anomaly list, sorted by score when available
    anom=[]
    ids=df.index[anomaly_mask]
    if len(ids):
        sub=df.loc[ids].copy(); sub['_score']=scores.loc[ids].values; sub=sub.sort_values('_score',ascending=False).head(30)
        for idx,r in sub.iterrows():
            place=str(r['_place']).split(', ',1); anom.append({'city':place[0],'country':place[1] if len(place)>1 else '', 'date':r['_date'].strftime('%Y-%m-%d') if pd.notna(r['_date']) else '', 'temperature':json_num(r.get('_temp')),'score':json_num(r.get('_score')) or 0.0,'reason':str(reasons.loc[idx]) or 'IQR / multivariate outlier'})
    quality=[]
    for c in raw.columns:
        quality.append({'column':str(c),'missing_pct':float(raw[c].isna().mean()*100),'unique':int(raw[c].nunique(dropna=True))})
    quality=sorted(quality,key=lambda q:q['missing_pct'],reverse=True)[:20]
    if not pollutant_cols: air_note='No recognizable air-quality/pollutant columns were found. The air-quality analysis remains unavailable; no substitute measurements were invented.'
    else: air_note=f'Found {len(pollutant_cols)} possible pollutant fields. Correlations are descriptive and do not establish causation.'
    if not temp_col: warnings_list.append('No recognized Celsius temperature field was found; temperature metrics and forecasting may be unavailable.')
    dashboard={'meta':{'status':'ready','source':inp.name,'generated_at':datetime.now(timezone.utc).isoformat(),'rows':int(len(df)),'cities':cities,'countries':countries,'date_min':date_min.strftime('%Y-%m-%d') if pd.notna(date_min) else None,'date_max':date_max.strftime('%Y-%m-%d') if pd.notna(date_max) else None,'timestamp_note':'lastupdated is treated as observation time; it is not assumed to represent a continuous historical series.','warnings':warnings_list[:12]},'kpis':{'mean_temp_c':mean_of('temp'),'mean_humidity_pct':mean_of('humidity'),'mean_wind_kph':mean_of('wind'),'precipitation_rows':int(df['_precip'].notna().sum()) if '_precip' in df else 0,'anomaly_count':int(anomaly_mask.sum())},'map_points':map_points,'trend':trend,'regions':regions,'correlations':correlations,'anomalies':anom,'forecasts':forecasts,'air_quality':{'available':bool(pollutant_cols),'fields':[str(c) for c in pollutant_cols],'correlations':air_corr,'note':air_note},'data_quality':quality}
    OUT_JSON.write_text(json.dumps(dashboard,indent=2,allow_nan=False),encoding='utf-8')
    # static figures for report and GitHub
    sns.set_theme(style='darkgrid'); plt.rcParams.update({'figure.facecolor':'#080d0c','axes.facecolor':'#0b1211','axes.edgecolor':'#263632','text.color':'#dce8e4','axes.labelcolor':'#9bb0a8','xtick.color':'#8ca199','ytick.color':'#8ca199'})
    if '_temp' in df and df['_temp'].notna().any():
        fig,ax=plt.subplots(figsize=(9,4)); sns.histplot(df['_temp'].dropna(),bins=35,kde=True,ax=ax,color='#29b8ec'); ax.set_title('Observed temperature distribution'); ax.set_xlabel('Temperature (source units; Celsius expected)'); fig.tight_layout(); fig.savefig(OUT_DIR/'temperature_distribution.png',dpi=150); plt.close(fig)
    if len(corr_cols)>=2:
        fig,ax=plt.subplots(figsize=(8,6)); sns.heatmap(df[corr_cols].corr(),annot=True,fmt='.2f',cmap='coolwarm',center=0,ax=ax); ax.set_title('Weather feature correlation'); fig.tight_layout(); fig.savefig(OUT_DIR/'correlation_heatmap.png',dpi=150); plt.close(fig)
    if trend:
        tt=pd.DataFrame(trend); fig,ax=plt.subplots(figsize=(9,4)); ax.plot(tt['label'],tt['temperature'],color='#29b8ec',label='Mean temperature'); ax.tick_params(axis='x',rotation=45); ax.set_title('Observed monthly temperature summary (not necessarily climate trend)'); ax.legend(); fig.tight_layout(); fig.savefig(OUT_DIR/'observed_trend.png',dpi=150); plt.close(fig)
    summary=['# WeatherScope — Automated Analysis Summary','',f'- Source file: `{inp.name}`',f'- Rows in source: {original_rows:,}',f'- Rows after exact duplicate removal: {len(df):,}',f'- Unique locations: {cities:,}',f'- Countries: {countries:,}',f'- Parsed timestamp range: {dashboard["meta"]["date_min"] or "unavailable"} to {dashboard["meta"]["date_max"] or "unavailable"}',f'- Mean temperature: {fmt_md(mean_of("temp"), "°C")}',f'- Mean humidity: {fmt_md(mean_of("humidity"), "%")}',f'- Flagged anomalies: {int(anomaly_mask.sum()):,}','', '## Forecast evaluation','']
    if forecasts['available']:
        summary += [f"- Location evaluated: {forecasts['city']}", '- Validation method: chronological inner validation for ensemble selection; final chronological test segment for reported model metrics.', '', '| Model | MAE | RMSE | R² |','|---|---:|---:|---:|']
        for m in forecasts['models']: summary.append(f"| {m['name']} | {m['mae']:.4f} | {m['rmse']:.4f} | {m['r2'] if m['r2'] is not None else 'N/A'} |")
    else: summary += [f"Forecasting not run: {forecasts['reason']}",'','This is a valid limitation, not a model failure. A snapshot dataset cannot support a reliable future forecast without repeated observations.']
    summary += ['', '## Air quality', air_note, '', '## Data and interpretation limitations', '- Outlier flags identify statistical unusualness, not confirmed meteorological extremes or data errors.', '- Correlation does not imply causation.', '- A `lastupdated` column alone does not establish long-term climate history.', '- Country comparisons reflect the observations present in this dataset and may not represent population-weighted or area-weighted climate conditions.', '', '## Pipeline warnings'] + [f'- {w}' for w in warnings_list] + ['', '## Figures', '- `analysis/output/temperature_distribution.png` (when temperature is available)', '- `analysis/output/correlation_heatmap.png` (when sufficient numeric features are available)', '- `analysis/output/observed_trend.png` (when multiple monthly bins exist)', '']
    REPORT.write_text('\n'.join(summary),encoding='utf-8')
    print(f'Wrote {OUT_JSON.relative_to(ROOT)}'); print(f'Wrote {REPORT.relative_to(ROOT)}'); print(f'Rows: {len(df):,}; locations: {cities:,}; anomaly flags: {int(anomaly_mask.sum()):,}; forecast available: {forecasts["available"]}')

def fmt_md(v,suffix=''):
    return 'unavailable' if v is None else f'{v:.2f}{suffix}'
if __name__=='__main__':
    warnings.filterwarnings('ignore', category=FutureWarning)
    main()
