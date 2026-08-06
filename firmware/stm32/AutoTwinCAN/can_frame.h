/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    can_frame.h
 * @brief   CAN frame data structures and vehicle state definitions
 * @version 2.0.0
 * @date    2026-01-15
 *
 * @details
 * Defines the core data structures used throughout the firmware:
 *   - RawCANFrame:    Raw CAN bus frame as received from MCP2515
 *   - DecodedSignal:  A single decoded signal with physical value
 *   - VehicleState:   Complete vehicle state (digital twin representation)
 *   - SignalConfig:   Metadata for signal decoding (from DBC)
 *
 * Design Principles:
 *   - All structures use fixed-size types for deterministic memory
 *   - Bit fields used where appropriate for CAN protocol accuracy
 *   - Union types for efficient multi-interpretation of data
 *   - No heap allocation — all stack/static
 *
 * @author  AutoTwin AI Development Team
 * ============================================================================
 */

#ifndef CAN_FRAME_H
#define CAN_FRAME_H

#include <Arduino.h>
#include "config.h"

// ============================================================================
// RAW CAN FRAME STRUCTURE
// ============================================================================

/**
 * @struct RawCANFrame
 * @brief Represents a single CAN bus frame as read from MCP2515.
 *
 * Memory layout: 4 + 1 + 8 + 1 + 4 = 18 bytes per frame
 * With 64-frame buffer: 64 × 18 = 1,152 bytes
 */
typedef struct {
    uint32_t id;                // CAN arbitration ID (11-bit or 29-bit)
    uint8_t  dlc;               // Data Length Code (0-8)
    uint8_t  data[8];           // Payload bytes
    bool     is_extended;       // true = 29-bit extended ID
    bool     is_remote;         // true = Remote Transmission Request
    uint32_t timestamp_us;      // micros() at reception time
} RawCANFrame;

// ============================================================================
// CAN FRAME RING BUFFER
// ============================================================================

/**
 * @struct CANFrameBuffer
 * @brief Circular buffer for CAN frames (FIFO).
 *
 * Prevents frame loss during serial output or processing delays.
 * Capacity: CAN_RX_BUFFER_SIZE frames (defined in config.h)
 */
typedef struct {
    RawCANFrame frames[CAN_RX_BUFFER_SIZE];
    volatile uint16_t head;         // Write position
    volatile uint16_t tail;         // Read position
    volatile uint16_t count;        // Current number of frames
    uint32_t overflow_count;        // Frames dropped due to full buffer
} CANFrameBuffer;

/**
 * @brief Initialize the CAN frame ring buffer
 */
static inline void canBuffer_init(CANFrameBuffer* buf) {
    buf->head = 0;
    buf->tail = 0;
    buf->count = 0;
    buf->overflow_count = 0;
    memset(buf->frames, 0, sizeof(buf->frames));
}

/**
 * @brief Push a frame into the buffer
 * @return true if successful, false if buffer full (frame dropped)
 */
static inline bool canBuffer_push(CANFrameBuffer* buf, const RawCANFrame* frame) {
    if (buf->count >= CAN_RX_BUFFER_SIZE) {
        buf->overflow_count++;
        return false;  // Buffer full, drop frame
    }

    buf->frames[buf->head] = *frame;
    buf->head = (buf->head + 1) % CAN_RX_BUFFER_SIZE;
    buf->count++;
    return true;
}

/**
 * @brief Pop a frame from the buffer
 * @param frame Output pointer
 * @return true if frame available, false if empty
 */
static inline bool canBuffer_pop(CANFrameBuffer* buf, RawCANFrame* frame) {
    if (buf->count == 0) {
        return false;  // Buffer empty
    }

    *frame = buf->frames[buf->tail];
    buf->tail = (buf->tail + 1) % CAN_RX_BUFFER_SIZE;
    buf->count--;
    return true;
}

/**
 * @brief Check if buffer is empty
 */
static inline bool canBuffer_isEmpty(const CANFrameBuffer* buf) {
    return buf->count == 0;
}

/**
 * @brief Check if buffer is full
 */
static inline bool canBuffer_isFull(const CANFrameBuffer* buf) {
    return buf->count >= CAN_RX_BUFFER_SIZE;
}

/**
 * @brief Get number of frames in buffer
 */
static inline uint16_t canBuffer_count(const CANFrameBuffer* buf) {
    return buf->count;
}

// ============================================================================
// DECODED SIGNAL STRUCTURE
// ============================================================================

/**
 * @struct DecodedSignal
 * @brief A single CAN signal after decoding to physical units.
 */
typedef struct {
    char     name[24];          // Signal name (e.g., "EngineCoolantTemp")
    float    physical_value;    // Value in engineering units
    int32_t  raw_value;         // Raw integer from CAN data
    char     unit[8];           // Unit string (e.g., "degC", "km/h")
    uint32_t can_id;            // Source CAN ID
    uint32_t timestamp_ms;      // millis() at decode time
    bool     is_valid;          // false if out of range
} DecodedSignal;

// ============================================================================
// SIGNAL CONFIGURATION (DBC-like metadata)
// ============================================================================

/**
 * @struct SignalConfig
 * @brief Configuration for decoding a single signal from CAN data.
 *        Mirrors DBC file signal definitions.
 */
typedef struct {
    char     name[24];          // Signal name
    uint32_t can_id;            // CAN message ID containing this signal
    uint8_t  start_bit;         // Start bit position in payload
    uint8_t  bit_length;        // Number of bits
    bool     is_signed;         // true = two's complement signed
    bool     big_endian;        // true = Motorola byte order
    float    factor;            // Multiplication factor
    float    offset;            // Addition offset
    float    min_value;         // Minimum valid physical value
    float    max_value;         // Maximum valid physical value
    char     unit[8];           // Engineering unit string
    uint8_t  subsystem;         // Subsystem enum for 3D mapping
} SignalConfig;

// ============================================================================
// VEHICLE STATE STRUCTURE
// ============================================================================

/**
 * @enum SubsystemID
 * @brief Identifies vehicle subsystems for 3D highlighting and diagnostics
 */
enum SubsystemID : uint8_t {
    SUBSYS_ENGINE       = 0,
    SUBSYS_TRANSMISSION = 1,
    SUBSYS_BRAKES       = 2,
    SUBSYS_COOLING      = 3,
    SUBSYS_BATTERY      = 4,
    SUBSYS_BODY         = 5,
    SUBSYS_STEERING     = 6,
    SUBSYS_ELECTRICAL   = 7,
    SUBSYS_FUEL         = 8,
    SUBSYS_SUSPENSION   = 9,
    SUBSYS_COUNT        = 10
};

/**
 * @enum GearPosition
 * @brief Transmission gear states
 */
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

/**
 * @struct EngineState
 * @brief Engine subsystem state
 */
typedef struct {
    uint16_t rpm;               // Engine speed [0..8000] rpm
    int16_t  coolant_temp;      // Coolant temperature [-40..215] °C
    int16_t  oil_temp;          // Oil temperature [-40..215] °C
    float    oil_pressure;      // Oil pressure [0..10] bar
    float    load;              // Engine load [0..100] %
    float    throttle_pos;      // Throttle position [0..100] %
    float    fuel_pressure;     // Fuel pressure [0..7] bar
    bool     engine_on;         // Engine running flag
    uint8_t  misfire_count;     // Misfire events since start
    uint32_t runtime_seconds;   // Total engine runtime
} EngineState;

/**
 * @struct TransmissionState
 * @brief Transmission subsystem state
 */
typedef struct {
    uint8_t  gear;              // Current gear (GearPosition enum)
    float    gear_ratio;        // Current gear ratio
    bool     torque_lockup;     // Torque converter locked
    float    slip_ratio;        // Clutch/torque converter slip
} TransmissionState;

/**
 * @struct BrakeState
 * @brief Brake subsystem state
 */
typedef struct {
    bool     applied;           // Brake pedal pressed
    float    pedal_position;    // Pedal travel [0..100] %
    float    pressure;          // Brake pressure [0..200] bar
    bool     abs_active;        // ABS intervention active
    bool     esp_active;        // ESP/stability control active
    float    pad_wear_fl;       // Front-left pad wear [0..100] %
    float    pad_wear_fr;       // Front-right pad wear [0..100] %
    float    pad_wear_rl;       // Rear-left pad wear [0..100] %
    float    pad_wear_rr;       // Rear-right pad wear [0..100] %
} BrakeState;

/**
 * @struct CoolingState
 * @brief Cooling system state
 */
typedef struct {
    int16_t  coolant_temp;      // Coolant temperature [-40..215] °C
    bool     fan_active;        // Radiator fan running
    uint8_t  fan_speed;         // Fan speed [0..100] %
    bool     thermostat_open;   // Thermostat position
    float    flow_rate;         // Coolant flow rate [0..200] L/min
} CoolingState;

/**
 * @struct BatteryState
 * @brief Battery and charging system state
 */
typedef struct {
    float    voltage;           // Battery voltage [0..20] V
    float    current;           // Battery current [-50..50] A (+ = charging)
    float    soc;               // State of charge [0..100] %
    float    health;            // Battery health [0..100] %
    bool     charging;          // Alternator charging
    int16_t  temperature;       // Battery temperature [-40..80] °C
} BatteryState;

/**
 * @struct BodyState
 * @brief Body and lighting state
 */
typedef struct {
    float    speed;             // Vehicle speed [0..300] km/h
    uint8_t  door_status;       // Door bitmask (FL|FR|RL|RR|Hood|Trunk)
    bool     headlights_low;    // Low beam ON
    bool     headlights_high;   // High beam ON
    bool     fog_lights;        // Fog lights ON
    bool     turn_left;         // Left indicator active
    bool     turn_right;        // Right indicator active
    bool     hazard;            // Hazard lights active
    bool     parking_brake;     // Parking brake engaged
    bool     seatbelt_driver;   // Driver seatbelt fastened
    float    odometer;          // Total distance [km]
} BodyState;

/**
 * @struct SteeringState
 * @brief Steering system state
 */
typedef struct {
    float    angle;             // Steering wheel angle [-720..720] deg
    float    rate;              // Steering rate [deg/s]
    bool     power_assist;      // Power steering active
    uint8_t  eps_mode;          // EPS mode (0=Comfort, 1=Normal, 2=Sport)
} SteeringState;

/**
 * @struct WheelSpeedState
 * @brief Individual wheel speed sensors
 */
typedef struct {
    float    fl;                // Front-left [km/h]
    float    fr;                // Front-right [km/h]
    float    rl;                // Rear-left [km/h]
    float    rr;                // Rear-right [km/h]
} WheelSpeedState;

/**
 * @struct FuelState
 * @brief Fuel system state
 */
typedef struct {
    float    level;             // Fuel level [0..100] %
    float    pressure;          // Fuel pressure [0..7] bar
    float    consumption_rate;  // Instant consumption [L/100km]
    float    range_km;          // Estimated range [km]
} FuelState;

/**
 * @struct VehicleState
 * @brief Complete vehicle state — the digital twin representation.
 *
 * This is the central data structure updated by CAN frame decoding.
 * All dashboard, 3D, and diagnostic modules read from this structure.
 *
 * Memory: ~200 bytes total
 */
typedef struct {
    // Subsystem states
    EngineState       engine;
    TransmissionState transmission;
    BrakeState        brakes;
    CoolingState      cooling;
    BatteryState      battery;
    BodyState         body;
    SteeringState     steering;
    WheelSpeedState   wheel_speed;
    FuelState         fuel;
    float             engine_load;      // [0..100] %
    int16_t           ambient_temp;     // °C

    // Metadata
    uint32_t last_update_ms;    // millis() of last CAN frame received
    uint32_t frame_count;       // Total frames received this session
    uint32_t session_start_ms;  // millis() at firmware start
    bool     can_active;        // true if CAN data flowing within timeout
    bool     data_valid;        // false if critical signals missing/stale
    uint8_t  stale_signals;     // Count of signals past expected update time
} VehicleState;

// ============================================================================
// VEHICLE STATE FUNCTIONS
// ============================================================================

/**
 * @brief Initialize vehicle state to safe defaults
 */
static inline void vehicleState_init(VehicleState* vs) {
    memset(vs, 0, sizeof(VehicleState));

    // Engine defaults
    vs->engine.rpm = 0;
    vs->engine.coolant_temp = 25;
    vs->engine.oil_temp = 25;
    vs->engine.oil_pressure = 0.0f;
    vs->engine.load = 0.0f;
    vs->engine.throttle_pos = 0.0f;
    vs->engine.fuel_pressure = 3.0f;
    vs->engine.engine_on = false;
    vs->engine.misfire_count = 0;
    vs->engine.runtime_seconds = 0;

    // Transmission defaults
    vs->transmission.gear = GEAR_PARK;
    vs->transmission.gear_ratio = 0.0f;
    vs->transmission.torque_lockup = false;
    vs->transmission.slip_ratio = 0.0f;

    // Brake defaults
    vs->brakes.applied = false;
    vs->brakes.pedal_position = 0.0f;
    vs->brakes.pressure = 0.0f;
    vs->brakes.abs_active = false;
    vs->brakes.esp_active = false;
    vs->brakes.pad_wear_fl = 10.0f;
    vs->brakes.pad_wear_fr = 10.0f;
    vs->brakes.pad_wear_rl = 10.0f;
    vs->brakes.pad_wear_rr = 10.0f;

    // Cooling defaults
    vs->cooling.coolant_temp = 25;
    vs->cooling.fan_active = false;
    vs->cooling.fan_speed = 0;
    vs->cooling.thermostat_open = false;
    vs->cooling.flow_rate = 0.0f;

    // Battery defaults
    vs->battery.voltage = 12.6f;
    vs->battery.current = 0.0f;
    vs->battery.soc = 100.0f;
    vs->battery.health = 100.0f;
    vs->battery.charging = true;
    vs->battery.temperature = 25;

    // Body defaults
    vs->body.speed = 0.0f;
    vs->body.door_status = 0x00;
    vs->body.headlights_low = false;
    vs->body.headlights_high = false;
    vs->body.fog_lights = false;
    vs->body.turn_left = false;
    vs->body.turn_right = false;
    vs->body.hazard = false;
    vs->body.parking_brake = true;
    vs->body.seatbelt_driver = false;
    vs->body.odometer = 0.0f;

    // Steering defaults
    vs->steering.angle = 0.0f;
    vs->steering.rate = 0.0f;
    vs->steering.power_assist = true;
    vs->steering.eps_mode = 1;

    // Wheel speed defaults
    vs->wheel_speed.fl = 0.0f;
    vs->wheel_speed.fr = 0.0f;
    vs->wheel_speed.rl = 0.0f;
    vs->wheel_speed.rr = 0.0f;

    // Fuel defaults
    vs->fuel.level = 100.0f;
    vs->fuel.pressure = 3.0f;
    vs->fuel.consumption_rate = 0.0f;
    vs->fuel.range_km = 600.0f;

    // Other
    vs->engine_load = 0.0f;
    vs->ambient_temp = 25;

    // Metadata
    vs->last_update_ms = 0;
    vs->frame_count = 0;
    vs->session_start_ms = millis();
    vs->can_active = false;
    vs->data_valid = true;
    vs->stale_signals = 0;
}

/**
 * @brief Convert gear enum to display string
 */
static inline const char* gearToChar(uint8_t gear) {
    switch (gear) {
        case GEAR_PARK:     return "P";
        case GEAR_REVERSE:  return "R";
        case GEAR_NEUTRAL:  return "N";
        case GEAR_DRIVE:    return "D";
        case GEAR_SPORT:    return "S";
        case GEAR_LOW:      return "L";
        case GEAR_MANUAL:   return "M";
        default:            return "?";
    }
}

/**
 * @brief Convert door bitmask to readable string
 */
static inline const char* doorsToString(uint8_t doors, char* buf, size_t bufSize) {
    if (doors == 0x00) {
        strncpy(buf, "Closed", bufSize);
        return buf;
    }

    buf[0] = '\0';
    if (doors & (1 << DOOR_FL_BIT))   strncat(buf, "FL ", bufSize - strlen(buf) - 1);
    if (doors & (1 << DOOR_FR_BIT))   strncat(buf, "FR ", bufSize - strlen(buf) - 1);
    if (doors & (1 << DOOR_RL_BIT))   strncat(buf, "RL ", bufSize - strlen(buf) - 1);
    if (doors & (1 << DOOR_RR_BIT))   strncat(buf, "RR ", bufSize - strlen(buf) - 1);
    if (doors & (1 << DOOR_HOOD_BIT)) strncat(buf, "Hood ", bufSize - strlen(buf) - 1);
    if (doors & (1 << DOOR_TRUNK_BIT))strncat(buf, "Trunk", bufSize - strlen(buf) - 1);
    return buf;
}

/**
 * @brief Check if vehicle state has gone stale (no CAN data)
 * @param vs Vehicle state pointer
 * @param timeout_ms Maximum allowed silence in ms
 * @return true if state is stale
 */
static inline bool vehicleState_isStale(const VehicleState* vs, uint32_t timeout_ms) {
    if (!vs->can_active) return true;
    return (millis() - vs->last_update_ms) > timeout_ms;
}

// ============================================================================
// BIT EXTRACTION HELPERS
// ============================================================================

/**
 * @brief Extract an unsigned integer from CAN data bytes
 * @param data      Pointer to CAN payload
 * @param start_bit Starting bit position (0 = LSB of byte 0)
 * @param bit_len   Number of bits to extract (1-32)
 * @return Extracted unsigned value
 */
static inline uint32_t extractUnsigned(const uint8_t* data, uint8_t start_bit, uint8_t bit_len) {
    uint32_t result = 0;
    uint8_t bits_remaining = bit_len;
    uint8_t current_bit = start_bit;

    while (bits_remaining > 0) {
        uint8_t byte_index = current_bit / 8;
        uint8_t bit_in_byte = current_bit % 8;

        uint8_t bits_to_read = 8 - bit_in_byte;
        if (bits_to_read > bits_remaining) bits_to_read = bits_remaining;

        uint8_t mask = ((1 << bits_to_read) - 1) << bit_in_byte;
        uint8_t extracted = (data[byte_index] & mask) >> bit_in_byte;

        result |= ((uint32_t)extracted << (bit_len - bits_remaining));

        bits_remaining -= bits_to_read;
        current_bit += bits_to_read;
    }

    return result;
}

/**
 * @brief Extract a signed integer from CAN data (two's complement)
 * @param data      Pointer to CAN payload
 * @param start_bit Starting bit position
 * @param bit_len   Number of bits (1-32)
 * @return Extracted signed value
 */
static inline int32_t extractSigned(const uint8_t* data, uint8_t start_bit, uint8_t bit_len) {
    uint32_t raw = extractUnsigned(data, start_bit, bit_len);

    // Check sign bit
    if (raw & (1UL << (bit_len - 1))) {
        // Negative: extend sign
        raw |= ~((1UL << bit_len) - 1);
    }

    return (int32_t)raw;
}

/**
 * @brief Convert raw value to physical value using factor and offset
 * @param raw    Raw integer value from CAN
 * @param factor Multiplication factor
 * @param offset Addition offset
 * @return Physical value in engineering units
 */
static inline float rawToPhysical(int32_t raw, float factor, float offset) {
    return ((float)raw * factor) + offset;
}

/**
 * @brief Clamp a value to [min, max] range
 */
static inline float clampFloat(float value, float min_val, float max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

#endif // CAN_FRAME_H