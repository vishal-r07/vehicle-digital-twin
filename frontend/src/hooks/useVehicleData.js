/**
 * useVehicleData.js - Vehicle data processing hook
 * 
 * Adds computed values, smoothing, and threshold detection
 * on top of raw WebSocket data.
 */

import { useMemo } from 'react';
import { useWebSocket } from './useWebSocket';
import { THRESHOLDS } from '../config/constants';

export function useVehicleData() {
  const { data, isConnected, error } = useWebSocket();

  const vehicleData = useMemo(() => {
    if (!data) return null;

    return {
      ...data,
      // Computed flags
      isRpmRedline: data.rpm >= THRESHOLDS.RPM_REDLINE,
      isRpmWarning: data.rpm >= THRESHOLDS.RPM_WARNING,
      isTempHigh: data.temp >= THRESHOLDS.TEMP_HIGH,
      isTempCritical: data.temp >= THRESHOLDS.TEMP_CRITICAL,
      isFuelLow: data.fuel <= THRESHOLDS.FUEL_LOW,
      isFuelCritical: data.fuel <= THRESHOLDS.FUEL_CRITICAL,
      isBatteryLow: data.battery <= THRESHOLDS.BATTERY_LOW,
      isBraking: data.brake === 1,
      // Normalized values (0-1) for gauge animations
      speedNorm: Math.min(data.speed / 300, 1),
      rpmNorm: Math.min(data.rpm / 8000, 1),
      fuelNorm: data.fuel / 100,
      tempNorm: Math.max(0, (data.temp + 40) / 190),
      accelNorm: data.accelerator / 100,
      steeringNorm: data.steering / 720,
    };
  }, [data]);

  return { vehicleData, isConnected, error };
}