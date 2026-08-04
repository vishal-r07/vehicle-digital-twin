import React from 'react';
import styles from './Dashboard.module.css';

function SteeringDisplay({ angle, normalized }) {
  const rotation = normalized * 180; // -180° to +180° visual

  return (
    <div className={styles['gauge-card']}>
      <span className={styles['gauge-label']}>Steering</span>
      
      <div style={{ transform: `rotate(${rotation}deg)`, transition: 'transform 0.1s ease', fontSize: '2rem' }}>
        🎡
      </div>

      <div>
        <span className={styles['gauge-value']} style={{ fontSize: '1.2rem' }}>
          {angle.toFixed(1)}
        </span>
        <span className={styles['gauge-unit']}>°</span>
      </div>
    </div>
  );
}

export default SteeringDisplay;