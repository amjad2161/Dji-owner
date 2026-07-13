/**
 * SkyCore - Dashboard Page
 * Real-time status with map and telemetry
 */

import React, { useEffect, useState } from 'react';
import { TelemetryService } from '../services/TelemetryService';
import { AdsBService } from '../services/AdsBService';
import { DroneState, Threat } from '../App';

const Dashboard: React.FC = () => {
  const [droneState, setDroneState] = useState<DroneState>(TelemetryService.getInstance().getCurrentState());
  const [threatStats, setThreatStats] = useState({ total: 0, critical: 0, high: 0, medium: 0, low: 0 });

  useEffect(() => {
    const unsubscribe = TelemetryService.getInstance().subscribe(setDroneState);
    const interval = setInterval(() => {
      setThreatStats(AdsBService.getInstance().getThreatStats());
    }, 2000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <div className={`connection-status ${droneState.connected ? 'connected' : 'disconnected'}`}>
          {droneState.connected ? '🟢 מחובר' : '🔴 מנותק'}
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Map Section */}
        <div className="map-container">
          <div className="map-header">
            <h2>מפה</h2>
            <span className="coordinates">
              {droneState.position.lat.toFixed(6)}, {droneState.position.lon.toFixed(6)}
            </span>
          </div>
          <div className="map-canvas">
            {/* OpenStreetMap integration placeholder */}
            <div className="map-placeholder">
              <div className="drone-marker" style={{
                left: '50%', top: '50%',
                transform: `rotate(${droneState.heading}deg)`
              }}>
                🚁
              </div>
              <div className="home-marker">🏠</div>
              {threatStats.total > 0 && (
                <div className="threat-marker">⚠️</div>
              )}
            </div>
          </div>
          <div className="map-controls">
            <button onClick={() => TelemetryService.getInstance().arm()}>Arm</button>
            <button onClick={() => TelemetryService.getInstance().takeoff(20)}>Takeoff</button>
            <button onClick={() => TelemetryService.getInstance().land()}>Land</button>
            <button onClick={() => TelemetryService.getInstance().rtl()}>RTH</button>
          </div>
        </div>

        {/* Telemetry Cards */}
        <div className="telemetry-grid">
          <div className="telemetry-card battery">
            <div className="card-icon">🔋</div>
            <div className="card-content">
              <span className="card-label">סкумулятор</span>
              <span className="card-value">{droneState.battery}%</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{
                  width: `${droneState.battery}%`,
                  backgroundColor: droneState.battery < 30 ? '#ef4444' : 
                                    droneState.battery < 50 ? '#f59e0b' : '#22c55e'
                }} />
              </div>
            </div>
          </div>

          <div className="telemetry-card altitude">
            <div className="card-icon">📍</div>
            <div className="card-content">
              <span className="card-label">גובה</span>
              <span className="card-value">{droneState.altitude.toFixed(1)}m</span>
            </div>
          </div>

          <div className="telemetry-card speed">
            <div className="card-icon">⚡</div>
            <div className="card-content">
              <span className="card-label">מהירות</span>
              <span className="card-value">{droneState.speed.toFixed(1)}m/s</span>
            </div>
          </div>

          <div className="telemetry-card heading">
            <div className="card-icon">🧭</div>
            <div className="card-content">
              <span className="card-label">כיוון</span>
              <span className="card-value">{droneState.heading.toFixed(0)}°</span>
            </div>
          </div>

          <div className="telemetry-card mode">
            <div className="card-icon">🎮</div>
            <div className="card-content">
              <span className="card-label">מצב</span>
              <span className="card-value">{droneState.mode}</span>
            </div>
          </div>

          <div className="telemetry-card threats">
            <div className="card-icon">⚠️</div>
            <div className="card-content">
              <span className="card-label">איומים</span>
              <span className="card-value">{threatStats.total}</span>
              {threatStats.critical > 0 && (
                <span className="threat-critical">{threatStats.critical} קריטיים</span>
              )}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="activity-panel">
          <h3>פעילות אחרונה</h3>
          <div className="activity-list">
            <div className="activity-item">
              <span className="activity-time">12:34:56</span>
              <span className="activity-text">מערכת מאותחלת</span>
            </div>
            <div className="activity-item">
              <span className="activity-time">12:34:57</span>
              <span className="activity-text">GPS מחובר (12 לוויינים)</span>
            </div>
            <div className="activity-item">
              <span className="activity-time">12:34:58</span>
              <span className="activity-text">בטיחות תקין</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;