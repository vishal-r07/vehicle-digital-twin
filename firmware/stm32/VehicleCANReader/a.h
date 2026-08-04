/**
 * @file CANConfig.h
 * @brief CAN Bus Configuration Constants for Vehicle Digital Twin Phase 1
 * 
 * Hardware: STM32F103 Nucleo + SN65HVD230 CAN Transceiver
 * CAN Pins: RX=PB8, TX=PB9
 * Baud Rate: 500 kbps
 * 
 * Architecture Note: All CAN IDs and conversion factors are defined here
 * to support future expansion (J1939, OBD-II, additional ECUs).
 */

#ifndef CAN_CONFIG_H
#define CAN_CONFIG_H

// ============================================================
// CAN BUS CONFIGURATION
// ============================================================
#define CAN_BAUD_RATE       500000    // 500 kbps
#define CAN_RX_PIN          PB8
#define CAN_TX_PIN          PB9

// ============================================================
// SERIAL CONFIGURATION
// ============================================================
#define SERIAL_BAUD_RATE    115200
#define SERIAL_PORT         Serial    // USB Serial (PA9/PA10 on Nucleo)

// ============================================================
// CAN MESSAGE IDs (Phase 1)
// Future: Extend with J1939 PGN or OBD-II PIDs
// ============================================================
#define CAN_ID_SPEED        0x100
#define CAN_ID_RPM          0x101
#define CAN_ID_FUEL         0x102
#define CAN_ID_TEMP         0x103
#define CAN_ID_BATTERY      0x104
#define CAN_ID_STEERING     0x105
#define CAN_ID_BRAKE        0x106
#define CAN_ID_ACCELERATOR  0x107
#define CAN_ID_GEAR         0x108
#define CAN_ID_DOOR         0x109

// ============================================================
// SIGNAL CONVERSION FACTORS
// Formula: physical_value = raw_value * resolution + offset
// ============================================================
#define SPEED_RESOLUTION    0.01f     // km/h per LSB
#define SPEED_OFFSET        0.0f

#define RPM_RESOLUTION      1.0f      // rpm per LSB
#define RPM_OFFSET          0.0f

#define FUEL_RESOLUTION     0.5f      // % per LSB
#define FUEL_OFFSET         0.0f

#define TEMP_RESOLUTION     1.0f      // °C per LSB
#define TEMP_OFFSET         -40.0f    // Offset for temperature

#define BATTERY_RESOLUTION  0.01f     // V per LSB
#define BATTERY_OFFSET      0.0f

#define STEERING_RESOLUTION 0.1f      // deg per LSB (signed)
#define STEERING_OFFSET     0.0f

#define ACCEL_RESOLUTION    0.5f      // % per LSB
#define ACCEL_OFFSET        0.0f

// ============================================================
// GEAR POSITION ENUM
// ============================================================
enum GearPosition : uint8_t {
    GEAR_P = 0,   // Park
    GEAR_R = 1,   // Reverse
    GEAR_N = 2,   // Neutral
    GEAR_D = 3,   // Drive
    GEAR_S = 4,   // Sport
    GEAR_L = 5,   // Low
    GEAR_M = 6    // Manual
};

// ============================================================
// DOOR STATUS BITMASK
// ============================================================
#define DOOR_FL_BIT         0   // Front Left
#define DOOR_FR_BIT         1   // Front Right
#define DOOR_RL_BIT         2   // Rear Left
#define DOOR_RR_BIT         3   // Rear Right

// ============================================================
// TIMING
// ============================================================
#define SERIAL_PRINT_INTERVAL_MS  100   // Print state every 100ms (10 Hz)
#define CAN_TIMEOUT_MS            1000  // CAN message timeout

#endif // CAN_CONFIG_H