/**
 * SkyCore GCS - Main App Component
 * React Router + Pages
 */

import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Missions from './pages/Missions';
import Threats from './pages/Threats';
import VideoStream from './pages/VideoStream';
import AIChat from './pages/AIChat';
import Telemetry from './pages/Telemetry';
import CommandToast from './components/CommandToast';

// Services
import { TelemetryService } from './services/TelemetryService';
import { AdsBService } from './services/AdsBService';
import { getToken, tokenValid, setSession, getUser, clearSession } from './services/auth';

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
  behavior?: string;
}

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);

  // Connect the live services ONLY once authenticated — the backend rejects
  // unauthenticated WebSockets, so a token must exist before connecting.
  const startServices = () => {
    TelemetryService.getInstance().connect();
    AdsBService.getInstance().startMonitoring();
  };

  useEffect(() => {
    // Restore a still-valid session (the server re-verifies the signature)
    const token = getToken();
    if (token && tokenValid(token)) {
      setUser(getUser());
      setIsAuthenticated(true);
      startServices();
    } else {
      clearSession();
    }
  }, []);

  const handleLogin = (username: string, token: string, role: string) => {
    setSession(token, username, role);
    setUser({ username, role });
    setIsAuthenticated(true);
    startServices();
  };

  const handleLogout = () => {
    clearSession();
    setIsAuthenticated(false);
    setUser(null);
    TelemetryService.getInstance().disconnect();
    AdsBService.getInstance().stopMonitoring();
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
            <NavLink to="/" end className="nav-link">Dashboard</NavLink>
            <NavLink to="/missions" className="nav-link">Missions</NavLink>
            <NavLink to="/threats" className="nav-link">Threats</NavLink>
            <NavLink to="/video" className="nav-link">Video</NavLink>
            <NavLink to="/chat" className="nav-link">AI Chat</NavLink>
            <NavLink to="/telemetry" className="nav-link">Telemetry</NavLink>
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
        <CommandToast />
      </div>
    </BrowserRouter>
  );
};

export default App;