/**
 * @file CANParser.h
 * @brief CAN frame decoder - converts raw CAN data to engineering units
 * 
 * Design Principle: Each CAN ID has its own decode function.
 * Future: Add J1939 SPN/PGN decoding, OBD-II PID decoding.
 */

#ifndef CAN_PARSER_H
#define CAN_PARSER_H

#include <Arduino.h>
#include "CANConfig.h"
#include "VehicleState.h"

/**
 * @class CANParser
 * @brief Decodes raw CAN frames into vehicle state
 */
class CANParser {
public:
    CANParser();
    
    /**
     * @brief Process a received CAN frame and update vehicle state
     * @param id    CAN arbitration ID
     * @param data  Payload bytes (up to 8)
     * @param dlc   Data length code
     * @param state Reference to vehicle state to update
     * @return true if frame was recognized and decoded
     */
    bool parseFrame(uint32_t id, const uint8_t* data, uint8_t dlc, VehicleState& state);

private:
    void decodeSpeed(const uint8_t* data, VehicleState& state);
    void decodeRPM(const uint8_t* data, VehicleState& state);
    void decodeFuel(const uint8_t* data, VehicleState& state);
    void decodeTemp(const uint8_t* data, VehicleState& state);
    void decodeBattery(const uint8_t* data, VehicleState& state);
    void decodeSteering(const uint8_t* data, VehicleState& state);
    void decodeBrake(const uint8_t* data, VehicleState& state);
    void decodeAccelerator(const uint8_t* data, VehicleState& state);
    void decodeGear(const uint8_t* data, VehicleState& state);
    void decodeDoor(const uint8_t* data, VehicleState& state);
};

#endif // CAN_PARSER_H