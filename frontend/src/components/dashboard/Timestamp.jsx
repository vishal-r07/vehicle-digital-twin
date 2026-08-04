import React from 'react';

function Timestamp({ time }) {
  const display = time
    ? new Date(time).toLocaleTimeString('en-US', { hour12: false })
    : '--:--:--';

  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#7a8ba0' }}>
      ⏱ {display}
    </span>
  );
}

export default Timestamp;