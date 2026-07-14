import React, { useEffect, useRef, useState } from 'react';
import { TelemetryService } from '../services/TelemetryService';
import { apiGet } from '../services/auth';
import { DroneState } from '../App';

const HOME_LAT = 32.0853, HOME_LON = 34.7818;
const M_PER_DEG_LAT = 111320;
const M_PER_DEG_LON = 111320 * Math.cos((HOME_LAT * Math.PI) / 180);
const W = 560, H = 440, CX = W / 2, CY = H / 2, SCALE = 1.3; // metres per pixel

const enuToPx = (e: number, n: number) => ({ x: CX + e / SCALE, y: CY - n / SCALE });
const llToEnu = (lat: number, lon: number) => ({
  e: (lon - HOME_LON) * M_PER_DEG_LON,
  n: (lat - HOME_LAT) * M_PER_DEG_LAT,
});

const btn: React.CSSProperties = {
  background: '#132019', color: '#00E5A0', border: '1px solid #1e2a24',
  borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontFamily: 'monospace', fontSize: 13,
};

const Missions: React.FC = () => {
  const [state, setState] = useState<DroneState>(TelemetryService.getInstance().getCurrentState());
  const [target, setTarget] = useState<{ lat: number; lon: number; alt: number } | null>(null);
  const [alt, setAlt] = useState(40);
  const [zone, setZone] = useState<{ e: number; n: number; radius: number } | null>(null);
  const [gfReason, setGfReason] = useState('');
  const [route, setRoute] = useState<{ e: number; n: number }[]>([]);
  const [flights, setFlights] = useState<Array<{ start_time: string; end_time: string; max_alt: number; distance_km: number; battery_used: number }>>([]);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svc = TelemetryService.getInstance();
    const id = setInterval(() => {
      setState(svc.getCurrentState());
      setGfReason(svc.getNavInfo().geofenceReason);
      setRoute(svc.getRoute());
    }, 300);
    apiGet<{ enabled: boolean; zones?: { center: { e: number; n: number }; radius: number }[] }>('/api/geofence')
      .then((d) => { if (d.enabled && d.zones?.[0]) { const z = d.zones[0]; setZone({ e: z.center.e, n: z.center.n, radius: z.radius }); } })
      .catch(() => {});
    const fetchFlights = () => apiGet<{ flights?: typeof flights }>('/api/flights').then((d) => setFlights(d.flights || [])).catch(() => {});
    fetchFlights();
    const fid = setInterval(fetchFlights, 8000);
    return () => { clearInterval(id); clearInterval(fid); };
  }, []);

  const svc = TelemetryService.getInstance();
  const airborne = state.altitude > 0.5 || ['TAKEOFF', 'FLYING', 'RTL'].includes(state.mode);

  const onMapClick = (ev: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const px = (ev.clientX - rect.left) * (W / rect.width);
    const py = (ev.clientY - rect.top) * (H / rect.height);
    const e = (px - CX) * SCALE;
    const n = (CY - py) * SCALE;
    const lat = HOME_LAT + n / M_PER_DEG_LAT;
    const lon = HOME_LON + e / M_PER_DEG_LON;
    setTarget({ lat, lon, alt });
    svc.goto(lat, lon, alt);
  };

  const drone = llToEnu(state.position.lat, state.position.lon);
  const dPx = enuToPx(drone.e, drone.n);
  const tPx = target ? enuToPx(llToEnu(target.lat, target.lon).e, llToEnu(target.lat, target.lon).n) : null;

  return (
    <div style={{ padding: 24, color: '#c7d3cd', fontFamily: 'monospace' }}>
      <h1 style={{ color: '#00E5A0', margin: 0 }}>Missions</h1>
      <p style={{ color: '#7d8a84', marginTop: 4 }}>
        Click the map to fly there (goto). mode: <b style={{ color: '#00D4FF' }}>{state.mode}</b>
        {'  '}alt {state.altitude.toFixed(1)} m {'  '}spd {state.speed.toFixed(1)} m/s
        {!airborne && <span style={{ color: '#FF9F1C' }}>  — takeoff first, then click to fly</span>}
      </p>
      {gfReason && <div style={{ color: '#FF6B6B', fontSize: 13, marginBottom: 8 }}>⚠ {gfReason}</div>}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <svg
          ref={svgRef} width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          onClick={onMapClick}
          style={{ background: '#0a0f0d', border: '1px solid #1e2a24', borderRadius: 8, cursor: 'crosshair', maxWidth: '100%' }}
        >
          {[100, 200, 300].map((r) => (
            <circle key={r} cx={CX} cy={CY} r={r / SCALE} fill="none" stroke="#16221c" strokeWidth={1} />
          ))}
          <line x1={CX} y1={0} x2={CX} y2={H} stroke="#121a16" />
          <line x1={0} y1={CY} x2={W} y2={CY} stroke="#121a16" />
          {[100, 200, 300].map((r) => (
            <text key={r} x={CX + 3} y={CY - r / SCALE + 12} fill="#3a4a42" fontSize={10}>{r}m</text>
          ))}
          {/* no-fly zone (real geofence — circular) */}
          {zone && (() => {
            const c = enuToPx(zone.e, zone.n);
            return (
              <g>
                <circle cx={c.x} cy={c.y} r={zone.radius / SCALE} fill="rgba(255,42,42,0.13)" stroke="#FF2A2A" strokeWidth={1.5} />
                <text x={c.x} y={c.y + 3} fill="#FF6B6B" fontSize={10} textAnchor="middle">NO-FLY</text>
              </g>
            );
          })()}
          {/* planned RRT* route around the no-fly zone */}
          {route.length > 1 && (
            <polyline
              points={route.map((p) => { const q = enuToPx(p.e, p.n); return `${q.x.toFixed(1)},${q.y.toFixed(1)}`; }).join(' ')}
              fill="none" stroke="#FFD166" strokeWidth={1.5} strokeDasharray="5 4"
            />
          )}
          {/* home */}
          <rect x={CX - 5} y={CY - 5} width={10} height={10} fill="#00E5A0" />
          <text x={CX + 8} y={CY + 4} fill="#00E5A0" fontSize={11}>HOME</text>
          {/* target */}
          {tPx && (
            <g>
              <circle cx={tPx.x} cy={tPx.y} r={8} fill="none" stroke="#FFD166" strokeWidth={2} />
              <line x1={tPx.x - 11} y1={tPx.y} x2={tPx.x + 11} y2={tPx.y} stroke="#FFD166" />
              <line x1={tPx.x} y1={tPx.y - 11} x2={tPx.x} y2={tPx.y + 11} stroke="#FFD166" />
            </g>
          )}
          {/* drone */}
          <g transform={`translate(${dPx.x},${dPx.y}) rotate(${state.heading})`}>
            <polygon points="0,-9 6,7 0,3 -6,7" fill="#00D4FF" />
          </g>
          <text x={dPx.x + 9} y={dPx.y + 3} fill="#00D4FF" fontSize={11}>UAV</text>
        </svg>

        <div style={{ minWidth: 220, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ background: '#111', border: '1px solid #1e2a24', borderRadius: 8, padding: 14 }}>
            <div style={{ color: '#7d8a84', fontSize: 12, marginBottom: 8 }}>WAYPOINT ALTITUDE</div>
            <input type="range" min={10} max={120} value={alt} onChange={(e) => setAlt(Number(e.target.value))} style={{ width: '100%' }} />
            <div style={{ color: '#00E5A0', textAlign: 'center' }}>{alt} m</div>
          </div>
          <button style={btn} onClick={() => svc.arm()}>Arm</button>
          <button style={btn} onClick={() => svc.takeoff(alt)}>Takeoff to {alt} m</button>
          <button style={btn} onClick={() => svc.land()}>Land</button>
          <button style={btn} onClick={() => svc.rtl()}>Return to Home</button>
          {target && (
            <div style={{ background: '#111', border: '1px solid #1e2a24', borderRadius: 8, padding: 14, fontSize: 12 }}>
              <div style={{ color: '#7d8a84' }}>target</div>
              <div style={{ color: '#FFD166' }}>{target.lat.toFixed(6)}, {target.lon.toFixed(6)} @ {target.alt} m</div>
            </div>
          )}
          <div style={{ background: '#111', border: '1px solid #1e2a24', borderRadius: 8, padding: 14, fontSize: 12 }}>
            <div style={{ color: '#7d8a84', letterSpacing: 1, marginBottom: 6 }}>RECENT FLIGHTS (SQLite)</div>
            {flights.length === 0 && <div style={{ color: '#7d8a84' }}>no flights logged yet</div>}
            {flights.slice(0, 5).map((f, i) => {
              const dur = Math.max(0, Math.round((new Date(f.end_time).getTime() - new Date(f.start_time).getTime()) / 1000));
              return (
                <div key={i} style={{ borderBottom: '1px solid #161f1b', padding: '4px 0', color: '#c7d3cd' }}>
                  <span style={{ color: '#00E5A0' }}>{dur}s</span> · {f.max_alt} m · {f.distance_km} km · −{f.battery_used}%
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Missions;
