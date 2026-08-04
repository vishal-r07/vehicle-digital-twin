import React from 'react';
import styles from './Dashboard.module.css';

function Speedometer({ value, normalized }) {
  const angle = -135 + (normalized * 270);
  const isHighSpeed = value > 200;

  return (
    <div className={`${styles['gauge-card']} ${isHighSpeed ? styles['warning'] : ''}`}>
      <span className={styles['gauge-label']}>Speed</span>
      
      <svg width="200" height="140" viewBox="0 0 200 140">
        {/* Outer ring */}
        <circle cx="100" cy="110" r="85" fill="none" stroke="#1e2a42" strokeWidth="2" />
        
        {/* Background arc */}
        <path
          d="M 15 110 A 85 85 0 1 1 185 110"
          fill="none"
          stroke="#2a3a52"
          strokeWidth="12"
          strokeLinecap="round"
        />
        
        {/* Tick marks */}
        {Array.from({ length: 11 }).map((_, i) => {
          const tickAngle = -135 + (i * 27);
          const x1 = 100 + 75 * Math.cos((tickAngle - 90) * Math.PI / 180);
          const y1 = 110 + 75 * Math.sin((tickAngle - 90) * Math.PI / 180);
          const x2 = 100 + 85 * Math.cos((tickAngle - 90) * Math.PI / 180);
          const y2 = 110 + 85 * Math.sin((tickAngle - 90) * Math.PI / 180);
          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="#4a5a72"
              strokeWidth="2"
            />
          );
        })}

        {/* Value arc */}
        <path
          d="M 15 110 A 85 85 0 1 1 185 110"
          fill="none"
          stroke={isHighSpeed ? '#ff6b35' : '#00d4ff'}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${normalized * 267} 267`}
          style={{ 
            transition: 'stroke-dasharray 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 10px ${isHighSpeed ? '#ff6b35' : '#00d4ff'})`
          }}
        />

        {/* Needle */}
        <line
          x1="100" y1="110"
          x2={100 + 65 * Math.cos((angle - 90) * Math.PI / 180)}
          y2={110 + 65 * Math.sin((angle - 90) * Math.PI / 180)}
          stroke={isHighSpeed ? '#ff6b35' : '#ff3333'}
          strokeWidth="3"
          strokeLinecap="round"
          style={{ 
            transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 8px ${isHighSpeed ? '#ff6b35' : '#ff3333'})`
          }}
        />

        {/* Center cap */}
        <circle cx="100" cy="110" r="8" fill="#1a1a2e" stroke="#4a5a72" strokeWidth="2" />
        <circle cx="100" cy="110" r="4" fill={isHighSpeed ? '#ff6b35' : '#00d4ff'} />
      </svg>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
        <span className={styles['gauge-value']} style={{ 
          fontSize: '2.5rem',
          color: isHighSpeed ? '#ff6b35' : undefined
        }}>
          {Math.round(value)}
        </span>
        <span className={styles['gauge-unit']}>km/h</span>
      </div>
    </div>
  );
}

export default Speedometer;