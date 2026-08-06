/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    serial_protocol.cpp
 * @brief   Serial communication protocol implementation
 * @version 2.0.0
 * @date    2026-01-15
 *
 * @details
 * Implements the structured serial protocol for STM32 → Python backend.
 * Handles frame formatting, rate limiting, diagnostic output, and
 * multi-level logging.
 *
 * Protocol Specification:
 *   - Frame-delimited with "---AUTOTWIN---" / "---END---"
 *   - Key=Value pairs (one per line)
 *   - 20 Hz output rate (50ms interval)
 *   - Sequence numbers for gap detection
 *   - Heartbeat for connection monitoring
 *
 * Python Backend Parser Expectations:
 *   1. Read lines until "---AUTOTWIN---" found
 *   2. Parse "Key=Value" pairs into dict
 *   3. Stop at "---END---"
 *   4. Validate sequence number continuity
 *   5. Handle missing/malformed lines gracefully
 *
 * @author  AutoTwin AI Development Team
 * ============================================================================
 */

#include "serial_protocol.h"
#include <stdio.h>
#include <string.h>

// ============================================================================
// STATIC / MODULE-LEVEL VARIABLES
// ============================================================================

// Output buffer for formatted lines (avoids repeated heap allocation)
static char s_lineBuffer[PROTO_MAX_LINE_LEN];

// Sequence tracking for gap detection
static uint32_t s_lastSeq = 0;
static uint32_t s_gapCount = 0;

// ============================================================================
// CONSTRUCTOR / DESTRUCTOR
// ============================================================================

SerialProtocol::SerialProtocol()
    : _lastPrintMs(0)
    , _lastHeartbeatMs(0)
    , _lastDiagMs(0)
    , _frameSeq(0)
    , _enabled(true)
    , _verboseLevel(PROTO_VERBOSE_NORMAL)
    , _bytesSent(0)
    , _framesSent(0)
{
}

// ============================================================================
// INITIALIZATION
// ============================================================================

void SerialProtocol::begin() {
    SERIAL_PORT.begin(SERIAL_BAUD_RATE);

    // Wait for USB CDC enumeration (up to 3 seconds)
    uint32_t waitStart = millis();
    while (!SERIAL_PORT && (millis() - waitStart) < 3000) {
        delay(10);
    }

    // Additional stabilization delay for USB CDC
    delay(100);

    _bytesSent = 0;
    _framesSent = 0;
}

void SerialProtocol::begin(uint32_t baud_rate) {
    SERIAL_PORT.begin(baud_rate);

    uint32_t waitStart = millis();
    while (!SERIAL_PORT && (millis() - waitStart) < 3000) {
        delay(10);
    }
    delay(100);
}

void SerialProtocol::setEnabled(bool enabled) {
    _enabled = enabled;
}

bool SerialProtocol::isEnabled() const {
    return _enabled;
}

void SerialProtocol::setVerboseLevel(uint8_t level) {
    _verboseLevel = level;
}

// ============================================================================
// BOOT BANNER
// ============================================================================

void SerialProtocol::printBootBanner() {
    if (!_enabled) return;

    SERIAL_PORT.println();
    SERIAL_PORT.println(F("+====================================================+"));
    SERIAL_PORT.println(F("|                                                    |"));
    SERIAL_PORT.println(F("|     AutoTwin AI - CAN Interface Firmware           |"));
    SERIAL_PORT.println(F("|     Real-Time Vehicle Digital Twin Platform        |"));
    SERIAL_PORT.println(F("|                                                    |"));
    SERIAL_PORT.print(F("|     Version:  "));
    SERIAL_PORT.print(FW_VERSION_MAJOR);
    SERIAL_PORT.print('.');
    SERIAL_PORT.print(FW_VERSION_MINOR);
    SERIAL_PORT.print('.');
    SERIAL_PORT.print(FW_VERSION_PATCH);
    SERIAL_PORT.println(F("                          |"));
    SERIAL_PORT.print(F("|     Platform: "));
    SERIAL_PORT.print(FW_PLATFORM);
    SERIAL_PORT.println(F("                     |"));
    SERIAL_PORT.print(F("|     CAN:      "));
    SERIAL_PORT.print(CAN_BAUD_RATE / 1000);
    SERIAL_PORT.println(F(" kbps                        |"));
    SERIAL_PORT.print(F("|     Crystal:  "));
    SERIAL_PORT.print(MCP2515_CRYSTAL_HZ / 1000000UL);
    SERIAL_PORT.println(F(" MHz                          |"));
    SERIAL_PORT.print(F("|     Serial:   "));
    SERIAL_PORT.print(SERIAL_BAUD_RATE);
    SERIAL_PORT.println(F(" baud                   |"));
    SERIAL_PORT.print(F("|     Protocol: v"));
    SERIAL_PORT.print(PROTO_VERSION_MAJOR);
    SERIAL_PORT.print('.');
    SERIAL_PORT.print(PROTO_VERSION_MINOR);
    SERIAL_PORT.println(F("                             |"));
    SERIAL_PORT.print(F("|     Build:    "));
    SERIAL_PORT.print(FW_BUILD_DATE);
    SERIAL_PORT.print(' ');
    SERIAL_PORT.print(FW_BUILD_TIME);
    SERIAL_PORT.println(F("   |"));
    SERIAL_PORT.println(F("|                                                    |"));
    SERIAL_PORT.println(F("+====================================================+"));
    SERIAL_PORT.println();

    _bytesSent += 600;  // Approximate
}

// ============================================================================
// VEHICLE STATE OUTPUT (Main Protocol Frame)
// ============================================================================

void SerialProtocol::printVehicleState(const VehicleState* vs, bool force) {
    if (!_enabled) return;
    if (vs == nullptr) return;

    uint32_t now = millis();

    // Rate limiting (unless forced)
    if (!force && (now - _lastPrintMs < SERIAL_PRINT_INTERVAL_MS)) {
        return;
    }
    _lastPrintMs = now;
    _frameSeq++;

    // === FRAME START ===
    SERIAL_PORT.println(F(PROTO_FRAME_START));

    // === ENGINE SIGNALS ===
    SERIAL_PORT.print(F("Speed="));
    SERIAL_PORT.println(vs->body.speed, 2);

    SERIAL_PORT.print(F("RPM="));
    SERIAL_PORT.println(vs->engine.rpm);

    SERIAL_PORT.print(F("Fuel="));
    SERIAL_PORT.println(vs->fuel.level, 1);

    SERIAL_PORT.print(F("Temp="));
    SERIAL_PORT.println(vs->engine.coolant_temp);

    SERIAL_PORT.print(F("Battery="));
    SERIAL_PORT.println(vs->battery.voltage, 2);

    // === CHASSIS SIGNALS ===
    SERIAL_PORT.print(F("Steering="));
    SERIAL_PORT.println(vs->steering.angle, 1);

    SERIAL_PORT.print(F("Brake="));
    SERIAL_PORT.println(vs->brakes.applied ? 1 : 0);

    SERIAL_PORT.print(F("Accel="));
    SERIAL_PORT.println(vs->engine.throttle_pos, 1);

    // === TRANSMISSION ===
    SERIAL_PORT.print(F("Gear="));
    SERIAL_PORT.println(gearToChar(vs->transmission.gear));

    // === BODY / DOORS ===
    char doorBuf[32];
    doorsToString(vs->body.door_status, doorBuf, sizeof(doorBuf));
    SERIAL_PORT.print(F("Door="));
    SERIAL_PORT.println(doorBuf);

    // === LIGHTING ===
    uint8_t indicatorVal = (vs->body.turn_left ? 1 : 0) |
                           (vs->body.turn_right ? 2 : 0) |
                           (vs->body.hazard ? 4 : 0);
    SERIAL_PORT.print(F("Indicator="));
    SERIAL_PORT.println(indicatorVal);

    uint8_t headlightVal = (vs->body.headlights_low ? 1 : 0) |
                           (vs->body.headlights_high ? 2 : 0) |
                           (vs->body.fog_lights ? 4 : 0);
    SERIAL_PORT.print(F("Headlight="));
    SERIAL_PORT.println(headlightVal);

    // === ADDITIONAL ENGINE DATA ===
    SERIAL_PORT.print(F("EngineLoad="));
    SERIAL_PORT.println(vs->engine_load, 1);

    SERIAL_PORT.print(F("AmbientTemp="));
    SERIAL_PORT.println(vs->ambient_temp);

    SERIAL_PORT.print(F("Odometer="));
    SERIAL_PORT.println(vs->body.odometer, 1);

    // === WHEEL SPEEDS ===
    SERIAL_PORT.print(F("WheelFL="));
    SERIAL_PORT.println(vs->wheel_speed.fl, 2);

    SERIAL_PORT.print(F("WheelFR="));
    SERIAL_PORT.println(vs->wheel_speed.fr, 2);

    SERIAL_PORT.print(F("WheelRL="));
    SERIAL_PORT.println(vs->wheel_speed.rl, 2);

    SERIAL_PORT.print(F("WheelRR="));
    SERIAL_PORT.println(vs->wheel_speed.rr, 2);

    // === BRAKE DETAILS ===
    SERIAL_PORT.print(F("BrakePressure="));
    SERIAL_PORT.println(vs->brakes.pressure, 1);

    SERIAL_PORT.print(F("ABS="));
    SERIAL_PORT.println(vs->brakes.abs_active ? 1 : 0);

    // === METADATA ===
    SERIAL_PORT.print(F("FrameCount="));
    SERIAL_PORT.println(vs->frame_count);

    SERIAL_PORT.print(F("CANActive="));
    SERIAL_PORT.println(vs->can_active ? 1 : 0);

    SERIAL_PORT.print(F("Uptime="));
    SERIAL_PORT.println((millis() - vs->session_start_ms) / 1000);

    SERIAL_PORT.print(F("Seq="));
    SERIAL_PORT.println(_frameSeq);

    // === FRAME END ===
    SERIAL_PORT.println(F(PROTO_FRAME_END));

    _framesSent++;
    _bytesSent += 350;  // Approximate frame size
}

// ============================================================================
// COMPACT STATE OUTPUT (for high-frequency updates)
// ============================================================================

void SerialProtocol::printCompactState(const VehicleState* vs) {
    if (!_enabled) return;
    if (vs == nullptr) return;

    // Single-line compact format for high-speed logging
    SERIAL_PORT.printf("CS|%d|%d|%.1f|%d|%.2f|%.1f|%d|%.1f|%s|%d|%lu\n",
        (int)vs->body.speed,
        vs->engine.rpm,
        vs->fuel.level,
        vs->engine.coolant_temp,
        vs->battery.voltage,
        vs->steering.angle,
        vs->brakes.applied ? 1 : 0,
        vs->engine.throttle_pos,
        gearToChar(vs->transmission.gear),
        vs->body.door_status,
        vs->frame_count
    );
}

// ============================================================================
// DIAGNOSTIC OUTPUT
// ============================================================================

void SerialProtocol::printDiagnostics(const DiagnosticCounters* counters,
                                       const VehicleState* vs) {
    if (!_enabled) return;

    SERIAL_PORT.println(F("[DIAG] ============ SYSTEM DIAGNOSTICS ============"));
    SERIAL_PORT.print(F("[DIAG] Frames Received:   "));
    SERIAL_PORT.println(counters->frames_received);
    SERIAL_PORT.print(F("[DIAG] Frames Decoded:    "));
    SERIAL_PORT.println(counters->frames_decoded);
    SERIAL_PORT.print(F("[DIAG] Unknown IDs:       "));
    SERIAL_PORT.println(counters->frames_unknown);
    SERIAL_PORT.print(F("[DIAG] Decode Errors:     "));
    SERIAL_PORT.println(counters->frames_error);
    SERIAL_PORT.print(F("[DIAG] CAN Bus Errors:    "));
    SERIAL_PORT.println(counters->can_errors);
    SERIAL_PORT.print(F("[DIAG] CAN Overruns:      "));
    SERIAL_PORT.println(counters->can_overruns);
    SERIAL_PORT.print(F("[DIAG] Bus-Off Events:    "));
    SERIAL_PORT.println(counters->can_bus_off);
    SERIAL_PORT.print(F("[DIAG] SPI Errors:        "));
    SERIAL_PORT.println(counters->spi_errors);
    SERIAL_PORT.print(F("[DIAG] Serial Bytes TX:   "));
    SERIAL_PORT.println(_bytesSent);
    SERIAL_PORT.print(F("[DIAG] Serial Frames TX:  "));
    SERIAL_PORT.println(_framesSent);
    SERIAL_PORT.print(F("[DIAG] Frame Buffer Used: "));
    SERIAL_PORT.print(vs->frame_count);
    SERIAL_PORT.println(F(" total"));
    SERIAL_PORT.print(F("[DIAG] Uptime:            "));
    SERIAL_PORT.print((millis() - vs->session_start_ms) / 1000);
    SERIAL_PORT.println(F(" seconds"));
    SERIAL_PORT.print(F("[DIAG] Free RAM:          "));
    SERIAL_PORT.print(freeRAM());
    SERIAL_PORT.println(F(" bytes"));
    SERIAL_PORT.println(F("[DIAG] ============================================="));
}

void SerialProtocol::periodicDiagnostics(const DiagnosticCounters* counters,
                                          const VehicleState* vs,
                                          uint32_t interval_ms) {
    uint32_t now = millis();
    if (now - _lastDiagMs >= interval_ms) {
        _lastDiagMs = now;
        printDiagnostics(counters, vs);
    }
}

// ============================================================================
// HEARTBEAT
// ============================================================================

void SerialProtocol::heartbeat(uint32_t interval_ms) {
    if (!_enabled) return;

    uint32_t now = millis();
    if (now - _lastHeartbeatMs >= interval_ms) {
        _lastHeartbeatMs = now;
        SERIAL_PORT.printf("[HB] seq=%lu uptime=%lu can=%d\n",
                          _frameSeq,
                          millis() / 1000,
                          _lastCanActive ? 1 : 0);
    }
}

void SerialProtocol::heartbeatWithState(const VehicleState* vs, uint32_t interval_ms) {
    if (!_enabled) return;

    uint32_t now = millis();
    if (now - _lastHeartbeatMs >= interval_ms) {
        _lastHeartbeatMs = now;
        _lastCanActive = vs->can_active;
        SERIAL_PORT.printf("[HB] seq=%lu up=%lus can=%d spd=%.0f rpm=%d\n",
                          _frameSeq,
                          (millis() - vs->session_start_ms) / 1000,
                          vs->can_active ? 1 : 0,
                          vs->body.speed,
                          vs->engine.rpm);
    }
}

// ============================================================================
// LOGGING FUNCTIONS
// ============================================================================

void SerialProtocol::printDebug(const char* msg) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_DEBUG) return;
    SERIAL_PORT.print(F(PROTO_DEBUG_PREFIX));
    SERIAL_PORT.println(msg);
    _bytesSent += strlen(msg) + 10;
}

void SerialProtocol::printDebug(const char* msg, int32_t value) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_DEBUG) return;
    SERIAL_PORT.print(F(PROTO_DEBUG_PREFIX));
    SERIAL_PORT.print(msg);
    SERIAL_PORT.print(F(" = "));
    SERIAL_PORT.println(value);
    _bytesSent += strlen(msg) + 20;
}

void SerialProtocol::printDebug(const char* msg, float value, uint8_t decimals) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_DEBUG) return;
    SERIAL_PORT.print(F(PROTO_DEBUG_PREFIX));
    SERIAL_PORT.print(msg);
    SERIAL_PORT.print(F(" = "));
    SERIAL_PORT.println(value, decimals);
    _bytesSent += strlen(msg) + 20;
}

void SerialProtocol::printInfo(const char* msg) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_NORMAL) return;
    SERIAL_PORT.print(F(PROTO_INFO_PREFIX));
    SERIAL_PORT.println(msg);
    _bytesSent += strlen(msg) + 10;
}

void SerialProtocol::printWarning(const char* msg) {
    if (!_enabled) return;
    SERIAL_PORT.print(F(PROTO_WARN_PREFIX));
    SERIAL_PORT.println(msg);
    _bytesSent += strlen(msg) + 10;
}

void SerialProtocol::printError(const char* msg) {
    if (!_enabled) return;
    SERIAL_PORT.print(F(PROTO_ERROR_PREFIX));
    SERIAL_PORT.println(msg);
    _bytesSent += strlen(msg) + 10;
}

void SerialProtocol::printFatal(const char* msg) {
    // Fatal messages always print regardless of enabled state
    SERIAL_PORT.print(F(PROTO_FATAL_PREFIX));
    SERIAL_PORT.println(msg);
}

void SerialProtocol::printf(const char* format, ...) {
    if (!_enabled) return;

    va_list args;
    va_start(args, format);
    vsnprintf(s_lineBuffer, sizeof(s_lineBuffer), format, args);
    va_end(args);

    SERIAL_PORT.print(s_lineBuffer);
    _bytesSent += strlen(s_lineBuffer);
}

// ============================================================================
// CAN-SPECIFIC LOGGING
// ============================================================================

void SerialProtocol::printCanFrame(const RawCANFrame* frame) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_CAN_TRACE) return;

    SERIAL_PORT.print(F("[CAN] ID=0x"));
    if (frame->is_extended) {
        SERIAL_PORT.print(frame->id, HEX);
    } else {
        // Print 3-digit hex for standard IDs
        if (frame->id < 0x100) SERIAL_PORT.print('0');
        if (frame->id < 0x10) SERIAL_PORT.print('0');
        SERIAL_PORT.print(frame->id, HEX);
    }
    SERIAL_PORT.print(F(" DLC="));
    SERIAL_PORT.print(frame->dlc);
    SERIAL_PORT.print(F(" Data=["));
    for (uint8_t i = 0; i < frame->dlc && i < 8; i++) {
        if (frame->data[i] < 0x10) SERIAL_PORT.print('0');
        SERIAL_PORT.print(frame->data[i], HEX);
        if (i < frame->dlc - 1) SERIAL_PORT.print(' ');
    }
    SERIAL_PORT.println(F("]"));
}

void SerialProtocol::printCanError(uint8_t eflg) {
    if (!_enabled) return;

    SERIAL_PORT.print(F(PROTO_ERROR_PREFIX));
    SERIAL_PORT.print(F("CAN Error Flags: 0x"));
    if (eflg < 0x10) SERIAL_PORT.print('0');
    SERIAL_PORT.print(eflg, HEX);
    SERIAL_PORT.print(F(" ["));

    bool hasError = false;
    if (eflg & MCP2515_EFLG_EWARN)  { SERIAL_PORT.print(F("EWARN ")); hasError = true; }
    if (eflg & MCP2515_EFLG_RXWAR)  { SERIAL_PORT.print(F("RXWAR ")); hasError = true; }
    if (eflg & MCP2515_EFLG_TXWAR)  { SERIAL_PORT.print(F("TXWAR ")); hasError = true; }
    if (eflg & MCP2515_EFLG_RXEP)   { SERIAL_PORT.print(F("RX_PASSIVE ")); hasError = true; }
    if (eflg & MCP2515_EFLG_TXEP)   { SERIAL_PORT.print(F("TX_PASSIVE ")); hasError = true; }
    if (eflg & MCP2515_EFLG_TXBO)   { SERIAL_PORT.print(F("BUS_OFF ")); hasError = true; }
    if (eflg & MCP2515_EFLG_RX0OVR) { SERIAL_PORT.print(F("RX0_OVERFLOW ")); hasError = true; }
    if (eflg & MCP2515_EFLG_RX1OVR) { SERIAL_PORT.print(F("RX1_OVERFLOW ")); hasError = true; }

    if (!hasError) SERIAL_PORT.print(F("NONE"));
    SERIAL_PORT.println(F("]"));
}

void SerialProtocol::printCanBusStatus(uint8_t tec, uint8_t rec) {
    if (!_enabled || _verboseLevel < PROTO_VERBOSE_DEBUG) return;

    SERIAL_PORT.printf("[CAN] Bus Status: TEC=%d REC=%d State=", tec, rec);

    if (tec >= 256 || rec >= 256) {
        SERIAL_PORT.println(F("BUS_OFF"));
    } else if (tec > 127 || rec > 127) {
        SERIAL_PORT.println(F("ERROR_PASSIVE"));
    } else if (tec > 95 || rec > 95) {
        SERIAL_PORT.println(F("ERROR_WARNING"));
    } else {
        SERIAL_PORT.println(F("ACTIVE"));
    }
}

// ============================================================================
// STATUS CHANGE LOGGING
// ============================================================================

void SerialProtocol::printStatusChange(const char* component,
                                        const char* old_state,
                                        const char* new_state) {
    if (!_enabled) return;
    SERIAL_PORT.printf("[STATUS] %s: %s -> %s\n", component, old_state, new_state);
}

void SerialProtocol::printModeChange(uint8_t old_mode, uint8_t new_mode) {
    if (!_enabled) return;

    const char* modeNames[] = {"NORMAL", "SLEEP", "LOOPBACK", "LISTEN", "CONFIG"};
    uint8_t oldIdx = (old_mode >> 5) & 0x07;
    uint8_t newIdx = (new_mode >> 5) & 0x07;

    if (oldIdx > 4) oldIdx = 4;
    if (newIdx > 4) newIdx = 4;

    SERIAL_PORT.printf("[MODE] MCP2515: %s -> %s\n", modeNames[oldIdx], modeNames[newIdx]);
}

// ============================================================================
// ERROR RECOVERY LOGGING
// ============================================================================

void SerialProtocol::printRecoveryAttempt(const char* component, uint8_t attempt, uint8_t max_attempts) {
    if (!_enabled) return;
    SERIAL_PORT.printf("[RECOVERY] %s: Attempt %d/%d\n", component, attempt, max_attempts);
}

void SerialProtocol::printRecoveryResult(const char* component, bool success) {
    if (!_enabled) return;
    SERIAL_PORT.printf("[RECOVERY] %s: %s\n", component, success ? "SUCCESS" : "FAILED");
}

// ============================================================================
// SCENARIO / REPLAY NOTIFICATIONS
// ============================================================================

void SerialProtocol::printScenarioStart(const char* scenario_name) {
    if (!_enabled) return;
    SERIAL_PORT.printf("[SCENARIO] Started: %s\n", scenario_name);
}

void SerialProtocol::printScenarioStop(const char* scenario_name, uint32_t duration_s) {
    if (!_enabled) return;
    SERIAL_PORT.printf("[SCENARIO] Stopped: %s (duration: %lus)\n", scenario_name, duration_s);
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

uint32_t SerialProtocol::freeRAM() {
    // STM32F103 has 20KB SRAM
    // _end is the end of used RAM (from linker)
    // _estack is the top of stack (from linker)
    extern char _end;
    extern char _estack;
    return (uint32_t)&_estack - (uint32_t)&_end;
}

void SerialProtocol::flush() {
    SERIAL_PORT.flush();
}

uint32_t SerialProtocol::getBytesSent() const {
    return _bytesSent;
}

uint32_t SerialProtocol::getFramesSent() const {
    return _framesSent;
}

uint32_t SerialProtocol::getSequence() const {
    return _frameSeq;
}

void SerialProtocol::resetCounters() {
    _bytesSent = 0;
    _framesSent = 0;
    _frameSeq = 0;
}

// ============================================================================
// RAW DATA OUTPUT (for CAN log recording)
// ============================================================================

void SerialProtocol::printRawCanLog(const RawCANFrame* frame) {
    if (!_enabled) return;

    // Binary-efficient format for logging:
    // timestamp,id,dlc,data_hex
    SERIAL_PORT.print(micros());
    SERIAL_PORT.print(',');
    SERIAL_PORT.print(frame->id, HEX);
    SERIAL_PORT.print(',');
    SERIAL_PORT.print(frame->dlc);
    SERIAL_PORT.print(',');
    for (uint8_t i = 0; i < frame->dlc; i++) {
        if (frame->data[i] < 0x10) SERIAL_PORT.print('0');
        SERIAL_PORT.print(frame->data[i], HEX);
    }
    SERIAL_PORT.println();
}

// ============================================================================
// PROTOCOL VERSION HANDSHAKE
// ============================================================================

void SerialProtocol::printProtocolInfo() {
    if (!_enabled) return;

    SERIAL_PORT.println(F("[PROTO] === Protocol Information ==="));
    SERIAL_PORT.printf("[PROTO] Version: %d.%d\n", PROTO_VERSION_MAJOR, PROTO_VERSION_MINOR);
    SERIAL_PORT.printf("[PROTO] Frame Start: %s\n", PROTO_FRAME_START);
    SERIAL_PORT.printf("[PROTO] Frame End: %s\n", PROTO_FRAME_END);
    SERIAL_PORT.printf("[PROTO] Output Rate: %d Hz\n", 1000 / SERIAL_PRINT_INTERVAL_MS);
    SERIAL_PORT.printf("[PROTO] Baud Rate: %lu\n", SERIAL_BAUD_RATE);
    SERIAL_PORT.printf("[PROTO] Signals: 24\n");
    SERIAL_PORT.println(F("[PROTO] ================================"));
}