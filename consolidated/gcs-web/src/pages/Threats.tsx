import React, { useEffect, useState } from 'react';
import { AdsBService } from '../services/AdsBService';
import { Threat } from '../App';

const SEV_COLOR: Record<string, string> = {
  critical: '#FF2A2A',
  high: '#FF9F1C',
  medium: '#FFD166',
  low: '#00E5A0',
};

const panel: React.CSSProperties = {
  background: '#111',
  border: '1px solid #1e2a24',
  borderRadius: 8,
  padding: 16,
};

const Threats: React.FC = () => {
  const [threats, setThreats] = useState<Threat[]>([]);
  const [stats, setStats] = useState({ total: 0, critical: 0, high: 0, medium: 0, low: 0 });
  const [backend, setBackend] = useState('');

  useEffect(() => {
    const svc = AdsBService.getInstance();
    const tick = () => {
      setThreats(svc.getAllThreats());
      setStats(svc.getThreatStats());
      setBackend(svc.getDetectBackend());
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ padding: 24, color: '#c7d3cd', fontFamily: 'monospace' }}>
      <h1 style={{ color: '#00E5A0', margin: 0 }}>Threats</h1>
      <p style={{ color: '#7d8a84', marginTop: 4 }}>Counter-UAS threat detection &amp; alerts</p>

      <div style={{ margin: '8px 0 16px', fontSize: 12, color: '#7d8a84' }}>
        classifier:&nbsp;
        <span style={{ color: backend ? '#00D4FF' : '#FF9F1C' }}>
          {backend || 'waiting for backend /ws/threats …'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        {([
          ['TOTAL', stats.total, '#00D4FF'],
          ['CRITICAL', stats.critical, SEV_COLOR.critical],
          ['HIGH', stats.high, SEV_COLOR.high],
          ['MEDIUM', stats.medium, SEV_COLOR.medium],
          ['LOW', stats.low, SEV_COLOR.low],
        ] as [string, number, string][]).map(([label, val, color]) => (
          <div key={label} style={{ ...panel, minWidth: 96, textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color }}>{val}</div>
            <div style={{ fontSize: 11, color: '#7d8a84', letterSpacing: 1 }}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{ ...panel, padding: 0, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ color: '#7d8a84', textAlign: 'left' }}>
              {['ID', 'TYPE', 'BEHAVIOR', 'SEVERITY', 'DISTANCE', 'BEARING', 'TIME'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', borderBottom: '1px solid #1e2a24' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {threats.length === 0 && (
              <tr>
                <td colSpan={7} style={{ padding: 20, textAlign: 'center', color: '#7d8a84' }}>
                  No active threats
                </td>
              </tr>
            )}
            {threats.map((t) => (
              <tr key={t.id} style={{ borderBottom: '1px solid #161f1b' }}>
                <td style={{ padding: '10px 14px' }}>{t.id}</td>
                <td style={{ padding: '10px 14px' }}>{t.type}</td>
                <td style={{ padding: '10px 14px', color: '#00D4FF' }}>{t.behavior || '—'}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{
                    color: SEV_COLOR[t.severity] || '#c7d3cd',
                    border: `1px solid ${SEV_COLOR[t.severity] || '#333'}`,
                    borderRadius: 4, padding: '2px 8px', fontSize: 11, textTransform: 'uppercase',
                  }}>
                    {t.severity}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }}>{Math.round(t.distance)} m</td>
                <td style={{ padding: '10px 14px' }}>{Math.round(t.bearing)}°</td>
                <td style={{ padding: '10px 14px', color: '#7d8a84' }}>
                  {t.timestamp instanceof Date ? t.timestamp.toLocaleTimeString() : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Threats;
