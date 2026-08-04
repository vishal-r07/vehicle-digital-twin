import React from 'react';

function ConnectionStatus({ connected }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: connected ? '#00ff88' : '#ff3333',
          boxShadow: connected ? '0 0 8px #00ff88' : '0 0 8px #ff3333',
        }}
      />
      <span style={{ fontSize: '0.75rem', color: '#7a8ba0' }}>
        WebSocket: {connected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}

export default ConnectionStatus;