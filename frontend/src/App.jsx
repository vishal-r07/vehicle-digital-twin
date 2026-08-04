import React from 'react';
import Dashboard from './components/dashboard/Dashboard';
import VehicleScene from './components/threejs/VehicleScene';
import { useVehicleData } from './hooks/useVehicleData';
import './styles/global.css';

function App() {
  const { vehicleData, isConnected, error } = useVehicleData();

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">
            <span className="title-icon">⚡</span>
            Vehicle Digital Twin
          </h1>
          <span className="phase-badge">Phase 1</span>
        </div>
        <div className="header-right">
          <span className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
          <span className="status-text">
            {isConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Left: Dashboard Gauges */}
        <section className="dashboard-section">
          <Dashboard data={vehicleData} isConnected={isConnected} />
        </section>

        {/* Right: 3D Vehicle */}
        <section className="threed-section">
          <VehicleScene data={vehicleData} />
        </section>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <span>Vehicle Digital Twin © 2026</span>
        <span>STM32F103 • CAN 500kbps • WebSocket 20Hz</span>
      </footer>
    </div>
  );
}

export default App;