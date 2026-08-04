/**
 * @file CANParser.cpp
 * @brief CAN frame decoding implementation
 * 
 * Byte Order: Little-Endian (Intel format) as per DBC specification
 * Signed values use two's complement
 */

#include "CANParser.h"

CANParser::CANParser() {}

bool CANParser::parseFrame(uint32_t id, const uint8_t* data, uint8_t dlc, VehicleState& state) {
    switch (id) {
        case CAN_ID_SPEED:       decodeSpeed(data, state);       break;
        case CAN_ID_RPM:         decodeRPM(data, state);         break;
        case CAN_ID_FUEL:        decodeFuel(data, state);        break;
        case CAN_ID_TEMP:        decodeTemp(data, state);        break;
        case CAN_ID_BATTERY:     decodeBattery(data, state);     break;
        case CAN_ID_STEERING:    decodeSteering(data, state);    break;
        case CAN_ID_BRAKE:       decodeBrake(data, state);       break;
        case CAN_ID_ACCELERATOR: decodeAccelerator(data, state); break;
        case CAN_ID_GEAR:        decodeGear(data, state);        break;
        case CAN_ID_DOOR:        decodeDoor(data, state);        break;
        default:
            return false;  // Unknown CAN ID
    }
    state.updateTimestamp();
    return true;
}

void CANParser::decodeSpeed(const uint8_t* data, VehicleState& state) {
    // 16-bit unsigned, little-endian, resolution 0.01 km/h
    uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
    state.speed = raw * SPEED_RESOLUTION + SPEED_OFFSET;
}

void CANParser::decodeRPM(const uint8_t* data, VehicleState& state) {
    // 16-bit unsigned, little-endian, resolution 1 rpm
    uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
    state.rpm = (uint16_t)(raw * RPM_RESOLUTION + RPM_OFFSET);
}

void CANParser::decodeFuel(const uint8_t* data, VehicleState& state) {
    // 8-bit unsigned, resolution 0.5%
    uint8_t raw = data[0];
    state.fuel = raw * FUEL_RESOLUTION + FUEL_OFFSET;
}

void CANParser::decodeTemp(const uint8_t* data, VehicleState& state) {
    // 8-bit unsigned with -40 offset
    uint8_t raw = data[0];
    state.temp = (int16_t)(raw * TEMP_RESOLUTION + TEMP_OFFSET);
}

void CANParser::decodeBattery(const uint8_t* data, VehicleState& state) {
    // 16-bit unsigned, little-endian, resolution 0.01V
    uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
    state.battery = raw * BATTERY_RESOLUTION + BATTERY_OFFSET;
}

void CANParser::decodeSteering(const uint8_t* data, VehicleState& state) {
    // 16-bit SIGNED, little-endian, resolution 0.1 deg
    int16_t raw = (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
    state.steering = raw * STEERING_RESOLUTION + STEERING_OFFSET;
}

void CANParser::decodeBrake(const uint8_t* data, VehicleState& state) {
    // Single bit: bit 0 of byte 0
    state.brake = (data[0] & 0x01) != 0;
}

void CANParser::decodeAccelerator(const uint8_t* data, VehicleState& state) {
    // 8-bit unsigned, resolution 0.5%
    uint8_t raw = data[0];
    state.accelerator = raw * ACCEL_RESOLUTION + ACCEL_OFFSET;
}

void CANParser::decodeGear(const uint8_t* data, VehicleState& state) {
    // 8-bit enum value
    state.gear = data[0];
}

void CANParser::decodeDoor(const uint8_t* data, VehicleState& state) {
    // 4-bit bitmask (bits 0-3)
    state.doors = data[0] & 0x0F;
}