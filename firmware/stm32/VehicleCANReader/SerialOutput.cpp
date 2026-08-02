/**
 * @file SerialOutput.cpp
 * @brief Serial output formatting implementation
 * 
 * Output format (parsed by Python backend):
 * ---FRAME---
 * Speed=58.00
 * RPM=2450
 * Fuel=82.0
 * Temp=91
 * Battery=12.50
 * Steering=-12.0
 * Brake=0
 * Accel=35.0
 * Gear=D
 * Door=Closed
 * ---END---
 */

#include "SerialOutput.h"
#include "CANConfig.h"

SerialOutput::SerialOutput() : _lastPrintMs(0) {}

void SerialOutput::printState(const VehicleState& state) {
    uint32_t now = millis();
    
    // Rate-limit serial output to avoid flooding
    if (now - _lastPrintMs < SERIAL_PRINT_INTERVAL_MS) {
        return;
    }
    _lastPrintMs = now;
    
    SERIAL_PORT.println("---FRAME---");
    
    SERIAL_PORT.print("Speed=");
    SERIAL_PORT.println(state.speed, 2);
    
    SERIAL_PORT.print("RPM=");
    SERIAL_PORT.println(state.rpm);
    
    SERIAL_PORT.print("Fuel=");
    SERIAL_PORT.println(state.fuel, 1);
    
    SERIAL_PORT.print("Temp=");
    SERIAL_PORT.println(state.temp);
    
    SERIAL_PORT.print("Battery=");
    SERIAL_PORT.println(state.battery, 2);
    
    SERIAL_PORT.print("Steering=");
    SERIAL_PORT.println(state.steering, 1);
    
    SERIAL_PORT.print("Brake=");
    SERIAL_PORT.println(state.brake ? 1 : 0);
    
    SERIAL_PORT.print("Accel=");
    SERIAL_PORT.println(state.accelerator, 1);
    
    SERIAL_PORT.print("Gear=");
    SERIAL_PORT.println(state.gearToString());
    
    SERIAL_PORT.print("Door=");
    SERIAL_PORT.println(state.doorToString());
    
    SERIAL_PORT.println("---END---");
}

void SerialOutput::printDebug(const char* msg) {
    SERIAL_PORT.print("[DEBUG] ");
    SERIAL_PORT.println(msg);
}