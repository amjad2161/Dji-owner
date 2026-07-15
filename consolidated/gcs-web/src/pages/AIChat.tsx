import React, { useEffect, useRef, useState } from 'react';
import { OpenRouterService, ChatMessage } from '../services/OpenRouterService';
import { TelemetryService } from '../services/TelemetryService';
import { AdsBService } from '../services/AdsBService';

function sitrep(): string {
  const s = TelemetryService.getInstance().getCurrentState();
  const nav = TelemetryService.getInstance().getNavInfo();
  const st = AdsBService.getInstance().getThreatStats();
  return `link=${s.connected ? 'CONNECTED' : 'DOWN'} mode=${s.mode} alt=${s.altitude.toFixed(1)}m spd=${s.speed.toFixed(1)}m/s batt=${s.battery.toFixed(0)}% pos=${s.position.lat.toFixed(5)},${s.position.lon.toFixed(5)} hdg=${Math.round(s.heading)}deg threats=${st.total}(crit ${st.critical},high ${st.high}) nav=${nav.navBackend || '-'} detect=${nav.detectBackend || '-'}`;
}

// Deterministic offline assistant, answers from live telemetry (used when no API key)
function localReply(text: string): string {
  const t = text.toLowerCase();
  const s = TelemetryService.getInstance().getCurrentState();
  const st = AdsBService.getInstance().getThreatStats();
  if (/help|command|what can/.test(t)) return 'Offline assistant. Ask: status, battery, altitude, position, threats. (Full AI runs via the server proxy when an OpenRouter key is configured.)';
  if (/batter/.test(t)) return `Battery ${s.battery.toFixed(0)}%. ${s.battery < 25 ? 'Low — recommend Return-to-Home.' : 'Nominal.'}`;
  if (/alt|height/.test(t)) return `Altitude ${s.altitude.toFixed(1)} m, mode ${s.mode}, climb/descent ${s.speed.toFixed(1)} m/s ground speed.`;
  if (/position|where|location|coord/.test(t)) return `Position ${s.position.lat.toFixed(6)}, ${s.position.lon.toFixed(6)}; heading ${Math.round(s.heading)}°.`;
  if (/threat|intrud|uas|hostile|drone/.test(t)) return `${st.total} tracks: ${st.critical} critical, ${st.high} high, ${st.medium} medium. Check the Threats page for the classifier detail.`;
  if (/status|sitrep|report|situation/.test(t)) return sitrep();
  return 'Offline assistant. Try: status, battery, altitude, position, threats.';
}

const AIChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'sys', role: 'assistant',
    content: 'AI operator. When the server has an OpenRouter key I answer via the model; otherwise I answer from live telemetry — try "status", "battery", "threats".',
    timestamp: new Date(),
  }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const svc = OpenRouterService.getInstance();

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const push = (m: ChatMessage) => setMessages((prev) => [...prev, m]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    push({ id: 'u' + Date.now(), role: 'user', content: text, timestamp: new Date() });

    setBusy(true);
    const id = 'a' + Date.now();
    push({ id, role: 'assistant', content: '', timestamp: new Date() });
    const history: ChatMessage[] = [
      { id: 'sys', role: 'system', content: svc.getSystemPrompt('en') + '\nLive telemetry: ' + sitrep(), timestamp: new Date() },
      ...messages.filter((m) => m.role !== 'system'),
      { id: 'u', role: 'user', content: text, timestamp: new Date() },
    ];
    const setContent = (content: string) =>
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content } : m)));
    // Try the server AI proxy; if it has no key / errors, answer from live telemetry offline.
    await svc.streamCompletion(
      history,
      (chunk) => setContent(chunk),          // non-streaming proxy: whole reply as one chunk
      () => setBusy(false),
      () => { setContent(localReply(text)); setBusy(false); },
    );
  };

  return (
    <div style={{ padding: 24, color: '#c7d3cd', fontFamily: 'monospace', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)' }}>
      <h1 style={{ color: '#00E5A0', margin: 0 }}>AI Operator</h1>
      <p style={{ color: '#7d8a84', marginTop: 4 }}>
        Mode: <span style={{ color: '#00D4FF' }}>server AI proxy</span> — falls back to the
        offline telemetry assistant when the server has no OpenRouter key.
      </p>

      <div style={{ flex: 1, overflowY: 'auto', background: '#0c110f', border: '1px solid #1e2a24', borderRadius: 8, padding: 14, margin: '8px 0' }}>
        {messages.filter((m) => m.role !== 'system').map((m) => (
          <div key={m.id} style={{ margin: '10px 0', textAlign: m.role === 'user' ? 'right' : 'left' }}>
            <span style={{
              display: 'inline-block', maxWidth: '80%', padding: '8px 12px', borderRadius: 8, whiteSpace: 'pre-wrap',
              background: m.role === 'user' ? '#132019' : '#111',
              border: `1px solid ${m.role === 'user' ? '#1e3a2a' : '#1e2a24'}`,
              color: m.role === 'user' ? '#c7d3cd' : '#a8e6cf',
            }}>
              {m.content || (busy ? '…' : '')}
            </span>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
          placeholder='Ask the operator assistant… (e.g. "status", "any threats?")'
          style={{ flex: 1, background: '#0a0f0d', border: '1px solid #1e2a24', borderRadius: 6, padding: '10px 12px', color: '#c7d3cd', fontFamily: 'monospace' }}
        />
        <button onClick={send} disabled={busy} style={{ background: '#132019', color: '#00E5A0', border: '1px solid #1e2a24', borderRadius: 6, padding: '0 20px', cursor: busy ? 'default' : 'pointer', fontFamily: 'monospace' }}>
          {busy ? '…' : 'Send'}
        </button>
      </div>
    </div>
  );
};

export default AIChat;
