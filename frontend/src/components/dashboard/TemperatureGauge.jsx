import React from 'react';
import styles from './Dashboard.module.css';

function TemperatureGauge({ value, normalized, isHigh, isCritical }) {
  const color = isCritical ? '#ff3333' : isHigh ? '#ffa500' : '#00d4ff';

  return (
    <div className={`${styles['gauge-card']} ${isCritical ? styles['danger'] : isHigh ? styles['warning'] : ''}`}>
      <span className={styles['gauge-label']}>Coolant Temp</span>
      
      {/* Vertical thermometer */}
      <div style={{ width: '20px', height: '80px', background: '#2a3a52', borderRadius: '10px', position: 'relative', overflow: 'hidden' }}>
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            width: '100%',
            height: `${normalized * 100}%`,
            background: color,
            borderRadius: '10px',
            transition: 'height 0.3s ease, background 0.3s ease',
          }}
        />
      </div>

      <div>
        <span className={styles['gauge-value']} style={{ fontSize: '1.5rem', color }}>
          {value}
        </span>
        <span className={styles['gauge-unit']}>°C</span>
      </div>
      
      {isCritical && <span style={{ color: '#ff3333', fontSize: '0.7rem' }}>🔥 CRITICAL</span>}
    </div>
  );
}

export default TemperatureGauge;