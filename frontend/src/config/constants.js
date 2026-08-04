/**
 * Application-wide constants
 * Centralized to avoid magic numbers
 */

export const WS_URL = 'ws://localhost:8765';
export const RECONNECT_INTERVAL = 3000; // ms
export const MAX_RECONNECT_ATTEMPTS = 50;

export const THRESHOLDS = {
  RPM_REDLINE: 6500,
  RPM_WARNING: 5500,
  TEMP_HIGH: 105,
  TEMP_CRITICAL: 120,
  FUEL_LOW: 15,
  FUEL_CRITICAL: 5,
  BATTERY_LOW: 11.5,
  SPEED_HIGH: 200,
};

export const GAUGE_LIMITS = {
  speed: { min: 0, max: 300 },
  rpm: { min: 0, max: 8000 },
  fuel: { min: 0, max: 100 },
  temp: { min: -40, max: 150 },
  battery: { min: 9, max: 16 },
  steering: { min: -720, max: 720 },
  accelerator: { min: 0, max: 100 },
};

export const COLORS = {
  primary: '#00d4ff',
  secondary: '#ff6b35',
  warning: '#ffa500',
  danger: '#ff3333',
  success: '#00ff88',
  background: '#0a0e17',
  surface: '#141b2d',
  surfaceLight: '#1e2a42',
  text: '#e0e6ed',
  textDim: '#7a8ba0',
  accent: '#6366f1',
};