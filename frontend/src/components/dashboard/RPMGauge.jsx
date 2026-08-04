import React from 'react';
import styles from './Dashboard.module.css';

function RPMGauge({ value, normalized, isRedline }) {
  const angle = -135 + (normalized * 270);

  return (
    <div className={`${styles['gauge-card']} ${isRedline ? styles['danger'] : ''}`}>
      <span className={styles['gauge-label']}>Engine RPM</span>
      
      <svg width="200" height="140" viewBox="0 0 200 140">
        <circle cx="100" cy="110" r="85" fill="none" stroke="#1e2a42" strokeWidth="2" />
        
        <path
          d="M 15 110 A 85 85 0 1 1 185 110"
          fill="none"
          stroke="#2a3a52"
          strokeWidth="12"
          strokeLinecap="round"
        />

        {/* Redline zone (last 20%) */}
        <path
          d="M 15 110 A 85 85 0 1 1 185 110"
          fill="none"
          stroke="rgba(255,51,51,0.15)"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray="53.4 213.6"
          strokeDashoffset="-213.6"
        />

        {Array.from({ length: 9 }).map((_, i) => {
          const tickAngle = -135 + (i * 33.75);
          const x1 = 100 + 75 * Math.cos((tickAngle - 90) * Math.PI / 180);
          const y1 = 110 + 75 * Math.sin((tickAngle - 90) * Math.PI / 180);
          const x2 = 100 + 85 * Math.cos((tickAngle - 90) * Math.PI / 180);
          const y2 = 110 + 85 * Math.sin((tickAngle - 90) * Math.PI / 180);
          const isRedZone = i >= 7;
          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={isRedZone ? '#ff3333' : '#4a5a72'}
              strokeWidth="2"
            />
          );
        })}

        <path
          d="M 15 110 A 85 85 0 1 1 185 110"
          fill="none"
          stroke={isRedline ? '#ff3333' : '#00ff88'}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${normalized * 267} 267`}
          style={{ 
            transition: 'stroke-dasharray 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 10px ${isRedline ? '#ff3333' : '#00ff88'})`
          }}
        />

        <line
          x1="100" y1="110"
          x2={100 + 65 * Math.cos((angle - 90) * Math.PI / 180)}
          y2={110 + 65 * Math.sin((angle - 90) * Math.PI / 180)}
          stroke={isRedline ? '#ff3333' : '#ff6b35'}
          strokeWidth="3"
          strokeLinecap="round"
          style={{ 
            transition: 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 8px ${isRedline ? '#ff3333' : '#ff6b35'})`
          }}
        />

        <circle cx="100" cy="110" r="8" fill="#1a1a2e" stroke="#4a5a72" strokeWidth="2" />
        <circle cx="100" cy="110" r="4" fill={isRedline ? '#ff3333' : '#ff6b35'} />
      </svg>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
        <span className={styles['gauge-value']} style={{ 
          fontSize: '2.5rem',
          background: isRedline ? 'linear-gradient(135deg, #ff3333 0%, #ff6b35 100%)' : undefined,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: isRedline ? 'transparent' : undefined,
        }}>
          {Math.round(value)}
        </span>
        <span className={styles['gauge-unit']}>RPM</span>
      </div>
      
      {isRedline && (
        <div style={{
          fontSize: '0.7rem',
          color: '#ff3333',
          fontWeight: '700',
          letterSpacing: '1px',
          animation: 'pulse 1s ease-in-out infinite'
        }}>
          ⚠ REDLINE ZONE
        </div>
      )}
    </div>
  );
}

export default RPMGauge;