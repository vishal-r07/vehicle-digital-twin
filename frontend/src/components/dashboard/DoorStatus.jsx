import React from 'react';
import styles from './Dashboard.module.css';

function DoorStatus({ status }) {
  const isOpen = status !== 'Closed';

  return (
    <div className={`${styles['gauge-card']} ${isOpen ? styles['warning'] : ''}`}>
      <span className={styles['gauge-label']}>Doors</span>
      <div style={{ fontSize: '1.8rem' }}>
        {isOpen ? '🚪' : '🔒'}
      </div>
      <span style={{ fontSize: '0.75rem', color: isOpen ? '#ffa500' : '#00ff88' }}>
        {status}
      </span>
    </div>
  );
}

export default DoorStatus;