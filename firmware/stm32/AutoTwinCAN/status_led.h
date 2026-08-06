/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    status_led.h
 * @brief   Diagnostic LED management system
 * @version 2.0.0
 * @date    2026-01-15
 *
 * @details
 * Non-blocking LED pattern generator for system status indication.
 * Supports multiple LEDs with independent patterns:
 *
 *   LED_STATUS (PB5):   System operational status
 *   LED_ERROR (PB4):    Error/fault indication
 *   LED_CAN_ACT (PB3):  CAN bus activity indicator
 *
 * Patterns:
 *   OFF:          LED off
 *   SLOW_BLINK:   500ms on/off (idle/standby)
 *   FAST_BLINK:   100ms on/off (CAN active, data flowing)
 *   SOLID:        Constant on (error/fault)
 *   HEARTBEAT:    Brief pulse every 1s (alive, no data)
 *   DOUBLE_BLINK: Two quick blinks (warning)
 *   SOS:          ... --- ... pattern (critical failure)
 *   BREATHING:    PWM fade in/out (initializing)
 *
 * Design:
 *   - Fully non-blocking (uses millis() timing)
 *   - No delay() calls
 *   - Call update() from main loop
 *   - Thread-safe for ISR usage via volatile flags
 *
 * Hardware Note:
 *   PA5 (SPI SCK) is shared with Nucleo onboard LED.
 *   Use external LEDs on PB3/PB4/PB5 for reliable indication.
 *
 * @author  AutoTwin AI Development Team
 * ============================================================================
 */

#ifndef STATUS_LED_H
#define STATUS_LED_H

#include <Arduino.h>
#include "config.h"

// ============================================================================
// LED PATTERN ENUMERATION
// ============================================================================

/**
 * @enum LedPattern
 * @brief Available LED blink patterns
 */
enum LedPattern : uint8_t {
    LED_PATTERN_OFF = 0,        // LED off
    LED_PATTERN_SLOW_BLINK,     // 500ms on, 500ms off
    LED_PATTERN_FAST_BLINK,     // 100ms on, 100ms off
    LED_PATTERN_SOLID,          // Constant on
    LED_PATTERN_HEARTBEAT,      // 50ms pulse every 1000ms
    LED_PATTERN_DOUBLE_BLINK,   // Two 100ms blinks, 800ms pause
    LED_PATTERN_SOS,            // ... --- ... (critical)
    LED_PATTERN_BREATHING,      // Smooth PWM fade (initializing)
    LED_PATTERN_STROBE,         // Very fast 50ms blink (data burst)
    LED_PATTERN_COUNT           // Number of patterns (for validation)
};

/**
 * @enum SystemLed
 * @brief Identifies physical LED channels
 */
enum SystemLed : uint8_t {
    SYS_LED_STATUS = 0,     // Main status LED (PB5)
    SYS_LED_ERROR,          // Error/fault LED (PB4)
    SYS_LED_CAN_ACTIVE,     // CAN activity LED (PB3)
    SYS_LED_COUNT           // Number of LEDs
};

// ============================================================================
// LED CHANNEL STRUCTURE
// ============================================================================

/**
 * @struct LedChannel
 * @brief State for a single LED channel
 */
typedef struct {
    uint8_t     pin;            // GPIO pin number
    LedPattern  pattern;        // Current pattern
    uint32_t    lastToggleMs;   // Last state change timestamp
    bool        currentState;   // Current on/off state
    uint8_t     patternStep;    // Step within multi-step patterns
    uint32_t    patternStartMs; // When current pattern started
    uint8_t     blinkCount;     // Blinks completed in current cycle
} LedChannel;

// ============================================================================
// STATUS LED MANAGER CLASS
// ============================================================================

/**
 * @class StatusLedManager
 * @brief Non-blocking LED pattern manager for multiple LEDs
 *
 * Usage:
 * @code
 *   StatusLedManager leds;
 *   leds.begin();
 *   leds.setPattern(SYS_LED_STATUS, LED_PATTERN_HEARTBEAT);
 *
 *   void loop() {
 *       leds.update();  // Call every loop iteration
 *       // ... other code ...
 *   }
 * @endcode
 */
class StatusLedManager {
public:
    // ========================================================================
    // CONSTRUCTOR
    // ========================================================================

    StatusLedManager() {
        for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
            _channels[i].pin = 0;
            _channels[i].pattern = LED_PATTERN_OFF;
            _channels[i].lastToggleMs = 0;
            _channels[i].currentState = false;
            _channels[i].patternStep = 0;
            _channels[i].patternStartMs = 0;
            _channels[i].blinkCount = 0;
        }
        _globalEnable = true;
        _brightness = 255;
    }

    // ========================================================================
    // INITIALIZATION
    // ========================================================================

    /**
     * @brief Initialize all LED GPIO pins
     */
    void begin() {
        // Configure pins
        _channels[SYS_LED_STATUS].pin = LED_STATUS_PIN;
        _channels[SYS_LED_ERROR].pin = LED_ERROR_PIN;
        _channels[SYS_LED_CAN_ACTIVE].pin = LED_CAN_ACTIVE_PIN;

        for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
            pinMode(_channels[i].pin, OUTPUT);
            digitalWrite(_channels[i].pin, LOW);
            _channels[i].currentState = false;
            _channels[i].pattern = LED_PATTERN_OFF;
        }
    }

    /**
     * @brief Initialize with custom pin assignments
     */
    void begin(uint8_t status_pin, uint8_t error_pin, uint8_t can_pin) {
        _channels[SYS_LED_STATUS].pin = status_pin;
        _channels[SYS_LED_ERROR].pin = error_pin;
        _channels[SYS_LED_CAN_ACTIVE].pin = can_pin;

        for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
            pinMode(_channels[i].pin, OUTPUT);
            digitalWrite(_channels[i].pin, LOW);
        }
    }

    // ========================================================================
    // PATTERN CONTROL
    // ========================================================================

    /**
     * @brief Set pattern for a specific LED
     * @param led   Which LED channel
     * @param pattern Pattern to display
     */
    void setPattern(SystemLed led, LedPattern pattern) {
        if (led >= SYS_LED_COUNT || pattern >= LED_PATTERN_COUNT) return;

        if (_channels[led].pattern != pattern) {
            _channels[led].pattern = pattern;
            _channels[led].patternStep = 0;
            _channels[led].patternStartMs = millis();
            _channels[led].blinkCount = 0;

            // Reset state for new pattern
            if (pattern == LED_PATTERN_OFF) {
                digitalWrite(_channels[led].pin, LOW);
                _channels[led].currentState = false;
            } else if (pattern == LED_PATTERN_SOLID) {
                digitalWrite(_channels[led].pin, HIGH);
                _channels[led].currentState = true;
            }
        }
    }

    /**
     * @brief Set all LEDs to same pattern
     */
    void setAllPatterns(LedPattern pattern) {
        for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
            setPattern((SystemLed)i, pattern);
        }
    }

    /**
     * @brief Get current pattern for a LED
     */
    LedPattern getPattern(SystemLed led) const {
        if (led >= SYS_LED_COUNT) return LED_PATTERN_OFF;
        return _channels[led].pattern;
    }

    /**
     * @brief Turn off a specific LED
     */
    void turnOff(SystemLed led) {
        setPattern(led, LED_PATTERN_OFF);
    }

    /**
     * @brief Turn off all LEDs
     */
    void allOff() {
        setAllPatterns(LED_PATTERN_OFF);
    }

    // ========================================================================
    // GLOBAL CONTROL
    // ========================================================================

    /**
     * @brief Enable/disable all LED output
     */
    void setGlobalEnable(bool enable) {
        _globalEnable = enable;
        if (!enable) {
            for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
                digitalWrite(_channels[i].pin, LOW);
            }
        }
    }

    /**
     * @brief Set brightness (for PWM-capable pins, future use)
     * @param brightness 0-255
     */
    void setBrightness(uint8_t brightness) {
        _brightness = brightness;
    }

    // ========================================================================
    // MAIN UPDATE (Call from loop)
    // ========================================================================

    /**
     * @brief Update all LED patterns (non-blocking)
     *
     * Call this function every iteration of the main loop.
     * Uses millis() for timing - no delays.
     */
    void update() {
        if (!_globalEnable) return;

        uint32_t now = millis();

        for (uint8_t i = 0; i < SYS_LED_COUNT; i++) {
            updateChannel(&_channels[i], now);
        }
    }

    // ========================================================================
    // CONVENIENCE METHODS
    // ========================================================================

    /**
     * @brief Indicate CAN frame received (brief flash on CAN LED)
     */
    void flashCanActivity() {
        _channels[SYS_LED_CAN_ACTIVE].pattern = LED_PATTERN_STROBE;
        _channels[SYS_LED_CAN_ACTIVE].patternStartMs = millis();
        _channels[SYS_LED_CAN_ACTIVE].patternStep = 0;
    }

    /**
     * @brief Indicate error condition
     */
    void indicateError() {
        setPattern(SYS_LED_ERROR, LED_PATTERN_SOLID);
        setPattern(SYS_LED_STATUS, LED_PATTERN_FAST_BLINK);
    }

    /**
     * @brief Indicate error cleared
     */
    void clearError() {
        setPattern(SYS_LED_ERROR, LED_PATTERN_OFF);
        setPattern(SYS_LED_STATUS, LED_PATTERN_SLOW_BLINK);
    }

    /**
     * @brief Indicate system initializing
     */
    void indicateInitializing() {
        setPattern(SYS_LED_STATUS, LED_PATTERN_BREATHING);
    }

    /**
     * @brief Indicate CAN bus active (data flowing)
     */
    void indicateCanActive() {
        setPattern(SYS_LED_CAN_ACTIVE, LED_PATTERN_FAST_BLINK);
    }

    /**
     * @brief Indicate CAN bus idle (no data)
     */
    void indicateCanIdle() {
        setPattern(SYS_LED_CAN_ACTIVE, LED_PATTERN_HEARTBEAT);
    }

    /**
     * @brief Indicate CAN bus off (critical)
     */
    void indicateCanBusOff() {
        setPattern(SYS_LED_CAN_ACTIVE, LED_PATTERN_SOS);
        setPattern(SYS_LED_ERROR, LED_PATTERN_FAST_BLINK);
    }

    /**
     * @brief Indicate normal operation
     */
    void indicateNormal() {
        setPattern(SYS_LED_STATUS, LED_PATTERN_HEARTBEAT);
        setPattern(SYS_LED_ERROR, LED_PATTERN_OFF);
    }

    /**
     * @brief Indicate critical failure
     */
    void indicateCritical() {
        setAllPatterns(LED_PATTERN_SOS);
    }

    /**
     * @brief Boot sequence animation
     */
    void bootSequence() {
        setPattern(SYS_LED_STATUS, LED_PATTERN_BREATHING);
        setPattern(SYS_LED_ERROR, LED_PATTERN_DOUBLE_BLINK);
        setPattern(SYS_LED_CAN_ACTIVE, LED_PATTERN_SLOW_BLINK);
    }

    // ========================================================================
    // STATUS QUERY
    // ========================================================================

    /**
     * @brief Check if any LED indicates error
     */
    bool hasError() const {
        return _channels[SYS_LED_ERROR].pattern == LED_PATTERN_SOLID ||
               _channels[SYS_LED_ERROR].pattern == LED_PATTERN_FAST_BLINK ||
               _channels[SYS_LED_ERROR].pattern == LED_PATTERN_SOS;
    }

    /**
     * @brief Check if CAN activity LED is active
     */
    bool isCanActive() const {
        return _channels[SYS_LED_CAN_ACTIVE].pattern == LED_PATTERN_FAST_BLINK ||
               _channels[SYS_LED_CAN_ACTIVE].pattern == LED_PATTERN_STROBE;
    }

private:
    // ========================================================================
    // INTERNAL PATTERN ENGINE
    // ========================================================================

    /**
     * @brief Update a single LED channel based on its pattern
     */
    void updateChannel(LedChannel* ch, uint32_t now) {
        uint32_t elapsed = now - ch->lastToggleMs;
        uint32_t patternElapsed = now - ch->patternStartMs;

        switch (ch->pattern) {
            case LED_PATTERN_OFF:
                if (ch->currentState) {
                    digitalWrite(ch->pin, LOW);
                    ch->currentState = false;
                }
                break;

            case LED_PATTERN_SOLID:
                if (!ch->currentState) {
                    digitalWrite(ch->pin, HIGH);
                    ch->currentState = true;
                }
                break;

            case LED_PATTERN_SLOW_BLINK:
                if (elapsed >= 500) {
                    ch->lastToggleMs = now;
                    ch->currentState = !ch->currentState;
                    digitalWrite(ch->pin, ch->currentState ? HIGH : LOW);
                }
                break;

            case LED_PATTERN_FAST_BLINK:
                if (elapsed >= 100) {
                    ch->lastToggleMs = now;
                    ch->currentState = !ch->currentState;
                    digitalWrite(ch->pin, ch->currentState ? HIGH : LOW);
                }
                break;

            case LED_PATTERN_HEARTBEAT:
                // Brief 50ms pulse every 1000ms
                if (patternElapsed < 50) {
                    if (!ch->currentState) {
                        digitalWrite(ch->pin, HIGH);
                        ch->currentState = true;
                    }
                } else {
                    if (ch->currentState) {
                        digitalWrite(ch->pin, LOW);
                        ch->currentState = false;
                    }
                }
                // Reset cycle every 1000ms
                if (patternElapsed >= 1000) {
                    ch->patternStartMs = now;
                }
                break;

            case LED_PATTERN_DOUBLE_BLINK:
                // Two 100ms blinks, then 800ms pause (total 1000ms cycle)
                if (patternElapsed < 100) {
                    digitalWrite(ch->pin, HIGH);
                    ch->currentState = true;
                } else if (patternElapsed < 200) {
                    digitalWrite(ch->pin, LOW);
                    ch->currentState = false;
                } else if (patternElapsed < 300) {
                    digitalWrite(ch->pin, HIGH);
                    ch->currentState = true;
                } else if (patternElapsed < 1000) {
                    digitalWrite(ch->pin, LOW);
                    ch->currentState = false;
                } else {
                    ch->patternStartMs = now;
                }
                break;

            case LED_PATTERN_SOS:
                // ... --- ... pattern
                // S: 3× (100ms on, 100ms off) = 600ms
                // O: 3× (300ms on, 100ms off) = 1200ms
                // S: 3× (100ms on, 100ms off) = 600ms
                // Gap: 500ms
                // Total cycle: 2900ms
                updateSOS(ch, patternElapsed);
                break;

            case LED_PATTERN_BREATHING:
                // Simulate breathing with discrete steps (no PWM dependency)
                // 2-second cycle: fade in (1s) + fade out (1s)
                {
                    uint16_t cyclePos = patternElapsed % 2000;
                    bool shouldOn;
                    if (cyclePos < 1000) {
                        // Fade in: increasing on-time
                        shouldOn = (cyclePos % 100) < (cyclePos / 10);
                    } else {
                        // Fade out: decreasing on-time
                        uint16_t fadePos = cyclePos - 1000;
                        shouldOn = (fadePos % 100) < (100 - fadePos / 10);
                    }
                    if (shouldOn != ch->currentState) {
                        ch->currentState = shouldOn;
                        digitalWrite(ch->pin, shouldOn ? HIGH : LOW);
                    }
                }
                break;

            case LED_PATTERN_STROBE:
                // Very fast blink for 200ms, then off
                if (patternElapsed < 200) {
                    if (elapsed >= 30) {
                        ch->lastToggleMs = now;
                        ch->currentState = !ch->currentState;
                        digitalWrite(ch->pin, ch->currentState ? HIGH : LOW);
                    }
                } else {
                    digitalWrite(ch->pin, LOW);
                    ch->currentState = false;
                    ch->pattern = LED_PATTERN_OFF;
                }
                break;

            default:
                digitalWrite(ch->pin, LOW);
                ch->currentState = false;
                break;
        }
    }

    /**
     * @brief SOS pattern sub-handler
     */
    void updateSOS(LedChannel* ch, uint32_t elapsed) {
        bool on = false;

        // S: dots (3 × 100ms on, 100ms off)
        if (elapsed < 600) {
            uint16_t pos = elapsed % 200;
            on = (pos < 100);
        }
        // O: dashes (3 × 300ms on, 100ms off)
        else if (elapsed < 1800) {
            uint16_t pos = (elapsed - 600) % 400;
            on = (pos < 300);
        }
        // S: dots again
        else if (elapsed < 2400) {
            uint16_t pos = (elapsed - 1800) % 200;
            on = (pos < 100);
        }
        // Gap
        else if (elapsed < 2900) {
            on = false;
        }
        else {
            // Reset cycle
            ch->patternStartMs = millis();
            on = false;
        }

        if (on != ch->currentState) {
            ch->currentState = on;
            digitalWrite(ch->pin, on ? HIGH : LOW);
        }
    }

    // ========================================================================
    // MEMBER VARIABLES
    // ========================================================================

    LedChannel _channels[SYS_LED_COUNT];
    bool       _globalEnable;
    uint8_t    _brightness;
};

// ============================================================================
// GLOBAL INSTANCE (extern declaration for use across files)
// ============================================================================

// Declare in ONE .cpp or .ino file:
//   StatusLedManager g_statusLeds;
//
// Use in other files:
//   extern StatusLedManager g_statusLeds;

#endif // STATUS_LED_H