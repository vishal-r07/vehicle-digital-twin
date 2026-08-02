/**
 * @file VehicleState.cpp
 * @brief Vehicle state management implementation
 */

#include "VehicleState.h"

void VehicleState::init() {
    speed       = 0.0f;
    rpm         = 0;
    fuel        = 100.0f;
    temp        = 25;
    battery     = 12.6f;
    steering    = 0.0f;
    brake       = false;
    accelerator = 0.0f;
    gear        = GEAR_P;
    doors       = 0x00;
    lastUpdateMs = 0;
    isValid     = false;
}

void VehicleState::updateTimestamp() {
    lastUpdateMs = millis();
    isValid = true;
}

bool VehicleState::checkTimeout(uint32_t currentMs) const {
    return (currentMs - lastUpdateMs) > CAN_TIMEOUT_MS;
}

const char* VehicleState::gearToString() const {
    switch (gear) {
        case GEAR_P: return "P";
        case GEAR_R: return "R";
        case GEAR_N: return "N";
        case GEAR_D: return "D";
        case GEAR_S: return "S";
        case GEAR_L: return "L";
        case GEAR_M: return "M";
        default:     return "?";
    }
}

const char* VehicleState::doorToString() const {
    if (doors == 0x00) return "Closed";
    if (doors == 0x0F) return "All Open";
    
    // Return specific door info
    static char doorStr[32];
    doorStr[0] = '\0';
    if (doors & (1 << DOOR_FL_BIT)) strcat(doorStr, "FL ");
    if (doors & (1 << DOOR_FR_BIT)) strcat(doorStr, "FR ");
    if (doors & (1 << DOOR_RL_BIT)) strcat(doorStr, "RL ");
    if (doors & (1 << DOOR_RR_BIT)) strcat(doorStr, "RR ");
    return doorStr;
}