import React from 'react';
import Speedometer from './Speedometer';
import RPMGauge from './RPMGauge';
import FuelGauge from './FuelGauge';
import TemperatureGauge from './TemperatureGauge';
import BatteryStatus from './BatteryStatus';
import GearIndicator from './GearIndicator';
import BrakeIndicator from './BrakeIndicator';
import SteeringDisplay from './SteeringDisplay';
import AcceleratorBar from './AcceleratorBar';
import DoorStatus from './DoorStatus';
import ConnectionStatus from './ConnectionStatus';
import Timestamp from './Timestamp';
import styles from './Dashboard.module.css';

function Dashboard({ data, isConnected }) {
  // Default values when no data
  const d = data || {
    speed: 0, rpm: 0, fuel: 100, temp: 25, battery: 12.6,
    steering: 0, brake: 0, accelerator: 0, gear: 'P', door: 'Closed',
    timestamp: null, speedNorm: 0, rpmNorm: 0, fuelNorm: 1,
    tempNorm: 0.34, accelNorm: 0, steeringNorm: 0,
    isRpmRedline: false, isTempHigh: false, isTempCritical: false,
    isFuelLow: false, isBatteryLow: false, isBraking: false,
  };

  return (
    <div className={styles.dashboard}>
      {/* Primary Gauges Row */}
      <div className={`${styles['gauge-row']} ${styles.primary}`}>
        <Speedometer value={d.speed} normalized={d.speedNorm} />
        <RPMGauge value={d.rpm} normalized={d.rpmNorm} isRedline={d.isRpmRedline} />
      </div>

      {/* Secondary Gauges Row */}
      <div className={`${styles['gauge-row']} ${styles.secondary}`}>
        <FuelGauge value={d.fuel} normalized={d.fuelNorm} isLow={d.isFuelLow} />
        <TemperatureGauge value={d.temp} normalized={d.tempNorm} isHigh={d.isTempHigh} isCritical={d.isTempCritical} />
        <BatteryStatus value={d.battery} isLow={d.isBatteryLow} />
      </div>

      {/* Indicators Row */}
      <div className={styles['indicator-row']}>
        <GearIndicator gear={d.gear} />
        <BrakeIndicator active={d.isBraking} />
        <SteeringDisplay angle={d.steering} normalized={d.steeringNorm} />
        <AcceleratorBar value={d.accelerator} normalized={d.accelNorm} />
        <DoorStatus status={d.door} />
      </div>

      {/* Status Row */}
      <div className={styles['status-row']}>
        <ConnectionStatus connected={isConnected} />
        <Timestamp time={d.timestamp} />
      </div>
    </div>
  );
}

export default Dashboard;