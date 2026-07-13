import React, { useEffect, useRef, useState } from 'react';
import { TelemetryService } from '../services/TelemetryService';
import { DroneState } from '../App';

const MAX = 150;
const panel: React.CSSProperties = {
  background: '#111', border: '1px solid #1e2a24', borderRadius: 8, padding: 14,
};

const Spark: React.FC<{ data: number[]; color: string; unit: string; label: string }> = ({ data, color, unit, label }) => {
  const w = 520, h = 110, pad = 8;
  const min = Math.min(...data, 0);
  const max = Math.max(...data, 1);
  const rng = (max - min) || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (MAX - 1)) * (w - 2 * pad);
    const y = h - pad - ((v - min) / rng) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const cur = data.length ? data[data.length - 1] : 0;
  return (
    <div style={panel}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ color: '#7d8a84', fontSize: 12, letterSpacing: 1 }}>{label}</span>
        <span style={{ color, fontWeight: 700, fontSize: 20 }}>{cur.toFixed(1)} <span style={{ fontSize: 12 }}>{unit}</span></span>
      </div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ marginTop: 6, display: 'block' }}>
        <polyline points={pts} fill="none" stroke={color} strokeWidth={2} />
      </svg>
    </div>
  );
};

const Telemetry: React.FC = () => {
  const [state, setState] = useState<DroneState>(TelemetryService.getInstance().getCurrentState());
  const [nav, setNav] = useState(TelemetryService.getInstance().getNavInfo());
  const hist = useRef({ alt: [] as number[], spd: [] as number[], batt: [] as number[] });
  const [, force] = useState(0);

  useEffect(() => {
    const svc = TelemetryService.getInstance();
    const id = setInterval(() => {
      const s = svc.getCurrentState();
      setState(s);
      setNav(svc.getNavInfo());
      const h = hist.current;
      h.alt.push(s.altitude); h.spd.push(s.speed); h.batt.push(s.battery);
      (['alt', 'spd', 'batt'] as const).forEach((k) => { if (h[k].length > MAX) h[k].shift(); });
      force((n) => n + 1);
    }, 300);
    return () => clearInterval(id);
  }, []);

  const prov = (label: string, val: string) => (
    <div style={{ fontSize: 12 }}>
      <span style={{ color: '#7d8a84' }}>{label}: </span>
      <span style={{ color: val && val !== 'unavailable' && !val.startsWith('naive') && !val.startsWith('raw') && !val.startsWith('none') ? '#00D4FF' : '#FF9F1C' }}>
        {val || '—'}
      </span>
    </div>
  );

  return (
    <div style={{ padding: 24, color: '#c7d3cd', fontFamily: 'monospace' }}>
      <h1 style={{ color: '#00E5A0', margin: 0 }}>Telemetry</h1>
      <p style={{ color: '#7d8a84', marginTop: 4 }}>
        Live state — {state.connected ? <span style={{ color: '#00E5A0' }}>● connected</span> : <span style={{ color: '#FF2A2A' }}>● disconnected</span>}
        {'  '}source: {nav.source || '—'}, mode: {state.mode}
      </p>

      <div style={{ ...panel, marginBottom: 16, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        {prov('nav', nav.navBackend)}
        {prov('control', nav.controlBackend)}
        {prov('detect', nav.detectBackend)}
        <div style={{ fontSize: 12 }}><span style={{ color: '#7d8a84' }}>nav NIS: </span><span style={{ color: '#c7d3cd' }}>{nav.nis.toFixed(2)}</span></div>
        <div style={{ fontSize: 12 }}><span style={{ color: '#7d8a84' }}>position: </span><span style={{ color: '#c7d3cd' }}>{state.position.lat.toFixed(6)}, {state.position.lon.toFixed(6)}</span></div>
        <div style={{ fontSize: 12 }}><span style={{ color: '#7d8a84' }}>heading: </span><span style={{ color: '#c7d3cd' }}>{Math.round(state.heading)}°</span></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Spark data={hist.current.alt} color="#00E5A0" unit="m" label="ALTITUDE" />
        <Spark data={hist.current.spd} color="#00D4FF" unit="m/s" label="GROUND SPEED" />
        <Spark data={hist.current.batt} color="#FFD166" unit="%" label="BATTERY" />
        <div style={panel}>
          <div style={{ color: '#7d8a84', fontSize: 12, letterSpacing: 1, marginBottom: 8 }}>NAV FILTER</div>
          <div style={{ fontSize: 13, lineHeight: 1.9 }}>
            The altitude/speed shown are the <span style={{ color: '#00D4FF' }}>22-state AUKF</span> estimate,
            not raw GPS. NIS (normalized innovation squared) near 1–10 = filter consistent.
            <br />Current NIS: <span style={{ color: '#00E5A0' }}>{nav.nis.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Telemetry;
