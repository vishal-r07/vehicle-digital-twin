/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    config.h
 * @brief   Master configuration for STM32F103RB + MCP2515 CAN firmware
 * @version 2.0.0
 * @date    2026-01-15
 * 
 * @details
 * This file contains ALL hardware and software configuration constants.
 * No magic numbers should appear in other source files.
 * 
 * Hardware Target:
 *   - MCU:       STM32F103RB (Nucleo-64)
 *   - CAN:       MCP2515 (SPI-to-CAN controller)
 *   - Transceiver: MCP2551 / TJA1050 (onboard MCP2515 module)
 *   - Debug:     USB Serial via ST-Link (PA9/PA10)
 * 
 * @note Modify ONLY this file when changing hardware connections.
 * ============================================================================
 */

#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// SECTION 1: FIRMWARE VERSION & IDENTITY
// ============================================================================

#define FW_VERSION_MAJOR    2
#define FW_VERSION_MINOR    0
#define FW_VERSION_PATCH    0
#define FW_BUILD_DATE       __DATE__
#define FW_BUILD_TIME       __TIME__
#define FW_NAME             "AutoTwinCAN"
#define FW_PLATFORM         "STM32F103RB"

// ============================================================================
// SECTION 2: MCP2515 SPI PIN MAPPING
// ============================================================================
// STM32F103RB SPI1 default pins:
//   MOSI = PA7
//   MISO = PA6
//   SCK  = PA5
// CS and INT are user-selectable GPIOs.

#define MCP2515_SPI_MOSI    PA7     // SPI1 Master Out Slave In
#define MCP2515_SPI_MISO    PA6     // SPI1 Master In Slave Out
#define MCP2515_SPI_SCK     PA5     // SPI1 Clock
#define MCP2515_SPI_CS      PA4     // Chip Select (active LOW)
#define MCP2515_INT         PB0     // Interrupt output (active LOW)

// SPI peripheral selection
#define MCP2515_SPI_PORT    SPI1

// ============================================================================
// SECTION 3: MCP2515 CAN CONFIGURATION
// ============================================================================

// Crystal frequency on the MCP2515 module (Hz)
// Most modules use 8 MHz. Some use 16 MHz.
// CHECK YOUR MODULE's crystal marking!
#define MCP2515_CRYSTAL_HZ  8000000UL    // 8 MHz (most common)
// #define MCP2515_CRYSTAL_HZ  16000000UL  // 16 MHz (uncomment if applicable)

// CAN Bus baud rate (bps)
#define CAN_BAUD_RATE       500000UL     // 500 kbps (automotive standard)

// CAN Mode
#define CAN_MODE_NORMAL     0x00         // Normal operation
#define CAN_MODE_LOOPBACK   0x01         // Self-test (no bus needed)
#define CAN_MODE_LISTEN     0x02         // Listen-only (silent)
#define CAN_MODE_CONFIG     0x03         // Configuration mode

// Startup mode
#define CAN_STARTUP_MODE    CAN_MODE_NORMAL

// ============================================================================
// SECTION 4: MCP2515 BIT TIMING REGISTERS
// ============================================================================
// Pre-calculated for common configurations.
// Formula: Bit Time = (SYNC + PRSEG + PHSEG1 + PHSEG2) × TQ
//          TQ = 2 × (BRP + 1) / F_OSC
//
// For 8 MHz crystal, 500 kbps, 8 TQ/bit:
//   TQ = 2×(0+1)/8MHz = 250ns
//   Bit Time = 8 × 250ns = 2μs → 500 kbps ✓
//   Sample Point = (1+1+3)/8 = 62.5%
//
// For 16 MHz crystal, 500 kbps, 8 TQ/bit:
//   TQ = 2×(1+1)/16MHz = 250ns
//   Bit Time = 8 × 250ns = 2μs → 500 kbps ✓

#if MCP2515_CRYSTAL_HZ == 8000000UL
    // 8 MHz crystal, 500 kbps
    #define MCP2515_CNF1    0x00    // SJW=1TQ, BRP=0
    #define MCP2515_CNF2    0x90    // BTLMODE=1, SAM=0, PHSEG1=3TQ, PRSEG=1TQ
    #define MCP2515_CNF3    0x02    // PHSEG2=3TQ
#elif MCP2515_CRYSTAL_HZ == 16000000UL
    // 16 MHz crystal, 500 kbps
    #define MCP2515_CNF1    0x01    // SJW=1TQ, BRP=1
    #define MCP2515_CNF2    0x90    // BTLMODE=1, SAM=0, PHSEG1=3TQ, PRSEG=1TQ
    #define MCP2515_CNF3    0x02    // PHSEG2=3TQ
#else
    #error "Unsupported MCP2515 crystal frequency. Define CNF values manually."
#endif

// ============================================================================
// SECTION 5: CAN FILTER & MASK CONFIGURATION
// ============================================================================
// Phase 1 CAN IDs: 0x100 - 0x10F
// We configure MCP2515 acceptance filters to accept only these IDs.
//
// Filter mode:
//   0 = Accept all messages (no filtering)
//   1 = Accept only configured IDs
//   2 = Accept ID range

#define CAN_FILTER_MODE     1       // 1 = Use specific filters

// Accepted CAN ID range (Phase 1)
#define CAN_ID_MIN          0x100
#define CAN_ID_MAX          0x10F

// Individual CAN IDs (for reference and serial protocol)
#define CAN_ID_SPEED        0x100   // Vehicle Speed
#define CAN_ID_RPM          0x101   // Engine RPM
#define CAN_ID_FUEL         0x102   // Fuel Level
#define CAN_ID_TEMP         0x103   // Coolant Temperature
#define CAN_ID_BATTERY      0x104   // Battery Voltage
#define CAN_ID_STEERING     0x105   // Steering Angle
#define CAN_ID_BRAKE        0x106   // Brake Status
#define CAN_ID_ACCELERATOR  0x107   // Accelerator Position
#define CAN_ID_GEAR         0x108   // Gear Position
#define CAN_ID_DOOR         0x109   // Door Status
#define CAN_ID_INDICATORS   0x10A   // Turn Indicators / Hazards
#define CAN_ID_HEADLIGHTS   0x10B   // Headlight Status
#define CAN_ID_WHEEL_SPEED  0x10C   // Individual Wheel Speeds
#define CAN_ID_ENGINE_LOAD  0x10D   // Engine Load
#define CAN_ID_AMBIENT_TEMP 0x10E   // Ambient Temperature
#define CAN_ID_ODOMETER     0x10F   // Odometer

// Total number of CAN IDs we handle
#define CAN_ID_COUNT        16

// ============================================================================
// SECTION 6: SERIAL COMMUNICATION CONFIGURATION
// ============================================================================

#define SERIAL_BAUD_RATE    115200UL
#define SERIAL_PORT         Serial          // USB CDC via ST-Link
#define SERIAL_TIMEOUT_MS   100             // Read timeout

// Serial Protocol Delimiters
#define FRAME_START_MARKER  "---AUTOTWIN---\n"
#define FRAME_END_MARKER    "---END---\n"
#define FRAME_START_TOKEN   "---AUTOTWIN---"
#define FRAME_END_TOKEN     "---END---"

// Serial output rate limiter (ms between full state prints)
#define SERIAL_PRINT_INTERVAL_MS  50    // 20 Hz output rate

// Debug output enable/disable
#define SERIAL_DEBUG_ENABLED    1       // 1 = debug messages ON
#define SERIAL_DEBUG_PORT       Serial  // Same port for Phase 1

// ============================================================================
// SECTION 7: SIGNAL CONVERSION FACTORS
// ============================================================================
// Formula: physical_value = raw_value × resolution + offset
// These match the DBC file definitions.

#define SPEED_RESOLUTION        0.01f       // km/h per LSB (16-bit)
#define SPEED_OFFSET            0.0f
#define SPEED_MAX               300.0f

#define RPM_RESOLUTION          1.0f        // rpm per LSB (16-bit)
#define RPM_OFFSET              0.0f
#define RPM_MAX                 8000.0f

#define FUEL_RESOLUTION         0.5f        // % per LSB (8-bit)
#define FUEL_OFFSET             0.0f
#define FUEL_MAX                100.0f

#define TEMP_RESOLUTION         1.0f        // °C per LSB (8-bit)
#define TEMP_OFFSET             (-40.0f)    // Offset for negative temps
#define TEMP_MAX                215.0f

#define BATTERY_RESOLUTION      0.01f       // V per LSB (16-bit)
#define BATTERY_OFFSET          0.0f
#define BATTERY_MAX             20.0f

#define STEERING_RESOLUTION     0.1f        // deg per LSB (16-bit signed)
#define STEERING_OFFSET         0.0f
#define STEERING_MAX            720.0f

#define ACCEL_RESOLUTION        0.5f        // % per LSB (8-bit)
#define ACCEL_OFFSET            0.0f
#define ACCEL_MAX               100.0f

#define ENGINE_LOAD_RESOLUTION  0.5f        // % per LSB (8-bit)
#define ENGINE_LOAD_OFFSET      0.0f
#define ENGINE_LOAD_MAX         100.0f

#define AMBIENT_TEMP_RESOLUTION 1.0f        // °C per LSB (8-bit)
#define AMBIENT_TEMP_OFFSET     (-40.0f)

#define WHEEL_SPEED_RESOLUTION  0.01f       // km/h per LSB (16-bit each)
#define WHEEL_SPEED_OFFSET      0.0f

#define ODOMETER_RESOLUTION     0.1f        // km per LSB (32-bit)
#define ODOMETER_OFFSET         0.0f

// ============================================================================
// SECTION 8: GEAR & ENUM DEFINITIONS
// ============================================================================

enum GearPosition : uint8_t {
    GEAR_PARK     = 0,
    GEAR_REVERSE  = 1,
    GEAR_NEUTRAL  = 2,
    GEAR_DRIVE    = 3,
    GEAR_SPORT    = 4,
    GEAR_LOW      = 5,
    GEAR_MANUAL   = 6,
    GEAR_UNKNOWN  = 0xFF
};

// Door bitmask positions
#define DOOR_FL_BIT   0     // Front Left
#define DOOR_FR_BIT   1     // Front Right
#define DOOR_RL_BIT   2     // Rear Left
#define DOOR_RR_BIT   3     // Rear Right
#define DOOR_HOOD_BIT 4     // Hood
#define DOOR_TRUNK_BIT 5    // Trunk

// Indicator bitmask
#define INDICATOR_LEFT_BIT    0
#define INDICATOR_RIGHT_BIT   1
#define INDICATOR_HAZARD_BIT  2

// Headlight bitmask
#define HEADLIGHT_LOW_BIT     0
#define HEADLIGHT_HIGH_BIT    1
#define HEADLIGHT_FOG_BIT     2

// ============================================================================
// SECTION 9: TIMING & PERFORMANCE
// ============================================================================

#define MAIN_LOOP_DELAY_US      100     // Main loop cycle time (μs)
#define CAN_POLL_INTERVAL_MS    1       // CAN check every 1ms
#define LED_BLINK_MS            500     // Status LED blink rate
#define LED_FAST_BLINK_MS       100     // Error LED blink rate
#define WATCHDOG_TIMEOUT_MS     5000    // Reset if no activity for 5s
#define CAN_TIMEOUT_MS          2000    // Flag if no CAN data for 2s
#define SERIAL_FLUSH_INTERVAL   10      // Flush serial every N frames

// ============================================================================
// SECTION 10: STATUS LED CONFIGURATION
// ============================================================================

#define LED_BUILTIN_PIN         LED_BUILTIN   // PA5 on Nucleo (shared with SCK!)
#define LED_STATUS_PIN          PB5           // External status LED
#define LED_ERROR_PIN           PB4           // External error LED
#define LED_CAN_ACTIVE_PIN      PB3           // CAN activity indicator

// LED States
enum LedState : uint8_t {
    LED_OFF = 0,
    LED_SLOW_BLINK,       // Normal idle
    LED_FAST_BLINK,       // CAN active
    LED_SOLID,            // Error / CAN timeout
    LED_HEARTBEAT         // System alive, no CAN
};

// ============================================================================
// SECTION 11: BUFFER SIZES
// ============================================================================

#define CAN_RX_BUFFER_SIZE      64      // Number of CAN frames to buffer
#define SERIAL_TX_BUFFER_SIZE   512     // Serial transmit buffer
#define SERIAL_RX_BUFFER_SIZE   128     // Serial receive buffer
#define ERROR_LOG_SIZE          16      // Circular error log

// ============================================================================
// SECTION 12: FEATURE FLAGS
// ============================================================================

#define FEATURE_CAN_FILTERING   1       // Enable MCP2515 HW filtering
#define FEATURE_CAN_INTERRUPT   1       // Use INT pin for RX notification
#define FEATURE_SERIAL_CRC      0       // Add CRC to serial frames (future)
#define FEATURE_AUTO_RECOVERY   1       // Auto-recover from CAN bus-off
#define FEATURE_FRAME_COUNTER   1       // Count received frames
#define FEATURE_ERROR_LOGGING   1       // Log errors to circular buffer
#define FEATURE_HEARTBEAT       1       // Periodic heartbeat output
#define FEATURE_LOOPBACK_TEST   0       // Enable for bench testing

// ============================================================================
// SECTION 13: MCP2515 REGISTER DEFINITIONS
// ============================================================================
// Complete MCP2515 register map for the SPI driver.

// --- SPI Instructions ---
#define MCP2515_CMD_RESET       0xC0
#define MCP2515_CMD_READ        0x03
#define MCP2515_CMD_WRITE       0x02
#define MCP2515_CMD_RTS         0x80
#define MCP2515_CMD_READ_STATUS 0xA0
#define MCP2515_CMD_RX_STATUS   0xB0
#define MCP2515_CMD_BIT_MODIFY  0x05

// --- Control Registers ---
#define MCP2515_REG_CANCTRL     0x0F    // CAN Control Register
#define MCP2515_REG_CANSTAT     0x0E    // CAN Status Register
#define MCP2515_REG_BFPCTRL     0x0C    // RXnBF Pin Control
#define MCP2515_REG_TXRTSCTRL   0x0D    // TXnRTS Pin Control

// --- Bit Timing ---
#define MCP2515_REG_CNF1        0x2A    // Configuration 1
#define MCP2515_REG_CNF2        0x29    // Configuration 2
#define MCP2515_REG_CNF3        0x28    // Configuration 3

// --- Interrupt ---
#define MCP2515_REG_CANINTE     0x2B    // Interrupt Enable
#define MCP2515_REG_CANINTF     0x2C    // Interrupt Flag

// --- Error ---
#define MCP2515_REG_EFLG        0x2D    // Error Flag
#define MCP2515_REG_TEC         0x1C    // Transmit Error Counter
#define MCP2515_REG_REC         0x1D    // Receive Error Counter

// --- Receive Buffers ---
#define MCP2515_REG_RXB0CTRL    0x60    // RX Buffer 0 Control
#define MCP2515_REG_RXB0SIDH    0x61    // RX Buffer 0 Standard ID High
#define MCP2515_REG_RXB0SIDL    0x62    // RX Buffer 0 Standard ID Low
#define MCP2515_REG_RXB0EID8    0x63    // RX Buffer 0 Extended ID High
#define MCP2515_REG_RXB0EID0    0x64    // RX Buffer 0 Extended ID Low
#define MCP2515_REG_RXB0DLC     0x65    // RX Buffer 0 DLC
#define MCP2515_REG_RXB0DATA    0x66    // RX Buffer 0 Data (8 bytes)

#define MCP2515_REG_RXB1CTRL    0x70    // RX Buffer 1 Control
#define MCP2515_REG_RXB1SIDH    0x71
#define MCP2515_REG_RXB1SIDL    0x72
#define MCP2515_REG_RXB1EID8    0x73
#define MCP2515_REG_RXB1EID0    0x74
#define MCP2515_REG_RXB1DLC     0x75
#define MCP2515_REG_RXB1DATA    0x76

// --- Transmit Buffers ---
#define MCP2515_REG_TXB0CTRL    0x30
#define MCP2515_REG_TXB0SIDH    0x31
#define MCP2515_REG_TXB0SIDL    0x32
#define MCP2515_REG_TXB0EID8    0x33
#define MCP2515_REG_TXB0EID0    0x34
#define MCP2515_REG_TXB0DLC     0x35
#define MCP2515_REG_TXB0DATA    0x36

#define MCP2515_REG_TXB1CTRL    0x40
#define MCP2515_REG_TXB2CTRL    0x50

// --- Acceptance Filters ---
#define MCP2515_REG_RXF0SIDH    0x00
#define MCP2515_REG_RXF0SIDL    0x01
#define MCP2515_REG_RXF0EID8    0x02
#define MCP2515_REG_RXF0EID0    0x03

#define MCP2515_REG_RXF1SIDH    0x04
#define MCP2515_REG_RXF1SIDL    0x05
#define MCP2515_REG_RXF1EID8    0x06
#define MCP2515_REG_RXF1EID0    0x07

#define MCP2515_REG_RXF2SIDH    0x08
#define MCP2515_REG_RXF2SIDL    0x09
#define MCP2515_REG_RXF2EID8    0x0A
#define MCP2515_REG_RXF2EID0    0x0B

#define MCP2515_REG_RXF3SIDH    0x10
#define MCP2515_REG_RXF3SIDL    0x11
#define MCP2515_REG_RXF3EID8    0x12
#define MCP2515_REG_RXF3EID0    0x13

#define MCP2515_REG_RXF4SIDH    0x14
#define MCP2515_REG_RXF4SIDL    0x15
#define MCP2515_REG_RXF4EID8    0x16
#define MCP2515_REG_RXF4EID0    0x17

#define MCP2515_REG_RXF5SIDH    0x18
#define MCP2515_REG_RXF5SIDL    0x19
#define MCP2515_REG_RXF5EID8    0x1A
#define MCP2515_REG_RXF5EID0    0x1B

// --- Acceptance Masks ---
#define MCP2515_REG_RXM0SIDH    0x20
#define MCP2515_REG_RXM0SIDL    0x21
#define MCP2515_REG_RXM0EID8    0x22
#define MCP2515_REG_RXM0EID0    0x23

#define MCP2515_REG_RXM1SIDH    0x24
#define MCP2515_REG_RXM1SIDL    0x25
#define MCP2515_REG_RXM1EID8    0x26
#define MCP2515_REG_RXM1EID0    0x27

// --- CANCTRL Bit Definitions ---
#define MCP2515_CANCTRL_REQOP   0xE0    // Request Operation Mode
#define MCP2515_CANCTRL_ABAT    0x10    // Abort All Pending Transmissions
#define MCP2515_CANCTRL_OSM     0x08    // One-Shot Mode
#define MCP2515_CANCTRL_CLKEN   0x04    // Clock Pin Enable
#define MCP2515_CANCTRL_CLKPRE  0x03    // Clock Prescaler

// Operation Modes (for CANCTRL[7:5])
#define MCP2515_MODE_NORMAL     0x00
#define MCP2515_MODE_SLEEP      0x20
#define MCP2515_MODE_LOOPBACK   0x40
#define MCP2515_MODE_LISTEN     0x60
#define MCP2515_MODE_CONFIG     0x80

// --- CANSTAT Bit Definitions ---
#define MCP2515_CANSTAT_OPMOD   0xE0    // Operation Mode
#define MCP2515_CANSTAT_ICOD    0x0E    // Interrupt Code

// --- CANINTE / CANINTF Bit Definitions ---
#define MCP2515_INT_RX0IF       0x01    // RX Buffer 0 Full
#define MCP2515_INT_RX1IF       0x02    // RX Buffer 1 Full
#define MCP2515_INT_TX0IF       0x04    // TX Buffer 0 Empty
#define MCP2515_INT_TX1IF       0x08    // TX Buffer 1 Empty
#define MCP2515_INT_TX2IF       0x10    // TX Buffer 2 Empty
#define MCP2515_INT_ERRIF       0x20    // Error Interrupt
#define MCP2515_INT_WAKIF       0x40    // Wakeup Interrupt
#define MCP2515_INT_MERRF       0x80    // Message Error Interrupt

// --- EFLG Bit Definitions ---
#define MCP2515_EFLG_EWARN      0x01    // Error Warning
#define MCP2515_EFLG_RXWAR      0x02    // RX Error Warning
#define MCP2515_EFLG_TXWAR      0x04    // TX Error Warning
#define MCP2515_EFLG_RXEP       0x08    // RX Error Passive
#define MCP2515_EFLG_TXEP       0x10    // TX Error Passive
#define MCP2515_EFLG_TXBO       0x20    // TX Bus-Off
#define MCP2515_EFLG_RX0OVR     0x40    // RX Buffer 0 Overflow
#define MCP2515_EFLG_RX1OVR     0x80    // RX Buffer 1 Overflow

// --- RXBnCTRL Bit Definitions ---
#define MCP2515_RXBCTRL_RXM0    0x20    // Receive Buffer Mode bit 0
#define MCP2515_RXBCTRL_RXM1    0x40    // Receive Buffer Mode bit 1
#define MCP2515_RXBCTRL_BUKT    0x04    // Rollover enable (RXB0 → RXB1)

// ============================================================================
// SECTION 14: SPI CONFIGURATION
// ============================================================================

#define SPI_CLOCK_MAX_HZ        10000000UL  // 10 MHz max for MCP2515
#define SPI_DATA_ORDER          MSBFIRST
#define SPI_DATA_MODE           SPI_MODE0   // CPOL=0, CPHA=0

// ============================================================================
// SECTION 15: DIAGNOSTIC COUNTERS
// ============================================================================
// These counters track system health and are reported via serial.

typedef struct {
    uint32_t frames_received;       // Total CAN frames received
    uint32_t frames_decoded;        // Successfully decoded frames
    uint32_t frames_unknown;        // Unknown CAN ID frames
    uint32_t frames_error;          // Frames with decode errors
    uint32_t serial_bytes_sent;     // Total serial bytes transmitted
    uint32_t can_errors;            // CAN bus error count
    uint32_t can_overruns;          // RX buffer overflow count
    uint32_t can_bus_off;           // Bus-off event count
    uint32_t spi_errors;            // SPI communication errors
    uint32_t uptime_seconds;        // System uptime
} DiagnosticCounters;

#endif // CONFIG_H