/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    mcp2515_driver.h
 * @brief   MCP2515 SPI-to-CAN Controller Driver (Header)
 * @version 2.0.0
 * @date    2026-01-15
 *
 * @details
 * Complete driver for Microchip MCP2515 CAN controller interfaced via SPI.
 * Provides a clean C++ class interface for:
 *   - Initialization and configuration
 *   - CAN frame transmission and reception
 *   - Acceptance filter and mask setup
 *   - Error detection and recovery
 *   - Status monitoring
 *
 * Hardware Requirements:
 *   - MCP2515 connected via SPI (Mode 0, max 10 MHz)
 *   - INT pin connected to MCU GPIO (active LOW)
 *   - CS pin controlled by MCU GPIO
 *
 * @note This driver does NOT use any external MCP2515 library.
 *       All register access is implemented directly for full control.
 *
 * @author  AutoTwin AI Development Team
 * ============================================================================
 */

#ifndef MCP2515_DRIVER_H
#define MCP2515_DRIVER_H

#include <Arduino.h>
#include <SPI.h>
#include "config.h"
#include "can_frame.h"

// ============================================================================
// MCP2515 DRIVER CLASS
// ============================================================================

/**
 * @class MCP2515Driver
 * @brief Complete driver for MCP2515 SPI CAN controller
 *
 * Usage:
 * @code
 *   MCP2515Driver can;
 *   can.begin();
 *   can.setMode(MCP2515_MODE_NORMAL);
 *
 *   RawCANFrame frame;
 *   if (can.receiveFrame(&frame)) {
 *       // Process frame
 *   }
 * @endcode
 */
class MCP2515Driver {
public:
    // ========================================================================
    // CONSTRUCTOR / DESTRUCTOR
    // ========================================================================

    /**
     * @brief Construct MCP2515 driver
     * @param cs_pin   Chip select GPIO pin
     * @param int_pin  Interrupt GPIO pin (active LOW), -1 if not used
     */
    MCP2515Driver(uint8_t cs_pin = MCP2515_SPI_CS, int8_t int_pin = MCP2515_INT);

    ~MCP2515Driver();

    // ========================================================================
    // INITIALIZATION
    // ========================================================================

    /**
     * @brief Initialize SPI and MCP2515
     * @param can_speed   CAN baud rate (default: CAN_BAUD_RATE from config)
     * @param mode        Initial operation mode
     * @return true if initialization successful
     */
    bool begin(uint32_t can_speed = CAN_BAUD_RATE, uint8_t mode = CAN_STARTUP_MODE);

    /**
     * @brief Reset MCP2515 via SPI reset command
     */
    void reset();

    /**
     * @brief Check if MCP2515 is responsive (read/write test)
     * @return true if communication verified
     */
    bool selfTest();

    // ========================================================================
    // MODE CONTROL
    // ========================================================================

    /**
     * @brief Set MCP2515 operation mode
     * @param mode One of MCP2515_MODE_NORMAL, _SLEEP, _LOOPBACK, _LISTEN, _CONFIG
     * @return true if mode change confirmed
     */
    bool setMode(uint8_t mode);

    /**
     * @brief Get current operation mode
     * @return Mode bits from CANSTAT register
     */
    uint8_t getMode();

    // ========================================================================
    // CAN FRAME RECEPTION
    // ========================================================================

    /**
     * @brief Check if CAN frame is available in RX buffers
     * @return true if RXB0 or RXB1 has a pending frame
     */
    bool frameAvailable();

    /**
     * @brief Read a CAN frame from MCP2515
     * @param frame Pointer to output frame structure
     * @return true if frame was successfully read
     */
    bool receiveFrame(RawCANFrame* frame);

    /**
     * @brief Read CAN frame and push into ring buffer
     * @param buffer Pointer to CAN frame ring buffer
     * @return true if frame was read and buffered
     */
    bool receiveToBuffer(CANFrameBuffer* buffer);

    // ========================================================================
    // CAN FRAME TRANSMISSION
    // ========================================================================

    /**
     * @brief Transmit a CAN frame
     * @param frame Pointer to frame to transmit
     * @param tx_buffer Which TX buffer to use (0, 1, or 2)
     * @return true if frame queued for transmission
     */
    bool transmitFrame(const RawCANFrame* frame, uint8_t tx_buffer = 0);

    /**
     * @brief Check if TX buffer is free
     * @param tx_buffer Buffer index (0, 1, 2)
     * @return true if buffer is available
     */
    bool txBufferFree(uint8_t tx_buffer);

    /**
     * @brief Abort all pending transmissions
     */
    void abortTransmissions();

    // ========================================================================
    // FILTER & MASK CONFIGURATION
    // ========================================================================

    /**
     * @brief Set acceptance filter
     * @param filter_num Filter number (0-5)
     * @param id         CAN ID to accept
     * @param extended   true for 29-bit extended ID
     */
    void setFilter(uint8_t filter_num, uint32_t id, bool extended = false);

    /**
     * @brief Set acceptance mask
     * @param mask_num Mask number (0 or 1)
     * @param mask     Mask value (bits to check)
     * @param extended true for 29-bit extended ID
     */
    void setMask(uint8_t mask_num, uint32_t mask, bool extended = false);

    /**
     * @brief Configure filters for Phase 1 CAN IDs (0x100-0x10F)
     */
    void configurePhase1Filters();

    /**
     * @brief Disable all filters (accept all messages)
     */
    void disableFilters();

    // ========================================================================
    // ERROR HANDLING
    // ========================================================================

    /**
     * @brief Check and process CAN bus errors
     * @return Error flag register value
     */
    uint8_t checkErrors();

    /**
     * @brief Get transmit error counter
     * @return TEC value (0-255)
     */
    uint8_t getTxErrorCount();

    /**
     * @brief Get receive error counter
     * @return REC value (0-255)
     */
    uint8_t getRxErrorCount();

    /**
     * @brief Check if CAN bus is in bus-off state
     * @return true if bus-off
     */
    bool isBusOff();

    /**
     * @brief Attempt recovery from bus-off state
     * @return true if recovery successful
     */
    bool recoverFromBusOff();

    /**
     * @brief Clear error flags
     */
    void clearErrorFlags();

    // ========================================================================
    // STATUS & DIAGNOSTICS
    // ========================================================================

    /**
     * @brief Read MCP2515 status register
     * @return Status byte (TX/RX buffer states)
     */
    uint8_t readStatus();

    /**
     * @brief Read RX status (which buffer has message, filter hit)
     * @return RX status byte
     */
    uint8_t readRxStatus();

    /**
     * @brief Get interrupt flag register
     * @return CANINTF value
     */
    uint8_t getInterruptFlags();

    /**
     * @brief Clear specific interrupt flag
     * @param flag Flag bit to clear
     */
    void clearInterruptFlag(uint8_t flag);

    /**
     * @brief Get driver statistics
     * @param frames_rx   Output: frames received
     * @param frames_tx   Output: frames transmitted
     * @param errors      Output: error count
     * @param overruns    Output: buffer overrun count
     */
    void getStatistics(uint32_t* frames_rx, uint32_t* frames_tx,
                       uint32_t* errors, uint32_t* overruns);

    // ========================================================================
    // INTERRUPT CONFIGURATION
    // ========================================================================

    /**
     * @brief Enable specific MCP2515 interrupts
     * @param mask Interrupt enable bits (MCP2515_INT_*)
     */
    void enableInterrupts(uint8_t mask);

    /**
     * @brief Disable all MCP2515 interrupts
     */
    void disableInterrupts();

    /**
     * @brief Check if INT pin is asserted (frame ready or error)
     * @return true if interrupt active (pin LOW)
     */
    bool interruptPending();

private:
    // ========================================================================
    // LOW-LEVEL SPI ACCESS
    // ========================================================================

    void select();
    void deselect();
    uint8_t readRegister(uint8_t reg);
    void readRegisters(uint8_t reg, uint8_t* buf, uint8_t len);
    void writeRegister(uint8_t reg, uint8_t value);
    void writeRegisters(uint8_t reg, const uint8_t* buf, uint8_t len);
    void modifyRegister(uint8_t reg, uint8_t mask, uint8_t value);

    // ========================================================================
    // INTERNAL HELPERS
    // ========================================================================

    bool setBitTiming(uint32_t can_speed);
    void readFrameFromBuffer(uint8_t buffer_base, RawCANFrame* frame);
    uint32_t calculateBitTiming(uint32_t can_speed, uint8_t* cnf1, uint8_t* cnf2, uint8_t* cnf3);

    // ========================================================================
    // MEMBER VARIABLES
    // ========================================================================

    uint8_t  _cs_pin;           // Chip select pin
    int8_t   _int_pin;          // Interrupt pin (-1 if unused)
    uint32_t _can_speed;        // Configured CAN baud rate
    uint8_t  _current_mode;     // Current operation mode
    bool     _initialized;      // Initialization flag

    // Statistics
    uint32_t _frames_rx;        // Total frames received
    uint32_t _frames_tx;        // Total frames transmitted
    uint32_t _error_count;      // Total errors detected
    uint32_t _overrun_count;    // Total buffer overruns
    uint32_t _bus_off_count;    // Total bus-off events
};

#endif // MCP2515_DRIVER_H