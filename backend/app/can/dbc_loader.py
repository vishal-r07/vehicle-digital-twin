"""
============================================================================
AutoTwin AI - DBC File Parser
============================================================================
Parses Vector DBC (Database CAN) files for signal definitions.

DBC Format Reference:
  - BO_ <ID> <Name>: <DLC> <Sender>     → Message definition
  - SG_ <Name> : <Bit>|<Len>@<Endian><Sign> (<Factor>,<Offset>) [<Min>|<Max>] "<Unit>" <Receivers>
  - CM_ SG_ <ID> <Signal> "<Comment>"   → Signal description
  - VAL_ <ID> <Signal> <Val> "<Desc>"   → Value descriptions

Supported Features:
  - Standard (11-bit) and Extended (29-bit) message IDs
  - Intel (little-endian) and Motorola (big-endian) byte order
  - Signed and unsigned signals
  - Factor/Offset physical conversion
  - Min/Max validation ranges
  - Units and descriptions

Usage:
    parser = DBCParser("path/to/signals.dbc")
    parser.load()

    msg = parser.get_message(0x100)
    signal = parser.get_signal(0x100, "Speed")
    physical = signal.decode(raw_bytes)
============================================================================
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class DBCSignal:
    """
    A single signal definition from a DBC file.

    Attributes match DBC SG_ line format:
      SG_ <name> : <start_bit>|<length>@<byte_order><sign> (<factor>,<offset>) [<min>|<max>] "<unit>" <receivers>
    """

    name: str
    start_bit: int
    bit_length: int
    byte_order: str  # "little_endian" (Intel) or "big_endian" (Motorola)
    is_signed: bool
    factor: float
    offset: float
    min_value: float
    max_value: float
    unit: str
    receivers: List[str] = field(default_factory=list)
    comment: str = ""
    value_descriptions: Dict[int, str] = field(default_factory=dict)

    # Metadata
    message_id: int = 0
    message_name: str = ""

    @property
    def is_float(self) -> bool:
        """True if factor produces fractional values."""
        return self.factor != 1.0 or self.offset != 0.0

    def decode_raw(self, raw_value: int) -> float:
        """Convert raw integer to physical value."""
        return raw_value * self.factor + self.offset

    def encode_physical(self, physical_value: float) -> int:
        """Convert physical value back to raw integer."""
        if self.factor == 0:
            return 0
        return int((physical_value - self.offset) / self.factor)

    def validate(self, physical_value: float) -> bool:
        """Check if physical value is within valid range."""
        return self.min_value <= physical_value <= self.max_value

    def __repr__(self) -> str:
        return (
            f"DBCSignal({self.name}, id=0x{self.message_id:03X}, "
            f"bit={self.start_bit}:{self.bit_length}, "
            f"factor={self.factor}, offset={self.offset}, unit={self.unit})"
        )


@dataclass
class DBCMessage:
    """
    A CAN message definition from a DBC file.

    Corresponds to a BO_ line and its associated SG_ lines.
    """

    can_id: int
    name: str
    dlc: int
    sender: str
    signals: Dict[str, DBCSignal] = field(default_factory=dict)
    comment: str = ""
    is_extended: bool = False

    @property
    def signal_names(self) -> List[str]:
        return list(self.signals.keys())

    def get_signal(self, name: str) -> Optional[DBCSignal]:
        return self.signals.get(name)

    def add_signal(self, signal: DBCSignal) -> None:
        signal.message_id = self.can_id
        signal.message_name = self.name
        self.signals[signal.name] = signal

    def __repr__(self) -> str:
        ext = "ext" if self.is_extended else "std"
        return (
            f"DBCMessage(0x{self.can_id:03X} '{self.name}', "
            f"DLC={self.dlc}, {ext}, signals={len(self.signals)})"
        )


@dataclass
class DBCFile:
    """Complete parsed DBC file."""

    path: str
    version: str = ""
    messages: Dict[int, DBCMessage] = field(default_factory=dict)
    signal_index: Dict[str, Tuple[int, str]] = field(default_factory=dict)  # name → (msg_id, sig_name)
    comments: Dict[str, str] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def signal_count(self) -> int:
        return sum(len(m.signals) for m in self.messages.values())


# ============================================================================
# DBC PARSER
# ============================================================================


class DBCParser:
    """
    Parser for Vector DBC files.

    Supports the standard DBC format used by Vector CANdb++,
    TSMaster, PCAN Symbol Editor, and most automotive tools.

    Usage:
        parser = DBCParser("vehicle.dbc")
        parser.load()
        msg = parser.get_message(0x100)
    """

    # Regex patterns for DBC parsing
    RE_VERSION = re.compile(r'VERSION\s+"(.*)"')
    RE_MESSAGE = re.compile(
        r'BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+(\w+)'
    )
    RE_SIGNAL = re.compile(
        r'SG_\s+(\w+)\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s*'
        r'\(([^,]+),([^)]+)\)\s*\[([^|]+)\|([^\]]+)\]\s*"([^"]*)"\s*(.*)'
    )
    RE_COMMENT_SIGNAL = re.compile(
        r'CM_\s+SG_\s+(\d+)\s+(\w+)\s+"([^"]*)"'
    )
    RE_COMMENT_MESSAGE = re.compile(
        r'CM_\s+BO_\s+(\d+)\s+"([^"]*)"'
    )
    RE_VALUE_DESC = re.compile(
        r'VAL_\s+(\d+)\s+(\w+)((?:\s+\d+\s+"[^"]*")+)\s*;'
    )

    def __init__(self, file_path: str):
        """
        Initialize DBC parser.

        Args:
            file_path: Path to the DBC file.
        """
        self._file_path = Path(file_path)
        self._dbc: Optional[DBCFile] = None
        self._loaded: bool = False

    # ========================================================================
    # LOADING
    # ========================================================================

    def load(self) -> DBCFile:
        """
        Load and parse the DBC file.

        Returns:
            Parsed DBCFile object.

        Raises:
            FileNotFoundError: If DBC file doesn't exist.
            DBCParseError: If file format is invalid.
        """
        if not self._file_path.exists():
            raise FileNotFoundError(f"DBC file not found: {self._file_path}")

        logger.info(f"DBCParser: loading '{self._file_path.name}'")

        content = self._file_path.read_text(encoding="utf-8", errors="ignore")
        self._dbc = DBCFile(path=str(self._file_path))

        # Parse version
        self._parse_version(content)

        # Parse messages and signals
        self._parse_messages(content)
        self._parse_signals(content)

        # Parse comments
        self._parse_comments(content)

        # Parse value descriptions
        self._parse_value_descriptions(content)

        # Build signal index
        self._build_signal_index()

        self._loaded = True
        logger.info(
            f"DBCParser: loaded {self._dbc.message_count} messages, "
            f"{self._dbc.signal_count} signals"
        )

        return self._dbc

    def load_from_string(self, content: str) -> DBCFile:
        """Load DBC from a string (for testing or embedded DBC)."""
        self._dbc = DBCFile(path="<string>")
        self._parse_version(content)
        self._parse_messages(content)
        self._parse_signals(content)
        self._parse_comments(content)
        self._parse_value_descriptions(content)
        self._build_signal_index()
        self._loaded = True
        return self._dbc

    # ========================================================================
    # PARSING METHODS
    # ========================================================================

    def _parse_version(self, content: str) -> None:
        """Extract DBC version string."""
        match = self.RE_VERSION.search(content)
        if match:
            self._dbc.version = match.group(1)

    def _parse_messages(self, content: str) -> None:
        """Parse all BO_ (message) definitions."""
        for match in self.RE_MESSAGE.finditer(content):
            raw_id = int(match.group(1))
            name = match.group(2)
            dlc = int(match.group(3))
            sender = match.group(4)

            # Check for extended ID (bit 31 set in DBC)
            is_extended = (raw_id & 0x80000000) != 0
            can_id = raw_id & 0x1FFFFFFF if is_extended else raw_id

            message = DBCMessage(
                can_id=can_id,
                name=name,
                dlc=dlc,
                sender=sender,
                is_extended=is_extended,
            )

            self._dbc.messages[can_id] = message

    def _parse_signals(self, content: str) -> None:
        """Parse all SG_ (signal) definitions and attach to messages."""
        lines = content.split("\n")
        current_message_id: Optional[int] = None

        for line in lines:
            line_stripped = line.strip()

            # Track which message we're in
            msg_match = self.RE_MESSAGE.match(line_stripped)
            if msg_match:
                raw_id = int(msg_match.group(1))
                current_message_id = raw_id & 0x1FFFFFFF
                continue

            # Parse signal
            sig_match = self.RE_SIGNAL.match(line_stripped)
            if sig_match and current_message_id is not None:
                signal = self._create_signal_from_match(sig_match)
                if signal and current_message_id in self._dbc.messages:
                    self._dbc.messages[current_message_id].add_signal(signal)

    def _create_signal_from_match(self, match) -> Optional[DBCSignal]:
        """Create a DBCSignal from a regex match."""
        try:
            name = match.group(1)
            start_bit = int(match.group(2))
            bit_length = int(match.group(3))
            byte_order_flag = int(match.group(4))  # 1=Intel, 0=Motorola
            sign_flag = match.group(5)  # '+'=unsigned, '-'=signed
            factor = float(match.group(6))
            offset = float(match.group(7))
            min_val = float(match.group(8))
            max_val = float(match.group(9))
            unit = match.group(10)
            receivers_str = match.group(11).strip()

            receivers = [r.strip() for r in receivers_str.split(",") if r.strip()]

            return DBCSignal(
                name=name,
                start_bit=start_bit,
                bit_length=bit_length,
                byte_order="little_endian" if byte_order_flag == 1 else "big_endian",
                is_signed=(sign_flag == "-"),
                factor=factor,
                offset=offset,
                min_value=min_val,
                max_value=max_val,
                unit=unit,
                receivers=receivers,
            )

        except (ValueError, IndexError) as e:
            logger.error(f"DBCParser: signal parse error: {e}")
            return None

    def _parse_comments(self, content: str) -> None:
        """Parse CM_ comment lines."""
        # Signal comments
        for match in self.RE_COMMENT_SIGNAL.finditer(content):
            msg_id = int(match.group(1))
            sig_name = match.group(2)
            comment = match.group(3)

            if msg_id in self._dbc.messages:
                signal = self._dbc.messages[msg_id].get_signal(sig_name)
                if signal:
                    signal.comment = comment

        # Message comments
        for match in self.RE_COMMENT_MESSAGE.finditer(content):
            msg_id = int(match.group(1))
            comment = match.group(2)

            if msg_id in self._dbc.messages:
                self._dbc.messages[msg_id].comment = comment

    def _parse_value_descriptions(self, content: str) -> None:
        """Parse VAL_ value description lines."""
        for match in self.RE_VALUE_DESC.finditer(content):
            msg_id = int(match.group(1))
            sig_name = match.group(2)
            values_str = match.group(3)

            if msg_id not in self._dbc.messages:
                continue

            signal = self._dbc.messages[msg_id].get_signal(sig_name)
            if not signal:
                continue

            # Parse value-description pairs: 0 "P" 1 "R" 2 "N" ...
            val_pattern = re.compile(r'(\d+)\s+"([^"]*)"')
            for val_match in val_pattern.finditer(values_str):
                val = int(val_match.group(1))
                desc = val_match.group(2)
                signal.value_descriptions[val] = desc

    def _build_signal_index(self) -> None:
        """Build a flat index: signal_name → (message_id, signal_name)."""
        for msg_id, message in self._dbc.messages.items():
            for sig_name in message.signals:
                self._dbc.signal_index[sig_name] = (msg_id, sig_name)

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_message(self, can_id: int) -> Optional[DBCMessage]:
        """Get message definition by CAN ID."""
        if not self._loaded:
            return None
        return self._dbc.messages.get(can_id)

    def get_signal(self, can_id: int, signal_name: str) -> Optional[DBCSignal]:
        """Get a specific signal from a message."""
        msg = self.get_message(can_id)
        if msg:
            return msg.get_signal(signal_name)
        return None

    def get_signal_by_name(self, signal_name: str) -> Optional[DBCSignal]:
        """Get signal by name (searches all messages)."""
        if signal_name in self._dbc.signal_index:
            msg_id, sig_name = self._dbc.signal_index[signal_name]
            return self.get_signal(msg_id, sig_name)
        return None

    def get_all_messages(self) -> Dict[int, DBCMessage]:
        """Get all message definitions."""
        return self._dbc.messages if self._dbc else {}

    def get_all_signal_names(self) -> List[str]:
        """Get list of all signal names in the DBC."""
        return list(self._dbc.signal_index.keys()) if self._dbc else []

    def get_signals_for_message(self, can_id: int) -> List[DBCSignal]:
        """Get all signals for a given CAN ID."""
        msg = self.get_message(can_id)
        if msg:
            return list(msg.signals.values())
        return []

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate(self) -> List[str]:
        """
        Validate the loaded DBC file.

        Returns:
            List of validation warnings/errors (empty if valid).
        """
        issues = []

        if not self._loaded:
            issues.append("DBC file not loaded")
            return issues

        if self._dbc.message_count == 0:
            issues.append("No messages defined in DBC")

        for msg_id, msg in self._dbc.messages.items():
            if msg.dlc < 0 or msg.dlc > 8:
                issues.append(f"Message 0x{msg_id:03X}: invalid DLC {msg.dlc}")

            for sig_name, sig in msg.signals.items():
                if sig.start_bit + sig.bit_length > msg.dlc * 8:
                    issues.append(
                        f"Signal '{sig_name}' in 0x{msg_id:03X}: "
                        f"exceeds message DLC (bit {sig.start_bit}+{sig.bit_length} > {msg.dlc*8})"
                    )
                if sig.factor == 0:
                    issues.append(f"Signal '{sig_name}': factor is zero")
                if sig.min_value > sig.max_value:
                    issues.append(f"Signal '{sig_name}': min > max")

        return issues

    # ========================================================================
    # PROPERTIES
    # ========================================================================

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def file_path(self) -> str:
        return str(self._file_path)

    @property
    def message_count(self) -> int:
        return self._dbc.message_count if self._dbc else 0

    @property
    def signal_count(self) -> int:
        return self._dbc.signal_count if self._dbc else 0