/**
 * SkyCore GCS - Main App Component
 * React Router + Pages
 */

import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Missions from './pages/Missions';
import Threats from './pages/Threats';
import VideoStream from './pages/VideoStream';
import AIChat from './pages/AIChat';
import Telemetry from './pages/Telemetry';

// Services
import { TelemetryService } from './services/TelemetryService';
import { AdsBService } from './services/AdsBService';

export interface DroneState {
  connected: boolean;
  battery: number;
  altitude: number;
  speed: number;
  position: { lat: number; lon: number };
  heading: number;
  mode: string;
}

export interface Threat {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  distance: number;
  bearing: number;
  timestamp: Date;
}

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);

  useEffect(() => {
    // Initialize services
    TelemetryService.getInstance().connect();
    AdsBService.getInstance().startMonitoring();

    // Check existing session
    const token = localStorage.getItem('skycore_token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (username: string, token: string) => {
    localStorage.setItem('skycore_token', token);
    setIsAuthenticated(true);
    setUser({ username, role: 'operator' });
  };

  const handleLogout = () => {
    localStorage.removeItem('skycore_token');
    setIsAuthenticated(false);
    setUser(null);
    TelemetryService.getInstance().disconnect();
  };

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <div className="app-container">
        <nav className="sidebar">
          <div className="logo">SkyCore</div>
          <div className="nav-links">
            <a href="/" className="nav-link">Dashboard</a>
            <a href="/missions" className="nav-link">Missions</a>
            <a href="/threats" className="nav-link">Threats</a>
            <a href="/video" className="nav-link">Video</a>
            <a href="/chat" className="nav-link">AI Chat</a>
            <a href="/telemetry" className="nav-link">Telemetry</a>
          </div>
          <div className="user-info">
            <span>{user?.username}</span>
            <button onClick={handleLogout}>Logout</button>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/missions" element={<Missions />} />
            <Route path="/threats" element={<Threats />} />
            <Route path="/video" element={<VideoStream />} />
            <Route path="/chat" element={<AIChat />} />
            <Route path="/telemetry" element={<Telemetry />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;