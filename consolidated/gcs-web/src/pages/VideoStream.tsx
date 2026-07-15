import React, { useEffect, useState } from 'react';
import { TelemetryService } from '../services/TelemetryService';
import { DroneState } from '../App';

const W = 640, H = 360;

const VideoStream: React.FC = () => {
  const [s, setS] = useState<DroneState>(TelemetryService.getInstance().getCurrentState());
  const [nav, setNav] = useState(TelemetryService.getInstance().getNavInfo());

  useEffect(() => {
    const svc = TelemetryService.getInstance();
    const id = setInterval(() => { setS(svc.getCurrentState()); setNav(svc.getNavInfo()); }, 300);
    return () => clearInterval(id);
  }, []);

  // compass ticks around current heading
  const ticks = [];
  for (let d = -60; d <= 60; d += 15) {
    const hdg = ((Math.round(s.heading / 15) * 15) + d + 360) % 360;
    const x = W / 2 + (d / 60) * (W / 2 - 40);
    ticks.push(
      <g key={d}>
        <line x1={x} y1={28} x2={x} y2={38} stroke="#2a3a32" />
        <text x={x} y={22} fill="#3a4a42" fontSize={10} textAnchor="middle">{hdg}</text>
      </g>,
    );
  }

  return (
    <div style={{ padding: 24, color: '#c7d3cd', fontFamily: 'monospace' }}>
      <h1 style={{ color: '#00E5A0', margin: 0 }}>Video</h1>
      <p style={{ color: '#7d8a84', marginTop: 4 }}>Camera feed and flight instruments</p>

      <div style={{
        background: '#2a0f0f', border: '1px solid #5a1f1f', color: '#FF6B6B',
        borderRadius: 8, padding: '10px 14px', margin: '8px 0', fontSize: 13,
      }}>
        ● NO LIVE CAMERA FEED — this backend is a simulator with no hardware camera. Shown below is a
        live telemetry <b>instrument HUD</b> (not video). Connect real DJI/PX4 hardware exposing RTSP to
        get a real feed.
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ background: '#070b09', border: '1px solid #1e2a24', borderRadius: 8, maxWidth: '100%' }}>
          {/* grid */}
          {Array.from({ length: 9 }, (_, i) => (
            <line key={'v' + i} x1={(i + 1) * (W / 10)} y1={0} x2={(i + 1) * (W / 10)} y2={H} stroke="#0e1512" />
          ))}
          {Array.from({ length: 5 }, (_, i) => (
            <line key={'h' + i} x1={0} y1={(i + 1) * (H / 6)} x2={W} y2={(i + 1) * (H / 6)} stroke="#0e1512" />
          ))}
          {/* watermark */}
          <text x={W / 2} y={H / 2 - 10} fill="#14201b" fontSize={34} textAnchor="middle" fontWeight="bold">NO SIGNAL</text>
          <text x={W / 2} y={H / 2 + 16} fill="#12201a" fontSize={13} textAnchor="middle">INSTRUMENT HUD — NOT CAMERA</text>

          {/* compass strip */}
          {ticks}
          <polygon points={`${W / 2 - 6},40 ${W / 2 + 6},40 ${W / 2},48`} fill="#00E5A0" />

          {/* crosshair */}
          <line x1={W / 2 - 24} y1={H / 2} x2={W / 2 - 8} y2={H / 2} stroke="#00E5A0" />
          <line x1={W / 2 + 8} y1={H / 2} x2={W / 2 + 24} y2={H / 2} stroke="#00E5A0" />
          <line x1={W / 2} y1={H / 2 - 24} x2={W / 2} y2={H / 2 - 8} stroke="#00E5A0" />
          <line x1={W / 2} y1={H / 2 + 8} x2={W / 2} y2={H / 2 + 24} stroke="#00E5A0" />

          {/* HUD readouts */}
          <text x={16} y={H / 2 - 6} fill="#00D4FF" fontSize={12}>SPD</text>
          <text x={16} y={H / 2 + 12} fill="#00E5A0" fontSize={20}>{s.speed.toFixed(1)}</text>
          <text x={W - 16} y={H / 2 - 6} fill="#00D4FF" fontSize={12} textAnchor="end">ALT</text>
          <text x={W - 16} y={H / 2 + 12} fill="#00E5A0" fontSize={20} textAnchor="end">{s.altitude.toFixed(1)}</text>

          <text x={16} y={H - 40} fill="#7d8a84" fontSize={11}>MODE {s.mode}</text>
          <text x={16} y={H - 24} fill="#7d8a84" fontSize={11}>HDG {Math.round(s.heading)}°  BATT {s.battery.toFixed(0)}%</text>
          <text x={16} y={H - 8} fill="#7d8a84" fontSize={11}>{s.position.lat.toFixed(5)}, {s.position.lon.toFixed(5)}</text>
          <text x={W - 16} y={H - 8} fill={s.connected ? '#00E5A0' : '#FF2A2A'} fontSize={11} textAnchor="end">
            {s.connected ? '● TELEMETRY LIVE' : '● NO LINK'}
          </text>
        </svg>

        <div style={{ minWidth: 220, background: '#111', border: '1px solid #1e2a24', borderRadius: 8, padding: 14, fontSize: 13, lineHeight: 1.9 }}>
          <div style={{ color: '#7d8a84', letterSpacing: 1, marginBottom: 6 }}>SOURCE</div>
          <div>nav: <span style={{ color: '#00D4FF' }}>{nav.navBackend || '—'}</span></div>
          <div>control: <span style={{ color: '#00D4FF' }}>{nav.controlBackend || '—'}</span></div>
          <div style={{ marginTop: 10, color: '#7d8a84' }}>
            To show a real camera, point the backend at DJI Mobile SDK / PX4 RTSP and stream frames on a
            <code style={{ color: '#a8e6cf' }}> /video </code> endpoint — the HUD stays as the overlay.
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoStream;
