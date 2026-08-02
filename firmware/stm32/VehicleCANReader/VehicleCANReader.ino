/**
 * @file VehicleCANReader.ino
 * @brief Main firmware for STM32F103 Nucleo - Vehicle Digital Twin Phase 1
 * 
 * Hardware:
 *   - STM32F103 Nucleo-64 (STM32F103RB)
 *   - SN65HVD230 CAN Transceiver
 *   - CAN RX: PB8, CAN TX: PB9
 *   - USB Serial: PA9 (TX), PA10 (RX) - via ST-Link
 * 
 * Function:
 *   Receives CAN frames from vehicle bus (simulated via TSMaster),
 *   decodes signals to engineering units, and outputs structured
 *   data over USB Serial for Python backend consumption.
 * 
 * Author: Vehicle Digital Twin Team
 * Phase: 1 (No AI, No Database)
 * 
 * Future Expansion Points:
 *   - Add CAN TX for bidirectional communication
 *   - Add OBD-II PID request/response
 *   - Add J1939 PGN decoding
 *   - Add CAN FD support (STM32G4/H7)
 *   - Add multiple CAN channels
 */

#include <Arduino.h>
#include "CANConfig.h"
#include "VehicleState.h"
#include "CANParser.h"
#include "SerialOutput.h"

// ============================================================
// GLOBAL INSTANCES
// ============================================================
VehicleState vehicleState;
CANParser    canParser;
SerialOutput serialOut;

// ============================================================
// CAN FILTER CONFIGURATION
// Accept only Phase 1 CAN IDs (0x100 - 0x109)
// Future: Expand filter for J1939, OBD-II ranges
// ============================================================
static const uint32_t CAN_FILTER_IDS[] = {
    CAN_ID_SPEED, CAN_ID_RPM, CAN_ID_FUEL, CAN_ID_TEMP,
    CAN_ID_BATTERY, CAN_ID_STEERING, CAN_ID_BRAKE,
    CAN_ID_ACCELERATOR, CAN_ID_GEAR, CAN_ID_DOOR
};
static const uint8_t CAN_FILTER_COUNT = sizeof(CAN_FILTER_IDS) / sizeof(CAN_FILTER_IDS[0]);

// ============================================================
// CAN INSTANCE (STM32 Arduino Core uses CAN1)
// ============================================================
// Note: STM32 Arduino Core provides HardwareCAN class
// For STM32F103, CAN1 is on PB8(RX)/PB9(TX) by default

#include <HardwareCAN.h>
HardwareCAN CanBus(CAN1);  // CAN1 peripheral

// ============================================================
// SETUP
// ============================================================
void setup() {
    // Initialize Serial for debug and data output
    SERIAL_PORT.begin(SERIAL_BAUD_RATE);
    while (!SERIAL_PORT) {
        delay(10);  // Wait for USB serial connection
    }
    
    serialOut.printDebug("Vehicle Digital Twin Phase 1 - Initializing...");
    
    // Initialize vehicle state to defaults
    vehicleState.init();
    
    // Initialize CAN peripheral
    // begin() returns 0 on success for STM32 Arduino Core
    uint32_t canStatus = CanBus.begin(CAN_SPEED_500K, CAN_MODE_NORMAL);
    
    if (canStatus != 0) {
        serialOut.printDebug("ERROR: CAN initialization failed!");
        while (1) {
            delay(1000);
        }
    }
    
    serialOut.printDebug("CAN initialized at 500 kbps");
    
    // Configure CAN acceptance filter
    // Accept frames with IDs in our Phase 1 range
    // Using mask mode: accept 0x100-0x10F range
    CanBus.filter(0, 0x100 << 21, 0x7F0 << 21);  // Filter 0: Accept 0x100-0x10F
    
    serialOut.printDebug("CAN filter configured");
    serialOut.printDebug("System ready. Awaiting CAN frames...");
    
    // LED indicator (Nucleo built-in LED on PA5)
    pinMode(LED_BUILTIN, OUTPUT);
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
    // --- CAN Reception ---
    CanMsg msg;
    
    // Non-blocking CAN receive
    if (CanBus.available() > 0) {
        CanBus.read(msg);
        
        // Parse the received frame
        bool decoded = canParser.parseFrame(
            msg.id,
            msg.data,
            msg.dlc,
            vehicleState
        );
        
        if (!decoded) {
            // Unknown CAN ID - log for debugging
            // In production, this would increment an error counter
        }
        
        // Toggle LED on valid CAN reception (visual heartbeat)
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }
    
    // --- Serial Output ---
    serialOut.printState(vehicleState);
    
    // --- Timeout Check ---
    if (vehicleState.checkTimeout(millis())) {
        // No CAN data received within timeout period
        // Future: Trigger fault state, notify backend
        static uint32_t lastWarnMs = 0;
        if (millis() - lastWarnMs > 5000) {
            serialOut.printDebug("WARNING: CAN timeout - no data received");
            lastWarnMs = millis();
        }
    }
    
    // Small delay to prevent CPU spinning (1ms loop cycle)
    delay(1);
}