/**
 * ============================================================================
 * AutoTwin AI - Main Firmware (Modular Version)
 * ============================================================================
 * @file    AutoTwinCAN.ino
 * @brief   Main entry point using modular MCP2515 driver and serial protocol
 * ============================================================================
 */

#include <Arduino.h>
#include <SPI.h>
#include "config.h"
#include "can_frame.h"
#include "mcp2515_driver.h"
#include "serial_protocol.h"

// ============================================================================
// GLOBAL INSTANCES
// ============================================================================

static MCP2515Driver    g_canDriver(MCP2515_SPI_CS, MCP2515_INT);
static SerialProtocol   g_serial;
static VehicleState     g_vehicle;
static DiagnosticCounters g_counters;
static CANFrameBuffer   g_frameBuffer;

// Timing
static uint32_t g_startTimeMs = 0;
static LedState g_ledState = LED_HEARTBEAT;
static uint32_t g_lastLedMs = 0;

// ============================================================================
// CAN FRAME DECODER
// ============================================================================

void decodeCanFrame(const RawCANFrame* frame) {
    const uint8_t* data = frame->data;
    uint8_t dlc = frame->dlc;

    switch (frame->id) {
        case CAN_ID_SPEED:
            if (dlc >= 2) {
                uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
                g_vehicle.body.speed = clampFloat(raw * SPEED_RESOLUTION, 0, SPEED_MAX);
            }
            break;

        case CAN_ID_RPM:
            if (dlc >= 2) {
                uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
                g_vehicle.engine.rpm = (uint16_t)min((float)(raw * RPM_RESOLUTION), RPM_MAX);
            }
            break;

        case CAN_ID_FUEL:
            if (dlc >= 1) {
                g_vehicle.fuel.level = clampFloat(data[0] * FUEL_RESOLUTION, 0, FUEL_MAX);
            }
            break;

        case CAN_ID_TEMP:
            if (dlc >= 1) {
                g_vehicle.engine.coolant_temp = (int16_t)(data[0] * TEMP_RESOLUTION + TEMP_OFFSET);
                g_vehicle.cooling.coolant_temp = g_vehicle.engine.coolant_temp;
            }
            break;

        case CAN_ID_BATTERY:
            if (dlc >= 2) {
                uint16_t raw = (uint16_t)data[0] | ((uint16_t)data[1] << 8);
                g_vehicle.battery.voltage = clampFloat(raw * BATTERY_RESOLUTION, 0, BATTERY_MAX);
            }
            break;

        case CAN_ID_STEERING:
            if (dlc >= 2) {
                int16_t raw = (int16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8));
                g_vehicle.steering.angle = clampFloat(raw * STEERING_RESOLUTION,
                                                       -STEERING_MAX, STEERING_MAX);
            }
            break;

        case CAN_ID_BRAKE:
            if (dlc >= 1) {
                g_vehicle.brakes.applied = (data[0] & 0x01) != 0;
            }
            break;

        case CAN_ID_ACCELERATOR:
            if (dlc >= 1) {
                g_vehicle.engine.throttle_pos = clampFloat(data[0] * ACCEL_RESOLUTION, 0, ACCEL_MAX);
            }
            break;

        case CAN_ID_GEAR:
            if (dlc >= 1) {
                g_vehicle.transmission.gear = data[0];
            }
            break;

        case CAN_ID_DOOR:
            if (dlc >= 1) {
                g_vehicle.body.door_status = data[0] & 0x3F;
            }
            break;

        case CAN_ID_INDICATORS:
            if (dlc >= 1) {
                g_vehicle.body.turn_left = (data[0] & 0x01) != 0;
                g_vehicle.body.turn_right = (data[0] & 0x02) != 0;
                g_vehicle.body.hazard = (data[0] & 0x04) != 0;
            }
            break;

        case CAN_ID_HEADLIGHTS:
            if (dlc >= 1) {
                g_vehicle.body.headlights_low = (data[0] & 0x01) != 0;
                g_vehicle.body.headlights_high = (data[0] & 0x02) != 0;
                g_vehicle.body.fog_lights = (data[0] & 0x04) != 0;
            }
            break;

        case CAN_ID_WHEEL_SPEED:
            if (dlc >= 8) {
                g_vehicle.wheel_speed.fl = ((uint16_t)data[0] | ((uint16_t)data[1] << 8)) * WHEEL_SPEED_RESOLUTION;
                g_vehicle.wheel_speed.fr = ((uint16_t)data[2] | ((uint16_t)data[3] << 8)) * WHEEL_SPEED_RESOLUTION;
                g_vehicle.wheel_speed.rl = ((uint16_t)data[4] | ((uint16_t)data[5] << 8)) * WHEEL_SPEED_RESOLUTION;
                g_vehicle.wheel_speed.rr = ((uint16_t)data[6] | ((uint16_t)data[7] << 8)) * WHEEL_SPEED_RESOLUTION;
            }
            break;

        case CAN_ID_ENGINE_LOAD:
            if (dlc >= 1) {
                g_vehicle.engine_load = clampFloat(data[0] * ENGINE_LOAD_RESOLUTION, 0, ENGINE_LOAD_MAX);
                g_vehicle.engine.load = g_vehicle.engine_load;
            }
            break;

        case CAN_ID_AMBIENT_TEMP:
            if (dlc >= 1) {
                g_vehicle.ambient_temp = (int16_t)(data[0] * AMBIENT_TEMP_RESOLUTION + AMBIENT_TEMP_OFFSET);
            }
            break;

        case CAN_ID_ODOMETER:
            if (dlc >= 4) {
                uint32_t raw = (uint32_t)data[0] | ((uint32_t)data[1] << 8) |
                              ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
                g_vehicle.body.odometer = raw * ODOMETER_RESOLUTION;
            }
            break;

        default:
            g_counters.frames_unknown++;
            return;
    }

    // Update metadata
    g_vehicle.last_update_ms = millis();
    g_vehicle.frame_count++;
    g_vehicle.can_active = true;
    g_counters.frames_decoded++;
}

// ============================================================================
// INTERRUPT HANDLER
// ============================================================================

#if FEATURE_CAN_INTERRUPT
static volatile bool g_canIntFlag = false;

void canISR() {
    g_canIntFlag = true;
}
#endif

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // Initialize serial protocol
    g_serial.begin();
    g_serial.printBootBanner();

    g_startTimeMs = millis();

    // Initialize vehicle state
    vehicleState_init(&g_vehicle);
    g_vehicle.session_start_ms = g_startTimeMs;

    // Initialize frame buffer
    canBuffer_init(&g_frameBuffer);

    // Zero counters
    memset(&g_counters, 0, sizeof(DiagnosticCounters));

    // Configure LED pins
    pinMode(LED_STATUS_PIN, OUTPUT);
    pinMode(LED_ERROR_PIN, OUTPUT);
    pinMode(LED_CAN_ACTIVE_PIN, OUTPUT);
    digitalWrite(LED_STATUS_PIN, LOW);
    digitalWrite(LED_ERROR_PIN, LOW);
    digitalWrite(LED_CAN_ACTIVE_PIN, LOW);

    // Initialize MCP2515 CAN driver
    g_serial.printInfo("Initializing MCP2515 CAN controller...");

    if (!g_canDriver.begin(CAN_BAUD_RATE, CAN_STARTUP_MODE)) {
        g_serial.printFatal("MCP2515 initialization FAILED!");
        g_serial.printError("Check SPI wiring: MOSI→PA7, MISO→PA6, SCK→PA5, CS→PA4");
        digitalWrite(LED_ERROR_PIN, HIGH);

        // Retry 3 times
        for (int i = 0; i < 3; i++) {
            delay(1000);
            g_serial.printf("[INIT] Retry %d/3...\n", i + 1);
            if (g_canDriver.begin(CAN_BAUD_RATE, CAN_STARTUP_MODE)) {
                g_serial.printInfo("MCP2515 initialized successfully on retry!");
                digitalWrite(LED_ERROR_PIN, LOW);
                break;
            }
        }

        if (digitalRead(LED_ERROR_PIN) == HIGH) {
            g_serial.printFatal("Cannot initialize MCP2515. System halted.");
            while (1) { delay(1000); }
        }
    }

    g_serial.printInfo("MCP2515 initialized at 500 kbps");

#if FEATURE_CAN_INTERRUPT
    attachInterrupt(digitalPinToInterrupt(MCP2515_INT), canISR, FALLING);
    g_serial.printInfo("CAN interrupt attached on PB0 (falling edge)");
#endif

    // Initial diagnostics
    g_serial.printDiagnostics(&g_counters, &g_vehicle);
    g_serial.printInfo("System operational. Awaiting CAN frames...");
    g_serial.println();

    g_ledState = LED_SLOW_BLINK;
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
    uint32_t now = millis();
    bool frameProcessed = false;

    // --- CAN Frame Reception ---
#if FEATURE_CAN_INTERRUPT
    if (g_canIntFlag) {
        g_canIntFlag = false;
#endif
        if (g_canDriver.frameAvailable()) {
            RawCANFrame frame;
            if (g_canDriver.receiveFrame(&frame)) {
                g_counters.frames_received++;
                decodeCanFrame(&frame);
                frameProcessed = true;
            }
        }
#if FEATURE_CAN_INTERRUPT
    }
#endif

    // --- CAN Timeout Check ---
    if (g_vehicle.can_active && (now - g_vehicle.last_update_ms > CAN_TIMEOUT_MS)) {
        g_vehicle.can_active = false;
        g_serial.printWarning("CAN timeout - no data received");
        g_ledState = LED_HEARTBEAT;
        digitalWrite(LED_CAN_ACTIVE_PIN, LOW);
    }

    // --- LED Management ---
    if (frameProcessed) {
        g_ledState = LED_FAST_BLINK;
        digitalWrite(LED_CAN_ACTIVE_PIN, HIGH);
    }

    static uint32_t lastLedToggle = 0;
    uint32_t blinkRate = (g_ledState == LED_FAST_BLINK) ? LED_FAST_BLINK_MS : LED_BLINK_MS;
    if (now - lastLedToggle >= blinkRate) {
        lastLedToggle = now;
        if (g_ledState != LED_SOLID) {
            digitalWrite(LED_STATUS_PIN, !digitalRead(LED_STATUS_PIN));
        }
    }

    // --- Periodic Error Check ---
    static uint32_t lastErrCheck = 0;
    if (now - lastErrCheck >= 1000) {
        lastErrCheck = now;
        uint8_t eflg = g_canDriver.checkErrors();
        if (eflg & MCP2515_EFLG_TXBO) {
            g_serial.printError("CAN Bus-Off detected! Attempting recovery...");
            if (g_canDriver.recoverFromBusOff()) {
                g_serial.printInfo("Bus-Off recovery successful");
            }
        }
    }

    // --- Serial Output ---
    g_serial.printVehicleState(&g_vehicle);
    g_serial.periodicDiagnostics(&g_counters, &g_vehicle, 30000);

#if FEATURE_HEARTBEAT
    g_serial.heartbeat(5000);
#endif

    // --- Main Loop Delay ---
    delayMicroseconds(MAIN_LOOP_DELAY_US);
}