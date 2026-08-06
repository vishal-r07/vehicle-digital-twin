/**
 * ============================================================================
 * AutoTwin AI - Vehicle Digital Twin Platform
 * ============================================================================
 * @file    mcp2515_driver.cpp
 * @brief   MCP2515 SPI-to-CAN Controller Driver (Implementation)
 * @version 2.0.0
 * @date    2026-01-15
 *
 * @details
 * Complete implementation of MCP2515 CAN controller driver.
 * All SPI communication follows MCP2515 datasheet timing requirements.
 *
 * SPI Protocol:
 *   - Mode 0 (CPOL=0, CPHA=0)
 *   - Max clock: 10 MHz
 *   - MSB first
 *   - CS active LOW
 *
 * @author  AutoTwin AI Development Team
 * ============================================================================
 */

#include "mcp2515_driver.h"

// ============================================================================
// CONSTRUCTOR / DESTRUCTOR
// ============================================================================

MCP2515Driver::MCP2515Driver(uint8_t cs_pin, int8_t int_pin)
    : _cs_pin(cs_pin)
    , _int_pin(int_pin)
    , _can_speed(CAN_BAUD_RATE)
    , _current_mode(MCP2515_MODE_CONFIG)
    , _initialized(false)
    , _frames_rx(0)
    , _frames_tx(0)
    , _error_count(0)
    , _overrun_count(0)
    , _bus_off_count(0)
{
}

MCP2515Driver::~MCP2515Driver() {
    // No dynamic allocation, nothing to free
}

// ============================================================================
// LOW-LEVEL SPI ACCESS (Private)
// ============================================================================

void MCP2515Driver::select() {
    digitalWrite(_cs_pin, LOW);
    // Small delay for CS setup time (tCSS = 50ns min)
    // At 72 MHz STM32, one NOP ≈ 14ns, so 4 NOPs ≈ 56ns
    NOP(); NOP(); NOP(); NOP();
}

void MCP2515Driver::deselect() {
    // CS hold time (tCSH = 50ns min)
    NOP(); NOP(); NOP(); NOP();
    digitalWrite(_cs_pin, HIGH);
}

uint8_t MCP2515Driver::readRegister(uint8_t reg) {
    select();
    SPI.transfer(MCP2515_CMD_READ);
    SPI.transfer(reg);
    uint8_t value = SPI.transfer(0x00);
    deselect();
    return value;
}

void MCP2515Driver::readRegisters(uint8_t reg, uint8_t* buf, uint8_t len) {
    select();
    SPI.transfer(MCP2515_CMD_READ);
    SPI.transfer(reg);
    for (uint8_t i = 0; i < len; i++) {
        buf[i] = SPI.transfer(0x00);
    }
    deselect();
}

void MCP2515Driver::writeRegister(uint8_t reg, uint8_t value) {
    select();
    SPI.transfer(MCP2515_CMD_WRITE);
    SPI.transfer(reg);
    SPI.transfer(value);
    deselect();
}

void MCP2515Driver::writeRegisters(uint8_t reg, const uint8_t* buf, uint8_t len) {
    select();
    SPI.transfer(MCP2515_CMD_WRITE);
    SPI.transfer(reg);
    for (uint8_t i = 0; i < len; i++) {
        SPI.transfer(buf[i]);
    }
    deselect();
}

void MCP2515Driver::modifyRegister(uint8_t reg, uint8_t mask, uint8_t value) {
    select();
    SPI.transfer(MCP2515_CMD_BIT_MODIFY);
    SPI.transfer(reg);
    SPI.transfer(mask);
    SPI.transfer(value);
    deselect();
}

// ============================================================================
// INITIALIZATION
// ============================================================================

bool MCP2515Driver::begin(uint32_t can_speed, uint8_t mode) {
    _can_speed = can_speed;

    // Configure GPIO
    pinMode(_cs_pin, OUTPUT);
    digitalWrite(_cs_pin, HIGH);  // Deselect

    if (_int_pin >= 0) {
        pinMode(_int_pin, INPUT_PULLUP);  // Active LOW with pull-up
    }

    // Initialize SPI
    SPI.begin();

    // Reset MCP2515
    reset();
    delay(100);  // Wait for oscillator startup

    // Verify communication with self-test
    if (!selfTest()) {
        return false;
    }

    // Enter configuration mode (required for bit timing setup)
    if (!setMode(MCP2515_MODE_CONFIG)) {
        return false;
    }

    // Configure bit timing for desired baud rate
    if (!setBitTiming(can_speed)) {
        return false;
    }

    // Configure RX buffers
    // RXB0: Accept all valid messages, enable rollover to RXB1
    writeRegister(MCP2515_REG_RXB0CTRL, MCP2515_RXBCTRL_BUKT);
    // RXB1: Accept all valid messages
    writeRegister(MCP2515_REG_RXB1CTRL, 0x00);

    // Enable interrupts: RX0, RX1, Error
    enableInterrupts(MCP2515_INT_RX0IF | MCP2515_INT_RX1IF | MCP2515_INT_ERRIF);

    // Configure filters if enabled
#if FEATURE_CAN_FILTERING
    configurePhase1Filters();
#else
    disableFilters();
#endif

    // Set to requested operating mode
    if (!setMode(mode)) {
        return false;
    }

    _initialized = true;
    return true;
}

void MCP2515Driver::reset() {
    select();
    SPI.transfer(MCP2515_CMD_RESET);
    deselect();
    delay(10);  // MCP2515 needs ~128 clock cycles to reset
}

bool MCP2515Driver::selfTest() {
    // Write a known pattern to CNF1, read it back
    uint8_t test_value = 0xA5;
    writeRegister(MCP2515_REG_CNF1, test_value);
    uint8_t read_back = readRegister(MCP2515_REG_CNF1);

    if (read_back != test_value) {
        return false;
    }

    // Write another pattern to verify
    test_value = 0x5A;
    writeRegister(MCP2515_REG_CNF1, test_value);
    read_back = readRegister(MCP2515_REG_CNF1);

    return (read_back == test_value);
}

// ============================================================================
// MODE CONTROL
// ============================================================================

bool MCP2515Driver::setMode(uint8_t mode) {
    // Write to CANCTRL REQOP bits [7:5]
    modifyRegister(MCP2515_REG_CANCTRL, MCP2515_CANCTRL_REQOP, mode);

    // Wait for mode confirmation (timeout 10ms)
    uint32_t start = millis();
    while ((millis() - start) < 10) {
        uint8_t stat = readRegister(MCP2515_REG_CANSTAT);
        if ((stat & MCP2515_CANSTAT_OPMOD) == mode) {
            _current_mode = mode;
            return true;
        }
        delayMicroseconds(100);
    }

    return false;  // Timeout - mode change failed
}

uint8_t MCP2515Driver::getMode() {
    uint8_t stat = readRegister(MCP2515_REG_CANSTAT);
    return stat & MCP2515_CANSTAT_OPMOD;
}

// ============================================================================
// BIT TIMING CONFIGURATION
// ============================================================================

bool MCP2515Driver::setBitTiming(uint32_t can_speed) {
    uint8_t cnf1, cnf2, cnf3;

#if MCP2515_CRYSTAL_HZ == 8000000UL
    // 8 MHz crystal
    if (can_speed == 500000UL) {
        cnf1 = 0x00;  // SJW=1TQ, BRP=0 → TQ=250ns
        cnf2 = 0x90;  // BTLMODE=1, SAM=0, PHSEG1=3TQ, PRSEG=1TQ
        cnf3 = 0x02;  // PHSEG2=3TQ
        // Total: 1+1+4+3 = 9? No: 1(sync)+1(PRSEG)+4(PHSEG1)+3(PHSEG2)=9
        // Actually: PRSEG=(0+1)=1, PHSEG1=(2+1)=3, PHSEG2=(2+1)=3
        // Total: 1+1+3+3 = 8 TQ × 250ns = 2μs → 500 kbps ✓
    } else if (can_speed == 250000UL) {
        cnf1 = 0x01;  // BRP=1 → TQ=500ns
        cnf2 = 0x90;
        cnf3 = 0x02;
        // 8 TQ × 500ns = 4μs → 250 kbps
    } else if (can_speed == 1000000UL) {
        cnf1 = 0x00;  // BRP=0 → TQ=125ns
        cnf2 = 0x90;
        cnf3 = 0x02;
        // 8 TQ × 125ns = 1μs → 1 Mbps
    } else {
        return false;  // Unsupported speed for 8 MHz
    }
#elif MCP2515_CRYSTAL_HZ == 16000000UL
    // 16 MHz crystal
    if (can_speed == 500000UL) {
        cnf1 = 0x01;  // BRP=1 → TQ=250ns
        cnf2 = 0x90;
        cnf3 = 0x02;
    } else if (can_speed == 250000UL) {
        cnf1 = 0x03;  // BRP=3 → TQ=500ns
        cnf2 = 0x90;
        cnf3 = 0x02;
    } else if (can_speed == 1000000UL) {
        cnf1 = 0x00;  // BRP=0 → TQ=125ns
        cnf2 = 0x90;
        cnf3 = 0x02;
    } else {
        return false;
    }
#else
    // Use pre-defined values from config.h
    cnf1 = MCP2515_CNF1;
    cnf2 = MCP2515_CNF2;
    cnf3 = MCP2515_CNF3;
#endif

    writeRegister(MCP2515_REG_CNF1, cnf1);
    writeRegister(MCP2515_REG_CNF2, cnf2);
    writeRegister(MCP2515_REG_CNF3, cnf3);

    return true;
}

uint32_t MCP2515Driver::calculateBitTiming(uint32_t can_speed,
                                            uint8_t* cnf1, uint8_t* cnf2, uint8_t* cnf3) {
    // This function provides automatic bit timing calculation
    // for non-standard baud rates. For standard rates, use
    // the lookup table in setBitTiming().

    uint32_t f_osc = MCP2515_CRYSTAL_HZ;
    uint32_t bit_time_ns = 1000000000UL / can_speed;  // ns per bit

    // Try different BRP values (0-63)
    for (uint8_t brp = 0; brp < 64; brp++) {
        uint32_t tq_ns = (2 * (brp + 1) * 1000000UL) / (f_osc / 1000000UL);

        // Try 8 to 25 TQ per bit
        for (uint8_t total_tq = 8; total_tq <= 25; total_tq++) {
            uint32_t calculated_bit_time = tq_ns * total_tq;

            // Check if this gives us the desired baud rate (±1%)
            uint32_t diff = (calculated_bit_time > bit_time_ns) ?
                           (calculated_bit_time - bit_time_ns) :
                           (bit_time_ns - calculated_bit_time);

            if (diff <= bit_time_ns / 100) {  // Within 1%
                // Found valid timing
                // Distribute TQ: Sync(1) + PRSEG + PHSEG1 + PHSEG2
                uint8_t remaining = total_tq - 1;  // Subtract sync segment

                // Aim for sample point at 75-87.5%
                uint8_t before_sp = (remaining * 3) / 4;  // ~75% sample point
                uint8_t after_sp = remaining - before_sp;

                uint8_t prseg = 1;  // Minimum propagation segment
                uint8_t phseg1 = before_sp - prseg;
                uint8_t phseg2 = after_sp;

                if (phseg1 < 1) phseg1 = 1;
                if (phseg2 < 2) phseg2 = 2;

                // Encode registers
                *cnf1 = brp;  // BRP[5:0], SJW=00 (1TQ)
                *cnf2 = 0x80 | ((phseg1 - 1) << 3) | (prseg - 1);  // BTLMODE=1
                *cnf3 = (phseg2 - 1);

                return calculated_bit_time;
            }
        }
    }

    return 0;  // No valid timing found
}

// ============================================================================
// CAN FRAME RECEPTION
// ============================================================================

bool MCP2515Driver::frameAvailable() {
    uint8_t intf = readRegister(MCP2515_REG_CANINTF);
    return (intf & (MCP2515_INT_RX0IF | MCP2515_INT_RX1IF)) != 0;
}

bool MCP2515Driver::receiveFrame(RawCANFrame* frame) {
    uint8_t intf = readRegister(MCP2515_REG_CANINTF);

    // Check RX Buffer 0 first (higher priority)
    if (intf & MCP2515_INT_RX0IF) {
        readFrameFromBuffer(MCP2515_REG_RXB0SIDH, frame);
        clearInterruptFlag(MCP2515_INT_RX0IF);
        _frames_rx++;
        return true;
    }

    // Check RX Buffer 1
    if (intf & MCP2515_INT_RX1IF) {
        readFrameFromBuffer(MCP2515_REG_RXB1SIDH, frame);
        clearInterruptFlag(MCP2515_INT_RX1IF);
        _frames_rx++;
        return true;
    }

    return false;  // No frame available
}

bool MCP2515Driver::receiveToBuffer(CANFrameBuffer* buffer) {
    RawCANFrame frame;
    if (receiveFrame(&frame)) {
        return canBuffer_push(buffer, &frame);
    }
    return false;
}

void MCP2515Driver::readFrameFromBuffer(uint8_t buffer_base, RawCANFrame* frame) {
    // Read 13 bytes: SIDH, SIDL, EID8, EID0, DLC, Data[0..7]
    uint8_t buf[13];
    readRegisters(buffer_base, buf, 13);

    // Parse Standard ID (bits [10:0])
    uint32_t id = ((uint32_t)buf[0] << 3) | ((uint32_t)(buf[1] & 0xE0) >> 5);

    // Check for Extended ID (IDE bit in SIDL)
    frame->is_extended = (buf[1] & 0x08) != 0;

    if (frame->is_extended) {
        // 29-bit Extended ID
        id = ((uint32_t)buf[0] << 21) |
             ((uint32_t)(buf[1] & 0xE0) << 13) |
             ((uint32_t)(buf[1] & 0x03) << 16) |
             ((uint32_t)buf[2] << 8) |
             ((uint32_t)buf[3]);
    }

    frame->id = id;
    frame->is_remote = (buf[4] & 0x40) != 0;  // RTR bit
    frame->dlc = buf[4] & 0x0F;

    // Copy data payload
    for (uint8_t i = 0; i < 8; i++) {
        frame->data[i] = (i < frame->dlc) ? buf[5 + i] : 0;
    }

    frame->timestamp_us = micros();
}

// ============================================================================
// CAN FRAME TRANSMISSION
// ============================================================================

bool MCP2515Driver::transmitFrame(const RawCANFrame* frame, uint8_t tx_buffer) {
    if (tx_buffer > 2) return false;

    // Check if TX buffer is free
    if (!txBufferFree(tx_buffer)) return false;

    uint8_t regBase;
    switch (tx_buffer) {
        case 0: regBase = MCP2515_REG_TXB0SIDH; break;
        case 1: regBase = MCP2515_REG_TXB1SIDH; break;
        case 2: regBase = MCP2515_REG_TXB2CTRL; break;
        default: return false;
    }

    // Build frame bytes
    uint8_t buf[13];
    memset(buf, 0, sizeof(buf));

    if (frame->is_extended) {
        // Extended ID (29-bit)
        buf[0] = (frame->id >> 21) & 0xFF;                     // EID[28:21] → SIDH
        buf[1] = ((frame->id >> 13) & 0xE0) | 0x08 |           // EID[20:18] + IDE
                 ((frame->id >> 16) & 0x03);                    // EID[17:16]
        buf[2] = (frame->id >> 8) & 0xFF;                       // EID[15:8]
        buf[3] = frame->id & 0xFF;                              // EID[7:0]
    } else {
        // Standard ID (11-bit)
        buf[0] = (frame->id >> 3) & 0xFF;                       // SID[10:3]
        buf[1] = (frame->id & 0x07) << 5;                       // SID[2:0]
    }

    // DLC + RTR
    buf[4] = frame->dlc & 0x0F;
    if (frame->is_remote) buf[4] |= 0x40;

    // Data
    for (uint8_t i = 0; i < frame->dlc && i < 8; i++) {
        buf[5 + i] = frame->data[i];
    }

    // Write to TX buffer
    writeRegisters(regBase, buf, 5 + frame->dlc);

    // Trigger transmission via RTS command
    uint8_t rts_cmd = MCP2515_CMD_RTS | (1 << tx_buffer);
    select();
    SPI.transfer(rts_cmd);
    deselect();

    _frames_tx++;
    return true;
}

bool MCP2515Driver::txBufferFree(uint8_t tx_buffer) {
    uint8_t status = readStatus();

    switch (tx_buffer) {
        case 0: return (status & 0x04) == 0;  // TXB0 pending bit
        case 1: return (status & 0x10) == 0;  // TXB1 pending bit
        case 2: return (status & 0x40) == 0;  // TXB2 pending bit
        default: return false;
    }
}

void MCP2515Driver::abortTransmissions() {
    modifyRegister(MCP2515_REG_CANCTRL, MCP2515_CANCTRL_ABAT, MCP2515_CANCTRL_ABAT);
    delayMicroseconds(100);
    modifyRegister(MCP2515_REG_CANCTRL, MCP2515_CANCTRL_ABAT, 0x00);
}

// ============================================================================
// FILTER & MASK CONFIGURATION
// ============================================================================

void MCP2515Driver::setFilter(uint8_t filter_num, uint32_t id, bool extended) {
    uint8_t regBase;

    switch (filter_num) {
        case 0: regBase = MCP2515_REG_RXF0SIDH; break;
        case 1: regBase = MCP2515_REG_RXF1SIDH; break;
        case 2: regBase = MCP2515_REG_RXF2SIDH; break;
        case 3: regBase = MCP2515_REG_RXF3SIDH; break;
        case 4: regBase = MCP2515_REG_RXF4SIDH; break;
        case 5: regBase = MCP2515_REG_RXF5SIDH; break;
        default: return;
    }

    uint8_t buf[4];
    if (extended) {
        buf[0] = (id >> 21) & 0xFF;
        buf[1] = ((id >> 13) & 0xE0) | 0x08 | ((id >> 16) & 0x03);
        buf[2] = (id >> 8) & 0xFF;
        buf[3] = id & 0xFF;
    } else {
        buf[0] = (id >> 3) & 0xFF;
        buf[1] = (id & 0x07) << 5;
        buf[2] = 0;
        buf[3] = 0;
    }

    writeRegisters(regBase, buf, 4);
}

void MCP2515Driver::setMask(uint8_t mask_num, uint32_t mask, bool extended) {
    uint8_t regBase = (mask_num == 0) ? MCP2515_REG_RXM0SIDH : MCP2515_REG_RXM1SIDH;

    uint8_t buf[4];
    if (extended) {
        buf[0] = (mask >> 21) & 0xFF;
        buf[1] = ((mask >> 13) & 0xE0) | ((mask >> 16) & 0x03);
        buf[2] = (mask >> 8) & 0xFF;
        buf[3] = mask & 0xFF;
    } else {
        buf[0] = (mask >> 3) & 0xFF;
        buf[1] = (mask & 0x07) << 5;
        buf[2] = 0;
        buf[3] = 0;
    }

    writeRegisters(regBase, buf, 4);
}

void MCP2515Driver::configurePhase1Filters() {
    // Must be in configuration mode to set filters
    uint8_t prev_mode = getMode();
    setMode(MCP2515_MODE_CONFIG);

    // Mask: Accept IDs where bits [10:4] match 0x10X pattern
    // Mask = 0x7F0 → checks bits 10:4, ignores bits 3:0
    // This accepts 0x100 through 0x10F
    setMask(0, 0x7F0, false);
    setMask(1, 0x7F0, false);

    // Filters: Set specific base IDs
    // Filter 0 → RXB0: Accept 0x100 (with mask, accepts 0x100-0x10F)
    setFilter(0, 0x100, false);
    setFilter(1, 0x100, false);

    // Filters 2-5 → RXB1 (same mask applies)
    setFilter(2, 0x100, false);
    setFilter(3, 0x100, false);
    setFilter(4, 0x100, false);
    setFilter(5, 0x100, false);

    // Restore previous mode
    setMode(prev_mode);
}

void MCP2515Driver::disableFilters() {
    uint8_t prev_mode = getMode();
    setMode(MCP2515_MODE_CONFIG);

    // Set mask to 0x000 = accept everything
    setMask(0, 0x000, false);
    setMask(1, 0x000, false);

    // Set RXBnCTRL to accept all messages
    writeRegister(MCP2515_REG_RXB0CTRL, MCP2515_RXBCTRL_BUKT | MCP2515_RXBCTRL_RXM1 | MCP2515_RXBCTRL_RXM0);
    writeRegister(MCP2515_REG_RXB1CTRL, MCP2515_RXBCTRL_RXM1 | MCP2515_RXBCTRL_RXM0);

    setMode(prev_mode);
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

uint8_t MCP2515Driver::checkErrors() {
    uint8_t eflg = readRegister(MCP2515_REG_EFLG);

    if (eflg & (MCP2515_EFLG_RX0OVR | MCP2515_EFLG_RX1OVR)) {
        _overrun_count++;
        // Clear overflow flags
        modifyRegister(MCP2515_REG_EFLG,
                      MCP2515_EFLG_RX0OVR | MCP2515_EFLG_RX1OVR, 0x00);
    }

    if (eflg & MCP2515_EFLG_TXBO) {
        _bus_off_count++;
    }

    if (eflg & (MCP2515_EFLG_EWARN | MCP2515_EFLG_RXWAR | MCP2515_EFLG_TXWAR |
                MCP2515_EFLG_RXEP | MCP2515_EFLG_TXEP)) {
        _error_count++;
    }

    return eflg;
}

uint8_t MCP2515Driver::getTxErrorCount() {
    return readRegister(MCP2515_REG_TEC);
}

uint8_t MCP2515Driver::getRxErrorCount() {
    return readRegister(MCP2515_REG_REC);
}

bool MCP2515Driver::isBusOff() {
    uint8_t eflg = readRegister(MCP2515_REG_EFLG);
    return (eflg & MCP2515_EFLG_TXBO) != 0;
}

bool MCP2515Driver::recoverFromBusOff() {
    if (!isBusOff()) return true;

    // Strategy: Enter config mode, clear errors, return to normal
    setMode(MCP2515_MODE_CONFIG);
    delay(10);

    // Clear error flags
    clearErrorFlags();

    // Return to normal mode
    bool success = setMode(MCP2515_MODE_NORMAL);

    if (success) {
        _current_mode = MCP2515_MODE_NORMAL;
    }

    return success;
}

void MCP2515Driver::clearErrorFlags() {
    writeRegister(MCP2515_REG_EFLG, 0x00);
}

// ============================================================================
// STATUS & DIAGNOSTICS
// ============================================================================

uint8_t MCP2515Driver::readStatus() {
    select();
    SPI.transfer(MCP2515_CMD_READ_STATUS);
    uint8_t status = SPI.transfer(0x00);
    deselect();
    return status;
}

uint8_t MCP2515Driver::readRxStatus() {
    select();
    SPI.transfer(MCP2515_CMD_RX_STATUS);
    uint8_t status = SPI.transfer(0x00);
    deselect();
    return status;
}

uint8_t MCP2515Driver::getInterruptFlags() {
    return readRegister(MCP2515_REG_CANINTF);
}

void MCP2515Driver::clearInterruptFlag(uint8_t flag) {
    modifyRegister(MCP2515_REG_CANINTF, flag, 0x00);
}

void MCP2515Driver::getStatistics(uint32_t* frames_rx, uint32_t* frames_tx,
                                   uint32_t* errors, uint32_t* overruns) {
    if (frames_rx)  *frames_rx = _frames_rx;
    if (frames_tx)  *frames_tx = _frames_tx;
    if (errors)     *errors = _error_count;
    if (overruns)   *overruns = _overrun_count;
}

// ============================================================================
// INTERRUPT CONFIGURATION
// ============================================================================

void MCP2515Driver::enableInterrupts(uint8_t mask) {
    writeRegister(MCP2515_REG_CANINTE, mask);
}

void MCP2515Driver::disableInterrupts() {
    writeRegister(MCP2515_REG_CANINTE, 0x00);
}

bool MCP2515Driver::interruptPending() {
    if (_int_pin < 0) return false;
    return digitalRead(_int_pin) == LOW;  // Active LOW
}