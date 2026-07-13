/**
 * SkyCore Telemetry Service
 * Singleton service for real-time drone telemetry with WebSocket
 */

import { DroneState } from '../App';

export class TelemetryService {
  private static instance: TelemetryService;
  private ws: WebSocket | null = null;
  private subscribers: Set<(state: DroneState) => void> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private currentState: DroneState = {
    connected: false,
    battery: 100,
    altitude: 0,
    speed: 0,
    position: { lat: 0, lon: 0 },
    heading: 0,
    mode: 'DISARMED'
  };
  private navInfo = { navBackend: '', controlBackend: '', detectBackend: '', nis: 0, source: '' };
  private pending: string[] = [];

  private constructor() {}

  public static getInstance(): TelemetryService {
    if (!TelemetryService.instance) {
      TelemetryService.instance = new TelemetryService();
    }
    return TelemetryService.instance;
  }

  public connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      // Connect to local SkyCore API
      const wsUrl = `ws://${window.location.hostname}:8080/ws/telemetry`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('Telemetry connected');
        this.reconnectAttempts = 0;
        this.currentState.connected = true;
        // flush any commands queued before the socket opened
        for (const msg of this.pending) this.ws?.send(msg);
        this.pending = [];
        this.notifySubscribers();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.currentState = {
            ...this.currentState,
            battery: data.battery?.percent ?? this.currentState.battery,
            altitude: data.position?.altitude ?? this.currentState.altitude,
            speed: data.velocity?.speed ?? this.currentState.speed,
            position: data.position ?? this.currentState.position,
            heading: data.attitude?.yaw ?? this.currentState.heading,
            mode: data.mode ?? this.currentState.mode
          };
          this.navInfo = {
            navBackend: data.nav_backend ?? this.navInfo.navBackend,
            controlBackend: data.control_backend ?? this.navInfo.controlBackend,
            detectBackend: data.detect_backend ?? this.navInfo.detectBackend,
            nis: data.nav_nis ?? this.navInfo.nis,
            source: data.source ?? this.navInfo.source,
          };
          this.notifySubscribers();
        } catch (e) {
          console.error('Failed to parse telemetry:', e);
        }
      };

      this.ws.onclose = () => {
        console.log('Telemetry disconnected');
        this.currentState.connected = false;
        this.notifySubscribers();
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('Telemetry error:', error);
      };
    } catch (error) {
      console.error('Failed to connect telemetry:', error);
    }
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.currentState.connected = false;
    this.notifySubscribers();
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  public subscribe(callback: (state: DroneState) => void): () => void {
    this.subscribers.add(callback);
    // Send current state immediately
    callback(this.currentState);
    
    // Return unsubscribe function
    return () => {
      this.subscribers.delete(callback);
    };
  }

  public unsubscribe(callback: (state: DroneState) => void): void {
    this.subscribers.delete(callback);
  }

  private notifySubscribers(): void {
    this.subscribers.forEach(callback => {
      try {
        callback(this.currentState);
      } catch (e) {
        console.error('Subscriber error:', e);
      }
    });
  }

  public getCurrentState(): DroneState {
    return { ...this.currentState };
  }

  public getNavInfo() {
    return { ...this.navInfo };
  }

  // Commands
  public async arm(): Promise<boolean> {
    return this.sendCommand('arm');
  }

  public async disarm(): Promise<boolean> {
    return this.sendCommand('disarm');
  }

  public async takeoff(altitude: number): Promise<boolean> {
    return this.sendCommand('takeoff', { altitude });
  }

  public async land(): Promise<boolean> {
    return this.sendCommand('land');
  }

  public async rtl(): Promise<boolean> {
    return this.sendCommand('rtl');
  }

  public async goto(lat: number, lon: number, altitude: number): Promise<boolean> {
    return this.sendCommand('goto', { lat, lon, altitude });
  }

  private async sendCommand(command: string, params?: Record<string, unknown>): Promise<boolean> {
    const msg = JSON.stringify({ command, ...params });
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // queue until the socket opens, so the first command after a page load isn't dropped
      this.pending.push(msg);
      if (!this.ws || this.ws.readyState === WebSocket.CLOSED) this.connect();
      return true;
    }

    try {
      this.ws.send(msg);
      return true;
    } catch (e) {
      console.error('Failed to send command:', e);
      return false;
    }
  }
}