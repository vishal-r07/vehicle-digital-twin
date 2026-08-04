import React from 'react';
import styles from './Dashboard.module.css';

function BatteryStatus({ value, isLow }) {
  const color = isLow ? '#ffa500' : '#00ff88';

  return (
    <div className={`${styles['gauge-card']} ${isLow ? styles['warning'] : ''}`}>
      <span className={styles['gauge-label']}>Battery</span>
      
      <div style={{ fontSize: '2rem' }}>🔋</div>

      <div>
        <span className={styles['gauge-value']} style={{ fontSize: '1.5rem', color }}>
          {value.toFixed(1)}
        </span>
        <span className={styles['gauge-unit']}>V</span>
      </div>
    </div>
  );
}

export default BatteryStatus;