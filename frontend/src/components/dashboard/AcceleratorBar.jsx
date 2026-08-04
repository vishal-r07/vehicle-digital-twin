import React from 'react';
import styles from './Dashboard.module.css';

function AcceleratorBar({ value, normalized }) {
  return (
    <div className={styles['gauge-card']}>
      <span className={styles['gauge-label']}>Throttle</span>
      
      <div style={{ width: '100%', height: '16px', background: '#2a3a52', borderRadius: '8px', overflow: 'hidden' }}>
        <div
          style={{
            width: `${normalized * 100}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #00ff88, #ffa500, #ff3333)',
            borderRadius: '8px',
            transition: 'width 0.1s ease',
          }}
        />
      </div>

      <span className={styles['gauge-value']} style={{ fontSize: '1.2rem' }}>
        {value.toFixed(0)}<span className={styles['gauge-unit']}>%</span>
      </span>
    </div>
  );
}

export default AcceleratorBar;