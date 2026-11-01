

'use client';




import { useEffect, useRef, useState } from 'react';

import type { CSSProperties, ReactNode } from 'react';

import {

  Activity,

  CloudRain,

  Database,

  Globe2,

  Wind,

  Waves,

  ShieldAlert,

  Thermometer,

  Layers3,

  CircleHelp,

  Gauge,

  Download,

} from 'lucide-react';

import {

  Area,

  Bar,

  BarChart,

  CartesianGrid,

  ComposedChart,

  Line,

  LineChart,

  ReferenceLine,

  ResponsiveContainer,

  Tooltip,

  XAxis,

  YAxis,

} from 'recharts';

import {

  ComposableMap,

  Geographies,

  Geography,

  Marker,

} from 'react-simple-maps';

import world from 'world-atlas/countries-110m.json';

import { fmt } from '../format';

import type { DashboardData } from '../types';



const GEO_URL = world;

const palette = ['#21d4c2', '#29a8ef', '#f6bc42', '#f16b4f'];



type MapPoint = {

  city: string;

  country: string;

  lon: number;

  lat: number;

  temp_c: number | null;

  anomaly: boolean;

};



type WorldMapProps = {

  points: MapPoint[];

};



type GeographyItem = {

  rsmKey: string;

};



function Panel({

  title,

  children,

  className = '',

}: {

  title: string;

  children: ReactNode;

  className?: string;

}) {

  return (

    <section className={`panel ${className}`}>

      <div className="panel-head">

        <span>{title}</span>

      </div>

      {children}

    </section>

  );

}



function Empty({

  message = 'Run the Python pipeline to populate this panel with real dataset results.',

}: {

  message?: string;

}) {

  return (

    <div className="empty">

      <Database size={18} />

      <span>{message}</span>

    </div>

  );

}



function temperatureColor(temp: number | null): string {

  if (temp === null || !Number.isFinite(temp)) {

    return '#718582';

  }



  if (temp < 5) return '#2589f4';

  if (temp < 20) return '#22d4c1';



  return '#f6bd42';

}



function WorldMap({ points }: WorldMapProps) {
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);

  // ADD THIS HERE
  useEffect(() => {
    if (!expanded) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [expanded]);





  const dragOrigin = useRef<{

    x: number;

    y: number;

    panX: number;

    panY: number;

  } | null>(null);



  const zoomBy = (amount: number) => {

    setZoom((current) =>

      Math.max(

        1,

        Math.min(4, Number((current + amount).toFixed(2))),

      ),

    );

  };



  const resetView = () => {

    setZoom(1);

    setPan({ x: 0, y: 0 });

  };



  const controlStyle: CSSProperties = {

    background: '#101b1a',

    color: '#a9d8d2',

    border: '1px solid #294441',

    borderRadius: 6,

    padding: '7px 10px',

    fontSize: 12,

    cursor: 'pointer',

  };



  return (

    <div

      className={`map-wrap ${expanded ? 'map-expanded' : ''}`}
      role={expanded ? 'dialog' : undefined}
      aria-modal={expanded ? true : undefined}
      aria-label={
        expanded ? 'Expanded interactive world map' : undefined
      }
      style={

        expanded

          ? {

              position: 'fixed',

              inset: 12,

              zIndex: 1000,

              height: 'auto',

              margin: 0,

              padding: 16,

              background: '#050a09',

              border: '1px solid #294441',

              borderRadius: 12,

              boxShadow: '0 0 0 100vmax rgba(0,0,0,0.85)',

              display: 'flex',

              flexDirection: 'column',

              overflow: 'hidden',

            }

          : undefined

      }

    >

      <div

        className="map-controls"

        style={{

          position: 'absolute',

          top: 10,

          right: 10,

          zIndex: 10,

          display: 'flex',

          gap: 6,

          flexWrap: 'wrap',

        }}

      >

        <button

          type="button"

          style={controlStyle}

          onClick={() => zoomBy(0.25)}

          aria-label="Zoom in"

          title="Zoom in"

        >

          +

        </button>



        <button

          type="button"

          style={controlStyle}

          onClick={() => zoomBy(-0.25)}

          aria-label="Zoom out"

          title="Zoom out"

        >

          −

        </button>



        <button

          type="button"

          style={controlStyle}

          onClick={resetView}

          title="Reset zoom and pan"

        >

          Reset

        </button>



        <button

          type="button"

          style={controlStyle}

          onClick={() => setExpanded((value) => !value)}

          title={expanded ? 'Exit expanded map' : 'Expand map'}

        >

          {expanded ? 'Exit expanded' : 'Expand map'}

        </button>

      </div>



      <div

        className="map-viewport"

        tabIndex={0}

        aria-label="Interactive world map. Drag to pan, use plus and minus or the mouse wheel to zoom. Press Escape to exit expanded view."

        onPointerDown={(event) => {

          if (event.button !== 0) return;



          dragOrigin.current = {

            x: event.clientX,

            y: event.clientY,

            panX: pan.x,

            panY: pan.y,

          };



          event.currentTarget.setPointerCapture(event.pointerId);

          setDragging(true);

        }}

        onPointerMove={(event) => {

          if (!dragOrigin.current) return;



          const origin = dragOrigin.current;



          setPan({

            x: Math.max(

              -1200,

              Math.min(

                1200,

                origin.panX + event.clientX - origin.x,

              ),

            ),

            y: Math.max(

              -700,

              Math.min(

                700,

                origin.panY + event.clientY - origin.y,

              ),

            ),

          });

        }}

        onPointerUp={() => {

          dragOrigin.current = null;

          setDragging(false);

        }}

        onPointerCancel={() => {

          dragOrigin.current = null;

          setDragging(false);

        }}

        onWheel={(event) => {

          event.preventDefault();

          zoomBy(event.deltaY < 0 ? 0.1 : -0.1);

        }}


        style={{

          position: 'relative',

          overflow: 'hidden',

          width: '100%',

          height: expanded ? undefined : 340,

          minHeight: expanded ? 0 : 260,

          flex: expanded ? '1 1 auto' : undefined,

          touchAction: 'none',

          cursor: dragging ? 'grabbing' : 'grab',

          outline: 'none',

        }}

      >

        <ComposableMap

          projectionConfig={{ scale: 142 }}

          width={900}

          height={470}

          style={{

            width: '100%',

            height: '100%',

            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,

            transformOrigin: 'center center',

            transition: dragging

              ? 'none'

              : 'transform 120ms ease-out',

          }}

        >

          <Geographies geography={GEO_URL}>

            {({

              geographies,

            }: {

              geographies: GeographyItem[];

            }) =>

              geographies.map((geo) => (

                <Geography

                  key={geo.rsmKey}

                  geography={geo}

                  fill="#111b1c"

                  stroke="#283536"

                  strokeWidth={0.45}

                  style={{

                    default: { outline: 'none' },

                    hover: {

                      fill: '#1b3332',

                      outline: 'none',

                    },

                    pressed: { outline: 'none' },

                  }}

                />

              ))

            }

          </Geographies>



          {points.map((point, index) => {

            const temp = point.temp_c;



            const validTemperature =

              temp !== null && Number.isFinite(temp);



            const fill = temperatureColor(temp);



            const radius = validTemperature

              ? Math.max(

                  2.1,

                  Math.min(6, 2 + (temp as number) / 14),

                )

              : 2.5;



            const anomalyColor =
              temp !== null && temp < 5
                ? '#2589f4'
                : '#ff5e48';



            return (

              <Marker

                key={`${point.city}-${point.country}-${index}`}

                coordinates={[point.lon, point.lat]}

              >

                <circle

                  r={radius}

                  fill={fill}

                  stroke={

                    point.anomaly

                      ? anomalyColor

                      : '#07100f'

                  }

                  strokeWidth={point.anomaly ? 2 : 0.8}

                  opacity={0.95}

                >

                  <title>

                    {`${point.city}, ${point.country} · ${

                      validTemperature

                        ? `${fmt(temp)}°C`

                        : 'Temperature unavailable'

                    } · ${

                      point.anomaly

                        ? 'Location has one or more historical anomaly flags'

                        : 'No historical anomaly flag in this location summary'

                    }`}

                  </title>

                </circle>



                {point.anomaly && (

                  <circle

                    r={radius + 2.5}

                    fill="none"

                    stroke={anomalyColor}

                    strokeWidth={0.8}

                    opacity={0.65}

                  />

                )}

              </Marker>

            );

          })}

        </ComposableMap>



        {!points.length && (

          <div className="map-overlay">

            <Globe2 size={22} />

            <b>Global observation field</b>

            <span>

              World map populates from dataset coordinates.

            </span>

          </div>

        )}

      </div>



      <div className="map-legend">

        <span>

          <i style={{ background: '#2589f4' }} />

          Cool

        </span>

        <span>

          <i style={{ background: '#22d4c1' }} />

          Mild

        </span>

        <span>

          <i style={{ background: '#f6bd42' }} />

          Warm

        </span>

        <span>
          <i
            className="legend-outline"
            style={{ borderColor: '#2589f4' }}
          />
          Cold anomaly (&lt;5°C)
        </span>
        <span>
          <i
            className="legend-outline"
            style={{ borderColor: '#ff5e48' }}
          />
          Other anomaly
        </span>

      </div>

    </div>

  );

}



export default function Dashboard({

  d,

}: {

  d: DashboardData;

}) {

  const active = d.meta.status === 'ready';
  const missingColumns = d.data_quality.filter((item) => item.missing_pct > 0);
  const anomalyReasons = Object.entries(d.anomaly_reason_counts ?? {})
    .sort((a, b) => b[1] - a[1]);
  const extras = d as DashboardData & {
    anomaly_breakdown?: Record<string, number>;
    seasonal?: Array<{
      hemisphere: string;
      season: string;
      observations: number;
      temperature: number | null;
      humidity: number | null;
      wind: number | null;
      precipitation: number | null;
    }>;
    region_basis?: string;

    continent_regions?: Array<{
      name: string;
      rows: number;
      locations: number;
      temperature: number | null;
      humidity: number | null;
      wind: number | null;
      precipitation: number | null;
      aggregation_method: string;
    }>;

    continent_coverage?: {
      classified_rows: number;
      unclassified_rows: number;
      classification_percentage: number;
    };




    forecasts: DashboardData['forecasts'] & {
      tree_feature_importance?: Array<{ feature: string; importance: number }>;
      scaling_note?: string;
    };
  };



  return (

    <main className="shell">

      <header className="topbar">

        <div className="brand">

          <div className="brand-mark">

            <Activity size={19} />

          </div>



          <div>

            <div className="brand-name">

              WEATHERSCOPE <span>/ GLOBAL</span>

            </div>

            <div className="brand-sub">

              CLIMATE INTELLIGENCE SYSTEM

            </div>

          </div>

        </div>



        <nav>

          <a className="active" href="#overview">Overview</a>

          <a href="#environment">Environment</a>

          <a href="#climate">Climate patterns</a>

          <a href="#forecast">Forecast lab</a>

          <a href="#anomalies">Anomalies</a>

          

        </nav>



        <div className="top-actions">

          <span

            className={`status-dot ${active ? 'on' : ''}`}

          />

          <span className="status-text">

            {active ? 'LOCAL DATA READY' : 'AWAITING DATA'}

          </span>



          <button

            className="utility-btn"

            title="Export summary"

            type="button"

            onClick={() => {

              const blob = new Blob(

                [JSON.stringify(d, null, 2)],

                { type: 'application/json' },

              );



              const url = URL.createObjectURL(blob);

              const link = document.createElement('a');



              link.href = url;

              link.download = 'weatherscope-summary.json';

              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);

            }}

          >

            <Download size={15} />

          </button>

        </div>

      </header>



      <div className="page-intro">

        <div>

          <div className="eyebrow">

            <span className="pulse" />

            WEATHER OBSERVATION NETWORK

            <span className="sep">/</span>

            RESEARCH WORKSPACE

          </div>



          <h1>

            Global weather, <em>decoded.</em>

          </h1>



          <p>

            Explore atmospheric patterns, detect unusual

            observations, and evaluate forecasts against

            held-out data.

          </p>

        </div>



        <div className="updated">

          <span>DATA SNAPSHOT</span>

          <b>

            {d.meta.generated_at

              ? new Date(d.meta.generated_at).toLocaleString()

              : 'NOT PROCESSED'}

          </b>

          <small>Global Weather Repository · Open-Meteo Archive enrichment</small>

        </div>

      </div>



      <section id="overview" className="kpis">

        <div className="kpi">

          <div className="kpi-label">

            OBSERVATIONS <Database size={14} />

          </div>

          <div className="kpi-value">

            {d.meta.rows

              ? d.meta.rows.toLocaleString()

              : '—'}

          </div>

          <div className="kpi-foot">Rows after validation</div>

        </div>



        <div className="kpi">

          <div className="kpi-label">

            MEAN TEMPERATURE <Thermometer size={14} />

          </div>

          <div className="kpi-value">

            {fmt(d.kpis.mean_temp_c)}

            <small>°C</small>

          </div>

          <div className="kpi-foot">

            Available observations

          </div>

        </div>



        <div className="kpi">

          <div className="kpi-label">

            MEAN HUMIDITY <Waves size={14} />

          </div>

          <div className="kpi-value">

            {fmt(d.kpis.mean_humidity_pct)}

            <small>%</small>

          </div>

          <div className="kpi-foot">Relative humidity</div>

        </div>



        <div className="kpi">

          <div className="kpi-label">

            FLAGGED ANOMALIES <ShieldAlert size={14} />

          </div>

          <div className="kpi-value alert">

            {d.kpis.anomaly_count != null

              ? d.kpis.anomaly_count.toLocaleString()

              : '—'}

          </div>

          <div className="kpi-foot">

            Flags, not confirmed events

          </div>

        </div>

      </section>



      <div className="main-grid">

        <Panel

          title="Global observation field"

          className="map-panel"

        >

          <div className="map-meta">

            <span>

              <Globe2 size={13} />

              CITY-LEVEL OBSERVATIONS

            </span>

            <span>

              {d.meta.cities

                ? `${d.meta.cities} locations`

                : 'NO LOCATION DATA'}

            </span>

          </div>



          <WorldMap

            points={d.map_points as MapPoint[]}

          />



          <div className="map-footer">

            <span>

              <i className="legend-dot cyan" />

              Temperature observation

            </span>

            <span>

              <i className="legend-dot red" />

              Historical anomaly flag (blue = cold, red = other)

            </span>

            <span className="map-note">

              Fill = mean temperature · Blue outline = cold flag · Red outline = other flag

            </span>

          </div>

        </Panel>



        <div className="right-stack">

          <Panel title="Weather profile">

            <div className="mini-stat-grid">

              <div>

                <span>Mean wind</span>

                <b>

                  {fmt(d.kpis.mean_wind_kph)}{' '}

                  <small>km/h</small>

                </b>

                <Wind size={15} />

              </div>



              <div>

                <span>Precipitation records</span>

                <b>

                  {d.kpis.precipitation_rows.toLocaleString()}

                </b>

                <CloudRain size={15} />

              </div>

            </div>



            <div className="subhead">OBSERVATION WINDOW</div>



            <div className="date-range">

              <span>

                From <b>{d.meta.date_min ?? '—'}</b>

              </span>

              <span>

                To <b>{d.meta.date_max ?? '—'}</b>

              </span>

            </div>



            {d.meta.warnings.slice(0, 2).map(

              (warning, index) => (

                <div className="notice" key={index}>

                  <CircleHelp size={14} />

                  {warning}

                </div>

              ),

            )}

          </Panel>



          <Panel title="Data integrity">

            <div className="integrity-score">

              <div>

                <b>{active ? 'READY' : '—'}</b>

                <span>PIPELINE STATUS</span>

              </div>

              <div className="integrity-icon">

                <Layers3 size={23} />

              </div>

            </div>



            {d.data_quality.length ? (
              <>
                <div className="quality-row">
                  <span>Columns checked</span>
                  <div className="quality-track"><i style={{ width: '100%' }} /></div>
                  <b>{d.data_quality.length}</b>
                </div>
                <div className="quality-row">
                  <span>Columns with missing values</span>
                  <div className="quality-track">
                    <i style={{ width: `${(missingColumns.length / d.data_quality.length) * 100}%` }} />
                  </div>
                  <b>{missingColumns.length}</b>
                </div>
                {missingColumns.length ? (
                  missingColumns
                    .sort((a, b) => b.missing_pct - a.missing_pct)
                    .slice(0, 4)
                    .map((quality) => (
                      <div className="quality-row" key={quality.column}>
                        <span>{quality.column}</span>
                        <div className="quality-track">
                          <i style={{ width: `${Math.min(100, quality.missing_pct)}%` }} />
                        </div>
                        <b>{fmt(quality.missing_pct)}%</b>
                      </div>
                    ))
                ) : (
                  <div className="notice">
                    <Layers3 size={14} />
                    No missing values detected across the displayed dataset columns.
                  </div>
                )}
                <div className="model-foot">
                  Unique-value counts are available for {d.data_quality.length} columns.
                </div>
              </>
            ) : (
              <Empty message="Missingness report appears after processing." />
            )}

          </Panel>

        </div>

      </div>





      <div className="lower-grid" id="environment">
        <Panel title="Weather trend profile">
          <div className="chart-legend">
            <span>
              <i style={{ background: '#29b8ec' }} />
              Temperature °C
            </span>
            <span>
              <i style={{ background: '#f6bc42' }} />
              Precipitation mm
            </span>
          </div>
          {d.trend.length ? (
            <ResponsiveContainer width="100%" height={210}>
              <ComposedChart data={d.trend}>
                <CartesianGrid stroke="#263332" strokeDasharray="3 4" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#7d918e', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="t"
                  tick={{ fill: '#7d918e', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="p"
                  orientation="right"
                  tick={{ fill: '#7d918e', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: '#0c1413',
                    border: '1px solid #2c4140',
                    borderRadius: 8,
                  }}
                />
                <Area
                  yAxisId="t"
                  type="monotone"
                  dataKey="temperature"
                  stroke="#29b8ec"
                  fill="#29b8ec"
                  fillOpacity={0.13}
                  connectNulls
                />
                <Line
                  yAxisId="p"
                  type="monotone"
                  dataKey="precipitation"
                  stroke="#f6bc42"
                  dot={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <Empty />
          )}
        </Panel>

        <Panel title={`Regional comparison · ${extras.region_basis ?? "country"}`}>
          {d.regions.length ? (
            <ResponsiveContainer width="100%" height={235}>
              <BarChart data={d.regions.slice(0, 12)} barGap={3}>
                <CartesianGrid
                  stroke="#263332"
                  strokeDasharray="3 4"
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#81928f', fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="temp"
                  tick={{ fill: '#81928f', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: '°C',
                    angle: -90,
                    position: 'insideLeft',
                    fill: '#81928f',
                  }}
                />
                <YAxis
                  yAxisId="humidity"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fill: '#81928f', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: '%',
                    angle: 90,
                    position: 'insideRight',
                    fill: '#81928f',
                  }}
                />
                <Tooltip
                  contentStyle={{
                    background: '#0c1413',
                    border: '1px solid #2c4140',
                    borderRadius: 8,
                  }}
                />
                <Bar
                  yAxisId="temp"
                  dataKey="temperature"
                  name="Mean temperature °C"
                  fill="#27c9b9"
                  radius={[3, 3, 0, 0]}
                />
                <Bar
                  yAxisId="humidity"
                  dataKey="humidity"
                  name="Humidity %"
                  fill="#2c9edb"
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty message="Regional comparisons are computed from country fields." />
          )}
          <div className="model-foot">
            Groups are observation-weighted summaries, not population- or area-weighted climate comparisons.
          </div>
        </Panel>
      {extras.continent_regions?.length ? (
        <Panel title="Continent-level comparison">
          {extras.continent_regions?.length ? (
            <>
              <div className="subhead">
                MEAN TEMPERATURE BY CONTINENT
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={extras.continent_regions}
                  margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                >
                  <CartesianGrid
                    stroke="#263332"
                    strokeDasharray="3 4"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: '#81928f', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    interval={0}
                    angle={-15}
                    textAnchor="end"
                    height={48}
                  />
                  <YAxis
                    tick={{ fill: '#81928f', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    label={{
                      value: '°C',
                      angle: -90,
                      position: 'insideLeft',
                      fill: '#81928f',
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#0c1413',
                      border: '1px solid #2c4140',
                      borderRadius: 8,
                    }}
                    formatter={(value) => [
                      value == null
                        ? 'Unavailable'
                        : `${Number(value).toFixed(2)} °C`,
                      'Mean temperature',
                    ]}
                  />
                  <Bar
                    dataKey="temperature"
                    name="Mean temperature"
                    fill="#27c9b9"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>

              <div className="subhead">
                CONTINENTAL WEATHER SUMMARY
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>CONTINENT</th>
                      <th>OBS.</th>
                      <th>LOCATIONS</th>
                      <th>TEMP °C</th>
                      <th>HUMIDITY</th>
                      <th>WIND km/h</th>
                      <th>MEAN DAILY PRECIP. mm/day</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extras.continent_regions.map((item) => (
                      <tr key={item.name}>
                        <td>{item.name}</td>
                        <td>{item.rows.toLocaleString()}</td>
                        <td>{item.locations.toLocaleString()}</td>
                        <td>{fmt(item.temperature, 1)}</td>
                        <td>{fmt(item.humidity, 1)}%</td>
                        <td>{fmt(item.wind, 1)}</td>
                        <td>{fmt(item.precipitation, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="model-foot">
                {extras.continent_coverage
                  ? `${extras.continent_coverage.classification_percentage.toFixed(1)}% of observations classified · ${extras.continent_coverage.classified_rows.toLocaleString()} classified · ${extras.continent_coverage.unclassified_rows.toLocaleString()} unclassified.`
                  : 'Continent classification coverage unavailable.'}
                {' '}
                {extras.continent_regions[0]?.aggregation_method ||
                  'Means are observation-weighted across available observations.'}
              </div>
            </>
          ) : (
            <Empty message="Continent-level comparisons require country fields and valid continent mappings." />
          )}
        </Panel>
      ) : null}
        <Panel title="Seasonal observation profile">
          {extras.seasonal?.length ? (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>HEMISPHERE / SEASON</th>
                      <th>OBS.</th>
                      <th>TEMP °C</th>
                      <th>HUMIDITY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extras.seasonal.map((item) => (
                      <tr key={`${item.hemisphere}-${item.season}`}>
                        <td>{item.hemisphere} · {item.season}</td>
                        <td>{item.observations.toLocaleString()}</td>
                        <td>{fmt(item.temperature, 1)}</td>
                        <td>{fmt(item.humidity, 1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="model-foot">
                Meteorological seasons are assigned by hemisphere. These are summaries of available observations, not climate normals.
              </div>
            </>
          ) : (
            <Empty message="Seasonal summaries require valid timestamps and temperature observations." />
          )}
        </Panel>                
                

              
      <Panel
        title="Air quality · Weather relationships"
        className="air-panel"
      >
        <div className="air-overview">
          <div className="air-icon">
            <Wind size={23} />
          </div>
              
          <div className="air-summary">
            {d.air_quality.available
              ? 'OPENAQ OBSERVATIONS · SIX POLLUTANTS'
              : 'AIR QUALITY DATA UNAVAILABLE'}
          </div>
            
          <p>{d.air_quality.note}</p>
            
          {d.air_quality.available && (
            <div className="quality-coverage">
              <div>
                <strong>
                  {d.air_quality.matched_city_days?.toLocaleString() ?? '—'}
                </strong>
                <span>Matched city-days</span>
              </div>
          
              <div>
                <strong>
                  {d.air_quality.matched_cities ?? '—'}
                </strong>
                <span>City-country pairs</span>
              </div>
          
              <div>
                <strong>
                  {d.air_quality.match_rate_pct?.toFixed(1) ?? '—'}%
                </strong>
                <span>Match rate</span>
              </div>
            </div>
          )}
        </div>
        
        <div className="air-correlations">
          <div className="subhead">
            STRONGEST WITHIN-CITY CORRELATIONS
          </div>
        
          {d.air_quality.correlations.length ? (
            d.air_quality.correlations.map((correlation, index) => (
              <div className="quality-row" key={index}>
                <span>
                  {correlation.pollutant} ({correlation.unit}) ↔{' '}
                  {correlation.feature.replaceAll('_', ' ')}
                </span>
            
                <div className="quality-track">
                  <i
                    style={{
                      width: `${Math.abs(correlation.correlation) * 100}%`,
                      background:
                        correlation.correlation < 0
                          ? '#2c9edb'
                          : '#f6bc42',
                    }}
                  />
                </div>
                  
                <b>{fmt(correlation.correlation, 2)}</b>
                  
                <small>
                  {correlation.sample_size?.toLocaleString()} city-days ·{' '}
                  {correlation.cities} cities
                </small>
              </div>
            ))
          ) : (
            <Empty message="No sufficiently covered pollutant-weather relationships available." />
          )}
        </div>
        
        <div className="model-foot">
          Correlations are observational, not causal. Gas pollutant units
          are analyzed separately. Full results are available in the
          analysis output CSV.
        </div>
      </Panel>
      </div>
        













     <section id="climate" className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">
              HISTORICAL ANALYSIS
              <span className="sep">/</span>
              CLIMATE PATTERNS
            </div>
            <h2>Historical climate patterns</h2>
          </div>
          <span className="section-note">
            Matched locations · Descriptive analysis
          </span>
        </div>

        {!d.climate.available ? (
          <Panel title="Climate analysis">
            <Empty message={d.climate.note || "Climate analysis is unavailable."} />
          </Panel>
        ) : (
          <>
            <Panel title="Matched-location year-over-year comparison">
              {d.climate.year_over_year.length ? (
                <>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>YEAR</th>
                          <th>MATCHED LOCATIONS</th>
                          <th>LOCATION-MONTHS</th>
                          <th>TEMP CHANGE °C</th>
                          <th>MEDIAN CHANGE °C</th>
                          <th>PRECIP. CHANGE mm/day</th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.climate.year_over_year.map((item) => (
                          <tr key={item.year}>
                            <td>{item.year}</td>
                            <td>{item.matched_locations.toLocaleString()}</td>
                            <td>{item.matched_location_months.toLocaleString()}</td>
                            <td>{fmt(item.temperature_change_c, 2)}</td>
                            <td>{fmt(item.median_temperature_change_c, 2)}</td>
                            <td>{fmt(item.precipitation_change_mm_per_day, 3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="model-foot">
                    Changes are calculated using matched locations, not changing
                    samples of unrelated cities.
                  </div>
                </>
              ) : (
                <Empty message="No matched-location year-over-year results available." />
              )}
            </Panel>

            <div className="forecast-grid">
              <Panel title="Monthly temperature anomalies">
                {d.climate.temperature_anomalies.length ? (
                  <>
                    <div className="chart-legend">
                      <span>
                        <i style={{ background: "#29b8ec" }} />
                        Mean anomaly
                      </span>
                      <span>
                        <i style={{ background: "#f6bc42" }} />
                        Median anomaly
                      </span>
                    </div>

                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart data={d.climate.temperature_anomalies}>
                        <CartesianGrid
                          stroke="#263332"
                          strokeDasharray="3 4"
                        />


                        <ReferenceLine
                          y={0}
                          stroke="#81928f"
                          strokeDasharray="5 5"
                          strokeOpacity={0.8}
                        />

                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#7d918e", fontSize: 9 }}
                          interval="preserveStartEnd"
                          angle={-25}
                          textAnchor="end"
                          height={48}
                        />
                        <YAxis
                          tick={{ fill: "#7d918e", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                          label={{
                            value: "°C",
                            angle: -90,
                            position: "insideLeft",
                            fill: "#81928f",
                          }}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#0c1413",
                            border: "1px solid #2c4140",
                            borderRadius: 8,
                          }}
                          formatter={(value, name) => [
                            value == null
                              ? "Unavailable"
                              : `${Number(value).toFixed(2)} °C`,
                            name,
                          ]}
                          labelFormatter={(label, payload) => {
                            const count = payload?.[0]?.payload?.locations;
                            return `${label} · ${count ?? "—"} locations`;
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="mean_anomaly_c"
                          name="Mean anomaly"
                          stroke="#29b8ec"
                          dot={false}
                          connectNulls={false}
                        />
                        <Line
                          type="monotone"
                          dataKey="median_anomaly_c"
                          name="Median anomaly"
                          stroke="#f6bc42"
                          dot={false}
                          connectNulls={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                    <div className="model-foot">
                      Anomalies are location-relative deviations from the
                      corresponding calendar month's average.
                      October 2026 is partial: observations end on October 13.
                      Other months reflect the available dataset coverage
                    </div>
                  </>
                ) : (
                  <Empty message="Monthly temperature anomaly data unavailable." />
                )}
              </Panel>

              <Panel title="Precipitation variability">
                {d.climate.precipitation_variability.length ? (
                  <>
                    <div className="chart-legend">
                      <span>
                        <i style={{ background: "#21d4c2" }} />
                        Mean daily precipitation
                      </span>
                      <span>
                        <i style={{ background: "#f6bc42" }} />
                        Median daily precipitation
                      </span>
                    </div>

                    <ResponsiveContainer width="100%" height={260}>
                      <ComposedChart data={d.climate.precipitation_variability}>
                        <CartesianGrid
                          stroke="#263332"
                          strokeDasharray="3 4"
                        />
                        <XAxis
                          dataKey="label"
                          tick={{ fill: "#7d918e", fontSize: 9 }}
                          interval="preserveStartEnd"
                          angle={-25}
                          textAnchor="end"
                          height={48}
                        />
                        <YAxis
                          yAxisId="precip"
                          tick={{ fill: "#7d918e", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          yAxisId="spread"
                          orientation="right"
                          tick={{ fill: "#7d918e", fontSize: 10 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#0c1413",
                            border: "1px solid #2c4140",
                            borderRadius: 8,
                          }}
                          formatter={(value, name) => [
                            value == null
                              ? "Unavailable"
                              : `${Number(value).toFixed(2)} mm/day`,
                            name,
                          ]}
                          labelFormatter={(label, payload) => {
                            const count = payload?.[0]?.payload?.locations;
                            return `${label} · ${count ?? "—"} locations`;
                          }}
                        />
                        <Line
                          yAxisId="precip"
                          type="monotone"
                          dataKey="mean_daily_precipitation_mm"
                          name="Mean daily precipitation"
                          stroke="#21d4c2"
                          dot={false}
                        />
                        <Line
                          yAxisId="precip"
                          type="monotone"
                          dataKey="median_daily_precipitation_mm"
                          name="Median daily precipitation"
                          stroke="#f6bc42"
                          dot={false}
                        />
                        <Bar
                          yAxisId="spread"
                          dataKey="between_location_std_mm"
                          name="Between-location standard deviation"
                          fill="#9a8cf5"
                          opacity={0.35}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                    <div className="model-foot">
                      Precipitation is mean daily precipitation per
                      location-month, not monthly accumulated rainfall.
                      October 2026 is partial: observations end on October 13.
                      Other months reflect the available dataset coverage.
                    </div>
                  </>
                ) : (
                  <Empty message="Monthly precipitation variability data unavailable." />
                )}
              </Panel>
            </div>

            <Panel title="Coverage and methodology">
              <div className="mini-stat-grid">
                <div>
                  <span>Eligible locations</span>
                  <b>{d.climate.coverage.eligible_locations.toLocaleString()}</b>
                </div>
                <div>
                  <span>Matched location-months</span>
                  <b>{d.climate.coverage.matched_location_months.toLocaleString()}</b>
                </div>
                <div>
                  <span>Years covered</span>
                  <b>{d.climate.coverage.years.join(" · ")}</b>
                </div>
              </div>
              <div className="model-foot">
                {d.climate.method}
              </div>
              <div className="notice">
                <CircleHelp size={14} />
                {d.climate.note}
              </div>
            </Panel>
          </>
        )}
      </section>


      
      {/* FORECAST LAB */}
      <section id="forecast" className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">
              MODEL EVALUATION
              <span className="sep">/</span>
              TIME SERIES
            </div>
            <h2>Forecast lab</h2>
          </div>
          <span className="section-note">
            Chronological holdout · No random shuffling
          </span>
        </div>

        <div className="forecast-grid">
          <Panel title="Actual vs predicted">
            <div className="chart-legend">
              <span><i style={{ background: '#f6bc42' }} />Actual</span>
              <span><i style={{ background: '#29b8ec' }} />Ensemble</span>
              <span><i style={{ background: '#9a8cf5' }} />Baseline</span>
            </div>

            {d.forecasts.available && d.forecasts.series.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={d.forecasts.series}>
                  <CartesianGrid stroke="#263332" strokeDasharray="3 4" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#7d918e', fontSize: 10 }}
                  />
                  <YAxis tick={{ fill: '#7d918e', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{
                      background: '#0c1413',
                      border: '1px solid #2c4140',
                    }}
                  />
                  <Line
                    dataKey="actual"
                    name="Actual"
                    stroke="#f6bc42"
                    dot={false}
                    connectNulls
                  />
                  <Line
                    dataKey="ensemble"
                    name="Ensemble"
                    stroke="#29b8ec"
                    dot={false}
                    connectNulls
                  />
                  <Line
                    dataKey="baseline"
                    name="Baseline"
                    stroke="#9a8cf5"
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Empty message={d.forecasts.reason} />
            )}
          </Panel>

          <Panel title="Model scorecard">
            {d.forecasts.models.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>MODEL</th>
                      <th>MAE ↓</th>
                      <th>RMSE ↓</th>
                      <th>R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.forecasts.models.map((model) => (
                      <tr key={model.name}>
                        <td>{model.name}</td>
                        <td>{fmt(model.mae, 3)}</td>
                        <td>{fmt(model.rmse, 3)}</td>
                        <td>{fmt(model.r2, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty message="Scores require a valid time series and holdout set." />
            )}

            <div className="model-foot">
              <Gauge size={15} />
              <span>Lower MAE / RMSE is better. R² may be negative.</span>
            </div>
          </Panel>
        </div>
      </section>

      {/* ANOMALY WATCHLIST + FEATURE IMPORTANCE */}
      <div className="lower-grid" id="anomalies">
        <Panel title="Anomaly watchlist">
          <div className="mini-stat-grid">
            {Object.entries(extras.anomaly_breakdown ?? {})
              .filter(([key]) => key !== 'total_unique')
              .map(([key, value]) => (
                <div key={key}>
                  <span>{key.replace(/_/g, ' ')}</span>
                  <b>{value.toLocaleString()}</b>
                </div>
              ))}
          </div>

          <div className="model-foot">
            {(extras.anomaly_breakdown?.total_unique ??
              d.kpis.anomaly_count).toLocaleString()} unique observations flagged.
            Detector counts overlap; these are statistical flags, not confirmed
            weather events or data errors.
          </div>

          {anomalyReasons.length > 0 && (
            <>
              <div className="subhead">DETECTOR / REASON COUNTS</div>
              {anomalyReasons.map(([reason, count]) => (
                <div className="quality-row" key={reason}>
                  <span>{reason}</span>
                  <div className="quality-track">
                    <i
                      style={{
                        width: `${
                          (count / anomalyReasons[0][1]) * 100
                        }%`,
                      }}
                    />
                  </div>
                  <b>{count.toLocaleString()}</b>
                </div>
              ))}
            </>
          )}

          <div className="subhead">FLAGGED OBSERVATIONS</div>
          <div className="table-wrap">
            {d.anomalies.length ? (
              <table>
                <thead>
                  <tr>
                    <th>LOCATION</th>
                    <th>DATE</th>
                    <th>TEMP</th>
                    <th>TYPE</th>
                    <th>REASON</th>
                  </tr>
                </thead>
                <tbody>
                  {d.anomalies.slice(0, 8).map((anomaly, index) => (
                    <tr key={index}>
                      <td>{anomaly.city}, {anomaly.country}</td>
                      <td>{anomaly.date || '—'}</td>
                      <td>{fmt(anomaly.temperature)}°</td>
                      <td>{anomaly.category ?? 'Statistical'}</td>
                      <td>
                        <span className="flag">{anomaly.reason}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <Empty message="Outliers will be ranked after anomaly detection." />
            )}
          </div>
        </Panel>

        <Panel title="Feature importance">
          <div className="importance-list">
            {d.forecasts.feature_importance.length ? (
              d.forecasts.feature_importance
                .slice(0, 8)
                .map((feature, index) => (
                  <div
                    className="importance-row"
                    key={feature.feature}
                  >
                    <span>{feature.feature}</span>
                    <div className="quality-track">
                      <i
                        style={{
                          width: `${Math.max(
                            0,
                            Math.min(100, feature.importance * 100),
                          )}%`,
                          background: palette[index % palette.length],
                        }}
                      />
                    </div>
                    <b>{fmt(feature.importance, 3)}</b>
                  </div>
                ))
            ) : (
              <Empty message="Feature importance requires a trained model." />
            )}
          </div>

          <div className="model-foot">
            <CircleHelp size={14} />
            <span>Predictive contribution is not causation.</span>
          </div>
        </Panel>
      </div>
    </main>
  );

}
