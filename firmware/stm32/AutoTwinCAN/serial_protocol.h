/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    serial_protocol.h
 * @brief   Serial communication protocol (Header - declarations only)
 * @version 2.0.0
 * ============================================================================
 */

#ifndef SERIAL_PROTOCOL_H
#define SERIAL_PROTOCOL_H

#include <Arduino.h>
#include <stdarg.h>
#include "config.h"
#include "can_frame.h"

// ============================================================================
// PROTOCOL CONSTANTS
// ============================================================================

#define PROTO_FRAME_START       "---AUTOTWIN---"
#define PROTO_FRAME_END         "---END---"
#define PROTO_DEBUG_PREFIX      "[DEBUG] "
#define PROTO_INFO_PREFIX       "[INFO] "
#define PROTO_WARN_PREFIX       "[WARN] "
#define PROTO_ERROR_PREFIX      "[ERROR] "
#define PROTO_FATAL_PREFIX      "[FATAL] "

#define PROTO_VERSION_MAJOR     2
#define PROTO_VERSION_MINOR     0
#define PROTO_MAX_LINE_LEN      128

// Verbosity levels
#define PROTO_VERBOSE_SILENT    0   // No output
#define PROTO_VERBOSE_ERRORS    1   // Errors only
#define PROTO_VERBOSE_NORMAL    2   // Errors + Info + State
#define PROTO_VERBOSE_DEBUG     3   // + Debug messages
#define PROTO_VERBOSE_CAN_TRACE 4   // + Every CAN frame

// ============================================================================
// SERIAL PROTOCOL CLASS
// ============================================================================

class SerialProtocol {
public:
    // Constructor
    SerialProtocol();

    // Initialization
    void begin();
    void begin(uint32_t baud_rate);
    void setEnabled(bool enabled);
    bool isEnabled() const;
    void setVerboseLevel(uint8_t level);

    // Boot
    void printBootBanner();

    // Vehicle State Output
    void printVehicleState(const VehicleState* vs, bool force = false);
    void printCompactState(const VehicleState* vs);

    // Diagnostics
    void printDiagnostics(const DiagnosticCounters* counters, const VehicleState* vs);
    void periodicDiagnostics(const DiagnosticCounters* counters,
                             const VehicleState* vs,
                             uint32_t interval_ms = 30000);

    // Heartbeat
    void heartbeat(uint32_t interval_ms = 5000);
    void heartbeatWithState(const VehicleState* vs, uint32_t interval_ms = 5000);

    // Logging
    void printDebug(const char* msg);
    void printDebug(const char* msg, int32_t value);
    void printDebug(const char* msg, float value, uint8_t decimals = 2);
    void printInfo(const char* msg);
    void printWarning(const char* msg);
    void printError(const char* msg);
    void printFatal(const char* msg);
    void printf(const char* format, ...);

    // CAN-specific logging
    void printCanFrame(const RawCANFrame* frame);
    void printCanError(uint8_t eflg);
    void printCanBusStatus(uint8_t tec, uint8_t rec);

    // Status changes
    void printStatusChange(const char* component, const char* old_state, const char* new_state);
    void printModeChange(uint8_t old_mode, uint8_t new_mode);

    // Recovery
    void printRecoveryAttempt(const char* component, uint8_t attempt, uint8_t max_attempts);
    void printRecoveryResult(const char* component, bool success);

    // Scenario
    void printScenarioStart(const char* scenario_name);
    void printScenarioStop(const char* scenario_name, uint32_t duration_s);

    // Raw CAN logging
    void printRawCanLog(const RawCANFrame* frame);

    // Protocol info
    void printProtocolInfo();

    // Utility
    static uint32_t freeRAM();
    void flush();
    uint32_t getBytesSent() const;
    uint32_t getFramesSent() const;
    uint32_t getSequence() const;
    void resetCounters();

private:
    uint32_t _lastPrintMs;
    uint32_t _lastHeartbeatMs;
    uint32_t _lastDiagMs;
    uint32_t _frameSeq;
    bool     _enabled;
    uint8_t  _verboseLevel;
    uint32_t _bytesSent;
    uint32_t _framesSent;
    bool     _lastCanActive;
};

#endif // SERIAL_PROTOCOL_H