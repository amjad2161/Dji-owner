/**
 * Transient toast for command accept/reject. Subscribes to the backend's ack/nack
 * replies (via TelemetryService) so a rejected goto (geofence / no route) or a failed
 * command is surfaced to the operator instead of silently doing nothing.
 */
import React, { useEffect, useState } from 'react';
import { TelemetryService, CommandResult } from '../services/TelemetryService';

const CommandToast: React.FC = () => {
  const [toast, setToast] = useState<CommandResult | null>(null);

  useEffect(() => TelemetryService.getInstance().subscribeCommandResult(setToast), []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), toast.ok ? 2500 : 5000);
    return () => clearTimeout(t);
  }, [toast]);

  if (!toast) return null;

  return (
    <div
      role="status"
      style={{
        position: 'fixed', bottom: 20, right: 20, zIndex: 1000, maxWidth: 380,
        padding: '10px 16px', borderRadius: 8, fontFamily: 'monospace', fontSize: 13, color: '#fff',
        background: toast.ok ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.97)',
        border: `1px solid ${toast.ok ? '#22c55e' : '#ef4444'}`,
      }}
    >
      <strong>{toast.command.toUpperCase()} {toast.ok ? '✓ accepted' : '✗ rejected'}</strong>
      {toast.reason && <div style={{ marginTop: 4, opacity: 0.92 }}>{toast.reason}</div>}
    </div>
  );
};

export default CommandToast;
