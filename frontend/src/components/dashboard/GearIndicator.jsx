import React from 'react';
import styles from './Dashboard.module.css';

function GearIndicator({ gear }) {
  const gearColors = {
    P: '#7a8ba0',
    R: '#ff6b35',
    N: '#ffa500',
    D: '#00ff88',
    S: '#ff3333',
    L: '#6366f1',
    M: '#00d4ff',
  };

  return (
    <div className={styles['gauge-card']}>
      <span className={styles['gauge-label']}>Gear</span>
      <span
        style={{
          fontSize: '2.5rem',
          fontWeight: 800,
          fontFamily: 'var(--font-mono)',
          color: gearColors[gear] || '#fff',
          textShadow: `0 0 20px ${gearColors[gear] || '#fff'}`,
        }}
      >
        {gear}
      </span>
    </div>
  );
}

export default GearIndicator;