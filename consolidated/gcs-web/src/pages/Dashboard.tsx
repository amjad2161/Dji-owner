/**
 * SkyCore - Dashboard Page
 * Live tactical overview: own drone (AUKF), classified threats, no-fly zone, planned route.
 */

import React, { useEffect, useRef, useState } from 'react';
import { TelemetryService } from '../services/TelemetryService';
import { AdsBService } from '../services/AdsBService';
import { apiGet } from '../services/auth';
import { HOME_LAT, HOME_LON, M_PER_DEG_LAT, M_PER_DEG_LON } from '../services/geo';
import { DroneState, Threat } from '../App';

const W = 560, H = 440, CX = W / 2, CY = H / 2, SCALE = 1.3; // metres per pixel
const enuToPx = (e: number, n: number) => ({ x: CX + e / SCALE, y: CY - n / SCALE });
const SEV_COLOR: Record<string, string> = { critical: '#FF2A2A', high: '#FF9F1C', medium: '#FFD166', low: '#00E5A0' };

interface Evt { t: string; text: string; color: string; }

const Dashboard: React.FC = () => {
  const [drone, setDrone] = useState<DroneState>(TelemetryService.getInstance().getCurrentState());
  const [threats, setThreats] = useState<Threat[]>([]);
  const [stats, setStats] = useState({ total: 0, critical: 0, high: 0, medium: 0, low: 0 });
  const [zone, setZone] = useState<{ e: number; n: number; radius: number } | null>(null);
  const [route, setRoute] = useState<{ e: number; n: number }[]>([]);
  const [events, setEvents] = useState<Evt[]>([]);
  const [weather, setWeather] = useState<{ ok?: boolean; temp_c?: number; wind_kph?: number; gust_kph?: number } | null>(null);
  const prev = useRef({ mode: '', crit: -1, reason: '' });

  useEffect(() => {
    const tel = TelemetryService.getInstance();
    const ads = AdsBService.getInstance();
    const unsub = tel.subscribe(setDrone);
    apiGet<{ enabled: boolean; zones?: { center: { e: number; n: number }; radius: number }[] }>('/api/geofence')
      .then((d) => { if (d.enabled && d.zones?.[0]) { const z = d.zones[0]; setZone({ e: z.center.e, n: z.center.n, radius: z.radius }); } })
      .catch(() => {});
    const fetchWeather = () => apiGet<{ ok?: boolean; temp_c?: number; wind_kph?: number; gust_kph?: number }>('/api/weather').then(setWeather).catch(() => {});
    fetchWeather();
    const wid = setInterval(fetchWeather, 60000);

    const push = (text: string, color: string) =>
      setEvents((prevE) => [{ t: new Date().toLocaleTimeString(), text, color }, ...prevE].slice(0, 8));

    const id = setInterval(() => {
      setThreats(ads.getAllThreats());
      const s = ads.getThreatStats();
      setStats(s);
      setRoute(tel.getRoute());
      const st = tel.getCurrentState();
      const reason = tel.getNavInfo().geofenceReason;
      if (st.mode !== prev.current.mode) { push(`Flight mode → ${st.mode}`, '#00D4FF'); prev.current.mode = st.mode; }
      const hadCrit = prev.current.crit > 0, nowCrit = s.critical > 0;
      if (nowCrit && !hadCrit) push(`${s.critical} critical threat(s) detected`, SEV_COLOR.critical);
      else if (!nowCrit && hadCrit) push('threat level cleared', SEV_COLOR.low);
      prev.current.crit = s.critical;
      // track the true current reason so a recurring identical reason re-notifies after it clears
      if (reason !== prev.current.reason) { if (reason) push(reason, '#FF6B6B'); prev.current.reason = reason; }
    }, 1000);

    return () => { unsub(); clearInterval(id); clearInterval(wid); };
  }, []);

  const dEnu = { e: (drone.position.lon - HOME_LON) * M_PER_DEG_LON, n: (drone.position.lat - HOME_LAT) * M_PER_DEG_LAT };
  const dPx = enuToPx(dEnu.e, dEnu.n);

  // threat marker positions from home-relative distance + bearing
  const threatMarks = threats.map((t) => {
    const b = (t.bearing * Math.PI) / 180;
    const e = t.distance * Math.sin(b), n = t.distance * Math.cos(b);
    return { t, e, n };
  }).filter((m) => Math.hypot(m.e, m.n) < 360);

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <div className={`connection-status ${drone.connected ? 'connected' : 'disconnected'}`}>
          {drone.connected ? '🟢 מחובר' : '🔴 מנותק'}
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="map-container">
          <div className="map-header">
            <h2>מפה טקטית</h2>
            <span className="coordinates">{drone.position.lat.toFixed(6)}, {drone.position.lon.toFixed(6)}</span>
          </div>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ background: '#0a0f0d', border: '1px solid #1e2a24', borderRadius: 8, display: 'block', maxHeight: 440 }}>
            {[100, 200, 300].map((r) => (
              <circle key={r} cx={CX} cy={CY} r={r / SCALE} fill="none" stroke="#16221c" />
            ))}
            <line x1={CX} y1={0} x2={CX} y2={H} stroke="#121a16" />
            <line x1={0} y1={CY} x2={W} y2={CY} stroke="#121a16" />
            {/* no-fly zone */}
            {zone && (() => { const c = enuToPx(zone.e, zone.n); return (
              <g><circle cx={c.x} cy={c.y} r={zone.radius / SCALE} fill="rgba(255,42,42,0.13)" stroke="#FF2A2A" strokeWidth={1.5} />
                <text x={c.x} y={c.y + 3} fill="#FF6B6B" fontSize={10} textAnchor="middle">NO-FLY</text></g>
            ); })()}
            {/* planned route */}
            {route.length > 1 && (
              <polyline points={route.map((p) => { const q = enuToPx(p.e, p.n); return `${q.x.toFixed(1)},${q.y.toFixed(1)}`; }).join(' ')}
                fill="none" stroke="#FFD166" strokeWidth={1.5} strokeDasharray="5 4" />
            )}
            {/* home */}
            <rect x={CX - 5} y={CY - 5} width={10} height={10} fill="#00E5A0" />
            <text x={CX + 8} y={CY + 4} fill="#00E5A0" fontSize={10}>HOME</text>
            {/* threats */}
            {threatMarks.map((m) => { const q = enuToPx(m.e, m.n); const col = SEV_COLOR[m.t.severity] || '#c7d3cd'; return (
              <g key={m.t.id}>
                <circle cx={q.x} cy={q.y} r={5} fill="none" stroke={col} strokeWidth={2} />
                <line x1={q.x - 7} y1={q.y} x2={q.x + 7} y2={q.y} stroke={col} />
                <line x1={q.x} y1={q.y - 7} x2={q.x} y2={q.y + 7} stroke={col} />
                <text x={q.x + 9} y={q.y + 3} fill={col} fontSize={9}>{(m.t as Threat & { behavior?: string }).behavior || m.t.type}</text>
              </g>
            ); })}
            {/* own drone (AUKF estimate) */}
            <g transform={`translate(${dPx.x},${dPx.y}) rotate(${drone.heading})`}>
              <polygon points="0,-9 6,7 0,3 -6,7" fill="#00D4FF" />
            </g>
            <text x={dPx.x + 9} y={dPx.y + 3} fill="#00D4FF" fontSize={10}>UAV</text>
          </svg>
          <div className="map-controls">
            <button onClick={() => TelemetryService.getInstance().arm()}>Arm</button>
            <button onClick={() => TelemetryService.getInstance().takeoff(40)}>Takeoff</button>
            <button onClick={() => TelemetryService.getInstance().land()}>Land</button>
            <button onClick={() => TelemetryService.getInstance().rtl()}>RTH</button>
            <button onClick={() => TelemetryService.getInstance().disarm()}>Disarm</button>
          </div>
        </div>

        <div className="telemetry-grid">
          <div className="telemetry-card battery">
            <div className="card-icon">🔋</div>
            <div className="card-content">
              <span className="card-label">מצבר</span>
              <span className="card-value">{drone.battery.toFixed(0)}%</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${drone.battery}%`, backgroundColor: drone.battery < 30 ? '#ef4444' : drone.battery < 50 ? '#f59e0b' : '#22c55e' }} />
              </div>
            </div>
          </div>
          <div className="telemetry-card altitude">
            <div className="card-icon">📍</div>
            <div className="card-content"><span className="card-label">גובה</span><span className="card-value">{drone.altitude.toFixed(1)}m</span></div>
          </div>
          <div className="telemetry-card speed">
            <div className="card-icon">⚡</div>
            <div className="card-content"><span className="card-label">מהירות</span><span className="card-value">{drone.speed.toFixed(1)}m/s</span></div>
          </div>
          <div className="telemetry-card heading">
            <div className="card-icon">🧭</div>
            <div className="card-content"><span className="card-label">כיוון</span><span className="card-value">{drone.heading.toFixed(0)}°</span></div>
          </div>
          <div className="telemetry-card mode">
            <div className="card-icon">🎮</div>
            <div className="card-content"><span className="card-label">מצב</span><span className="card-value">{drone.mode}</span></div>
          </div>
          <div className="telemetry-card threats">
            <div className="card-icon">⚠️</div>
            <div className="card-content">
              <span className="card-label">איומים</span>
              <span className="card-value">{stats.total}</span>
              {stats.critical > 0 && <span className="threat-critical">{stats.critical} קריטיים</span>}
            </div>
          </div>
          <div className="telemetry-card weather">
            <div className="card-icon">🌦️</div>
            <div className="card-content">
              <span className="card-label">מזג אוויר (חי)</span>
              <span className="card-value">{weather?.wind_kph != null ? `${weather.wind_kph} kph` : '…'}</span>
              {weather?.temp_c != null && (
                <span style={{ fontSize: 12 }}>
                  {weather.temp_c}°C · {weather.ok ? <span style={{ color: '#00E5A0' }}>בטוח לטוס</span> : <span style={{ color: '#FF9F1C' }}>זהירות</span>}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="activity-panel">
          <h3>פעילות אחרונה</h3>
          <div className="activity-list">
            {events.length === 0 && (
              <div className="activity-item"><span className="activity-text" style={{ color: '#7d8a84' }}>ממתין לאירועים…</span></div>
            )}
            {events.map((e, i) => (
              <div className="activity-item" key={i}>
                <span className="activity-time">{e.t}</span>
                <span className="activity-text" style={{ color: e.color }}>{e.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
