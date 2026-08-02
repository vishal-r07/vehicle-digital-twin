/**
 * @file SerialOutput.h
 * @brief Structured serial output for Python backend consumption
 * 
 * Protocol: Key=Value pairs separated by newlines, frame delimited by START/END
 * Future: Can be replaced with JSON or binary protocol
 */

#ifndef SERIAL_OUTPUT_H
#define SERIAL_OUTPUT_H

#include <Arduino.h>
#include "VehicleState.h"

/**
 * @class SerialOutput
 * @brief Formats and transmits vehicle state over serial
 */
class SerialOutput {
public:
    SerialOutput();
    
    /**
     * @brief Print complete vehicle state in structured format
     * @param state Current vehicle state
     */
    void printState(const VehicleState& state);
    
    /**
     * @brief Print a single diagnostic message
     */
    void printDebug(const char* msg);
    
private:
    uint32_t _lastPrintMs;
};

#endif // SERIAL_OUTPUT_H