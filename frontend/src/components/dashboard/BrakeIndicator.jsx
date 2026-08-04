import React from 'react';
import styles from './Dashboard.module.css';

function BrakeIndicator({ active }) {
  return (
    <div className={`${styles['gauge-card']} ${active ? styles['danger'] : ''}`}>
      <span className={styles['gauge-label']}>Brake</span>
      <div
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          background: active ? '#ff3333' : '#2a3a52',
          boxShadow: active ? '0 0 20px rgba(255,51,51,0.6)' : 'none',
          transition: 'all 0.15s ease',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1.2rem',
        }}
      >
        {active ? '🛑' : '⚪'}
      </div>
      <span style={{ fontSize: '0.7rem', color: active ? '#ff3333' : '#7a8ba0' }}>
        {active ? 'APPLIED' : 'RELEASED'}
      </span>
    </div>
  );
}

export default BrakeIndicator;