/**
 * SkyCore ADS-B Service
 * Threat detection and classification for airspace awareness
 */

import { Threat } from '../App';

export interface ADSBContact {
  icao: string;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;
  heading: number;
  timestamp: number;
}

export type ThreatLevel = 'none' | 'low' | 'medium' | 'high' | 'critical';

export class AdsBService {
  private static instance: AdsBService;
  private contacts: Map<string, ADSBContact> = new Map();
  private threats: Threat[] = [];
  private monitoring = false;
  private updateInterval: ReturnType<typeof setInterval> | null = null;

  // Live threats from the real backend C-UAS classifier (ws /ws/threats)
  private threatWs: WebSocket | null = null;
  private backendThreats: Threat[] = [];
  private backendDetectBackend = '';
  private threatReconnect = 0;
  private threatReconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // Threat thresholds
  private readonly SAFE_DISTANCE_M = 5000;
  private readonly WARNING_DISTANCE_M = 2000;
  private readonly CRITICAL_DISTANCE_M = 500;

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
    
    // Simulate ADS-B contacts for demo
    this.updateInterval = setInterval(() => {
      this.updateSimulatedContacts();
      this.evaluateThreats();
    }, 1000);

    // Also consume real C-UAS classifier threats from the backend
    this.connectBackendThreats();

    console.log('ADS-B monitoring started');
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
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }
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
    console.log('ADS-B monitoring stopped');
  }

  private updateSimulatedContacts(): void {
    // Simulated manned aircraft
    const now = Date.now();
    
    // Helicopter near Tel Aviv
    const heli: ADSBContact = {
      icao: '800ABC',
      callsign: 'HELI-1',
      latitude: 32.0853 + (Math.random() - 0.5) * 0.01,
      longitude: 34.7818 + (Math.random() - 0.5) * 0.01,
      altitude: 150 + Math.random() * 100,
      speed: 45 + Math.random() * 20,
      heading: Math.random() * 360,
      timestamp: now
    };

    this.contacts.set(heli.icao, heli);

    // Light aircraft
    const aircraft: ADSBContact = {
      icao: '400XYZ',
      callsign: 'CESS-123',
      latitude: 32.05 + (Math.random() - 0.5) * 0.02,
      longitude: 34.75 + (Math.random() - 0.5) * 0.02,
      altitude: 2000 + Math.random() * 1000,
      speed: 120 + Math.random() * 50,
      heading: 90 + Math.random() * 30,
      timestamp: now
    };

    this.contacts.set(aircraft.icao, aircraft);
  }

  private evaluateThreats(): void {
    this.threats = [];

    this.contacts.forEach((contact, icao) => {
      // Get drone position from telemetry (simplified)
      const droneLat = 32.0853;
      const droneLon = 34.7818;

      // Calculate distance
      const distanceM = this.calculateDistance(
        droneLat, droneLon,
        contact.latitude, contact.longitude
      );

      // Get threat level
      const threatLevel = this.classifyThreat(contact, distanceM);

      if (threatLevel !== 'none') {
        this.threats.push({
          id: icao,
          type: this.classifyAircraft(contact),
          severity: threatLevel,
          distance: distanceM,
          bearing: this.calculateBearing(droneLat, droneLon, contact.latitude, contact.longitude),
          timestamp: new Date(contact.timestamp)
        });
      }
    });
  }

  public classifyThreat(contact: ADSBContact, distanceM: number): ThreatLevel {
    // Critical if very close and low
    if (distanceM < this.CRITICAL_DISTANCE_M && contact.altitude < 500) {
      return 'critical';
    }

    // High if close
    if (distanceM < this.WARNING_DISTANCE_M) {
      return 'high';
    }

    // Medium if approaching
    if (distanceM < this.SAFE_DISTANCE_M) {
      return 'medium';
    }

    // Low if far but same altitude
    const droneAlt = 100; // Simplified
    if (distanceM < this.SAFE_DISTANCE_M * 2 && Math.abs(contact.altitude - droneAlt) < 300) {
      return 'low';
    }

    return 'none';
  }

  public classifyAircraft(contact: ADSBContact): string {
    if (contact.icao.startsWith('8')) {
      return 'Helicopter';
    }
    if (contact.icao.startsWith('4')) {
      return 'Light Aircraft';
    }
    return contact.callsign || 'Unknown';
  }

  private calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000; // Earth's radius in meters
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  private calculateBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const dLon = this.toRad(lon2 - lon1);
    const y = Math.sin(dLon) * Math.cos(this.toRad(lat2));
    const x = Math.cos(this.toRad(lat1)) * Math.sin(this.toRad(lat2)) -
              Math.sin(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) * Math.cos(dLon);
    let bearing = this.toDeg(Math.atan2(y, x));
    return (bearing + 360) % 360;
  }

  private toRad(deg: number): number {
    return deg * (Math.PI / 180);
  }

  private toDeg(rad: number): number {
    return rad * (180 / Math.PI);
  }

  public getAllContacts(): ADSBContact[] {
    return Array.from(this.contacts.values());
  }

  // Real backend C-UAS threats first, then simulated ADS-B contacts
  private merged(): Threat[] {
    return [...this.backendThreats, ...this.threats];
  }

  public getDetectBackend(): string {
    return this.backendDetectBackend;
  }

  public getAllThreats(): Threat[] {
    return this.merged();
  }

  public getThreatStats(): { total: number; critical: number; high: number; medium: number; low: number } {
    const all = this.merged();
    return {
      total: all.length,
      critical: all.filter(t => t.severity === 'critical').length,
      high: all.filter(t => t.severity === 'high').length,
      medium: all.filter(t => t.severity === 'medium').length,
      low: all.filter(t => t.severity === 'low').length
    };
  }

  public async fetchFromOpenSky(): Promise<void> {
    // Connect to OpenSky Network API
    try {
      const response = await fetch('https://opensky-network.org/api/states/all');
      const data = await response.json();
      
      this.contacts.clear();
      
      data.states?.forEach((state: string[]) => {
        const contact: ADSBContact = {
          icao: state[0],
          callsign: state[1]?.trim() || 'Unknown',
          latitude: parseFloat(state[6]) || 0,
          longitude: parseFloat(state[5]) || 0,
          altitude: parseFloat(state[7]) || 0,
          speed: parseFloat(state[9]) || 0,
          heading: parseFloat(state[10]) || 0,
          timestamp: Date.now()
        };
        this.contacts.set(contact.icao, contact);
      });

      this.evaluateThreats();
    } catch (e) {
      console.error('Failed to fetch OpenSky data:', e);
    }
  }
}