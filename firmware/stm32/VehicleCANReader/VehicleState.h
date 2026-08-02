/**
 * @file VehicleState.h
 * @brief Vehicle state data structure - single source of truth for all signals
 * 
 * Design: This struct is the canonical vehicle state. Future phases will
 * serialize this to JSON/MQTT/Database without modification.
 */

#ifndef VEHICLE_STATE_H
#define VEHICLE_STATE_H

#include <Arduino.h>
#include "CANConfig.h"

/**
 * @struct VehicleState
 * @brief Complete vehicle state representation
 */
struct VehicleState {
    float    speed;         // km/h [0..300]
    uint16_t rpm;           // rpm [0..8000]
    float    fuel;          // % [0..100]
    int8_t   temp;          // °C [-40..215]
    float    battery;       // V [0..20]
    float    steering;      // deg [-720..720]
    bool     brake;         // true = applied
    float    accelerator;   // % [0..100]
    uint8_t  gear;          // GearPosition enum
    uint8_t  doors;         // bitmask: FL|FR|RL|RR

    // Metadata
    uint32_t lastUpdateMs;  // millis() of last CAN frame received
    bool     isValid;       // true if all signals received within timeout

    void init();
    void updateTimestamp();
    bool checkTimeout(uint32_t currentMs) const;
    const char* gearToString() const;
    const char* doorToString() const;
};

#endif // VEHICLE_STATE_H