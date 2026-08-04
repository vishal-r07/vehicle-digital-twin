import React from 'react';
import styles from './Dashboard.module.css';

function FuelGauge({ value, normalized, isLow }) {
  return (
    <div className={`${styles['gauge-card']} ${isLow ? styles['warning'] : ''}`}>
      <span className={styles['gauge-label']}>Fuel Level</span>
      
      <div style={{ width: '100%', height: '24px', background: '#2a3a52', borderRadius: '12px', overflow: 'hidden' }}>
        <div
          style={{
            width: `${normalized * 100}%`,
            height: '100%',
            background: isLow
              ? 'linear-gradient(90deg, #ff6b35, #ffa500)'
              : 'linear-gradient(90deg, #00d4ff, #00ff88)',
            borderRadius: '12px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      <div>
        <span className={styles['gauge-value']} style={{ fontSize: '1.5rem', color: isLow ? '#ffa500' : '#00d4ff' }}>
          {value.toFixed(1)}
        </span>
        <span className={styles['gauge-unit']}>%</span>
      </div>
      
      {isLow && <span style={{ color: '#ffa500', fontSize: '0.7rem' }}>⚠ LOW FUEL</span>}
    </div>
  );
}

export default FuelGauge;