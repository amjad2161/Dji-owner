/**
 * SkyCore ADS-B / C-UAS Service
 *
 * Threat awareness for the GCS. This service is a THIN CONSUMER of the backend's
 * real C-UAS classifier feed (WebSocket /ws/threats) — it does NOT invent contacts.
 * Everything shown to the operator is the classifier's verdict, so the Threats page
 * cannot mix fabricated rows with real detections.
 */

import { Threat } from '../App';

export type ThreatLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export class AdsBService {
  private static instance: AdsBService;
  private monitoring = false;

  // Live threats from the real backend C-UAS classifier (ws /ws/threats)
  private threatWs: WebSocket | null = null;
  private backendThreats: Threat[] = [];
  private backendDetectBackend = '';
  private threatReconnect = 0;
  private threatReconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private constructor() {}

  public static getInstance(): AdsBService {
    if (!AdsBService.instance) {
      AdsBService.instance = new AdsBService();
    }
    return AdsBService.instance;
  }

  public startMonitoring(): void {
    if (this.monitoring) return;
    this.monitoring = true;
    this.connectBackendThreats();       // consume the real classifier feed; no simulated contacts
    console.log('C-UAS monitoring started');
  }

  private connectBackendThreats(): void {
    if (!this.monitoring) return;                       // a queued reconnect must not revive a stopped feed
    if (this.threatWs?.readyState === WebSocket.OPEN) return;
    try {
      // same-origin under the unified server (wss on https); dev backend is on :8080
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = import.meta.env.DEV ? `${window.location.hostname}:8080` : window.location.host;
      const url = `${proto}//${host}/ws/threats`;
      const ws = new WebSocket(url);
      this.threatWs = ws;
      ws.onopen = () => { this.threatReconnect = 0; console.log('C-UAS threat feed connected'); };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.backendDetectBackend = data.detect_backend ?? '';
          this.backendThreats = (data.threats ?? []).map((t: {
            id: string; type: string; severity: ThreatLevel; distance: number; bearing: number; timestamp: number; behavior?: string;
          }) => ({
            id: t.id,
            type: t.type,
            severity: (t.severity === 'none' ? 'low' : t.severity) as Threat['severity'],
            distance: t.distance,
            bearing: t.bearing,
            timestamp: new Date(t.timestamp),
            behavior: t.behavior,
          }));
        } catch (e) {
          console.error('Failed to parse threat feed:', e);
        }
      };
      ws.onclose = () => {
        this.backendThreats = [];
        if (this.monitoring && this.threatReconnect < 5) {
          this.threatReconnect++;
          this.threatReconnectTimer = setTimeout(() => {
            this.threatReconnectTimer = null;
            this.connectBackendThreats();
          }, 2000 * this.threatReconnect);
        }
      };
      ws.onerror = () => { /* onclose handles retry */ };
    } catch (e) {
      console.error('Threat feed connect failed:', e);
    }
  }

  public stopMonitoring(): void {
    this.monitoring = false;                            // set first so a firing reconnect bails
    if (this.threatReconnectTimer) {                    // cancel a pending reconnect so it can't revive the socket
      clearTimeout(this.threatReconnectTimer);
      this.threatReconnectTimer = null;
    }
    if (this.threatWs) {
      this.threatWs.onclose = null;                     // don't let close() schedule another reconnect
      this.threatWs.close();
      this.threatWs = null;
    }
    this.backendThreats = [];
    console.log('C-UAS monitoring stopped');
  }

  public getDetectBackend(): string {
    return this.backendDetectBackend;
  }

  /** Real backend C-UAS classifier threats only — no fabricated contacts. */
  public getAllThreats(): Threat[] {
    return [...this.backendThreats];
  }

  public getThreatStats(): { total: number; critical: number; high: number; medium: number; low: number } {
    const all = this.backendThreats;
    return {
      total: all.length,
      critical: all.filter(t => t.severity === 'critical').length,
      high: all.filter(t => t.severity === 'high').length,
      medium: all.filter(t => t.severity === 'medium').length,
      low: all.filter(t => t.severity === 'low').length,
    };
  }
}
