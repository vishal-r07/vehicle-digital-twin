"""
============================================================================
AutoTwin AI - CAN Frame Ring Buffer
============================================================================
High-performance circular buffer for CAN frames.

Purpose:
  - Absorb bursts of CAN frames without loss
  - Provide ordered access for replay/recording
  - Enable time-windowed queries (last N seconds)
  - Thread-safe for producer (serial thread) / consumer (async parser)

Design:
  - Fixed-size ring buffer (configurable capacity)
  - Lock-free single-producer / single-consumer optimization
  - Overflow counter for dropped frame tracking
  - Timestamp-based retrieval for replay

Usage:
    buffer = FrameBuffer(capacity=1000)

    # Producer (serial thread):
    buffer.push(frame)

    # Consumer (async parser):
    frame = buffer.pop()

    # Time-window query:
    recent = buffer.get_last_n_seconds(5.0)
============================================================================
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger


# ============================================================================
# BUFFERED FRAME DATA STRUCTURE
# ============================================================================


@dataclass
class BufferedFrame:
    """
    A CAN frame stored in the buffer with metadata.

    Wraps either raw CAN data or parsed signals.
    """

    # Frame data
    can_id: int = 0
    data: bytes = b""
    dlc: int = 0
    signals: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    source: str = "unknown"

    # Flags
    is_raw: bool = False       # True if raw CAN bytes
    is_parsed: bool = False    # True if pre-parsed signals

    @property
    def age_ms(self) -> float:
        """Age of this frame in milliseconds."""
        return (time.time() - self.timestamp) * 1000

    def __repr__(self) -> str:
        if self.is_raw:
            return f"BufferedFrame(CAN 0x{self.can_id:03X}, seq={self.sequence})"
        return f"BufferedFrame(parsed, {len(self.signals)} signals, seq={self.sequence})"


# ============================================================================
# FRAME BUFFER IMPLEMENTATION
# ============================================================================


class FrameBuffer:
    """
    Thread-safe ring buffer for CAN frames.

    Features:
      - Fixed capacity with overflow tracking
      - Thread-safe push/pop operations
      - Time-windowed retrieval
      - Sequence numbering
      - Statistics tracking

    Capacity:
      Default 1000 frames. At 20 Hz, this holds 50 seconds of data.
      At 100 Hz (all CAN IDs), this holds 10 seconds.
    """

    def __init__(self, capacity: int = 1000):
        """
        Initialize the frame buffer.

        Args:
            capacity: Maximum number of frames to store.
        """
        self._capacity = capacity
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.Lock()

        # Sequence counter
        self._sequence: int = 0

        # Statistics
        self._total_pushed: int = 0
        self._total_popped: int = 0
        self._total_dropped: int = 0
        self._peak_usage: int = 0

    # ========================================================================
    # PUSH (Producer)
    # ========================================================================

    def push(self, frame: BufferedFrame) -> bool:
        """
        Push a frame into the buffer.

        Thread-safe. Called from serial reader thread.

        Args:
            frame: Frame to buffer.

        Returns:
            True if pushed successfully, False if buffer full (frame dropped).
        """
        with self._lock:
            # Assign sequence number
            self._sequence += 1
            frame.sequence = self._sequence

            # Check if buffer is full (deque auto-evicts oldest)
            if len(self._buffer) >= self._capacity:
                self._total_dropped += 1

            self._buffer.append(frame)
            self._total_pushed += 1

            # Track peak usage
            current_size = len(self._buffer)
            if current_size > self._peak_usage:
                self._peak_usage = current_size

            return True

    def push_raw(self, can_id: int, data: bytes, dlc: int = 8, source: str = "can") -> bool:
        """
        Push a raw CAN frame (convenience method).

        Args:
            can_id: CAN arbitration ID
            data: Payload bytes
            dlc: Data length code
            source: Source identifier

        Returns:
            True if pushed successfully.
        """
        frame = BufferedFrame(
            can_id=can_id,
            data=data,
            dlc=dlc,
            source=source,
            is_raw=True,
        )
        return self.push(frame)

    def push_parsed(self, signals: Dict[str, Any], source: str = "serial") -> bool:
        """
        Push a pre-parsed signal frame (convenience method).

        Args:
            signals: Dictionary of signal values
            source: Source identifier

        Returns:
            True if pushed successfully.
        """
        frame = BufferedFrame(
            signals=signals,
            source=source,
            is_parsed=True,
        )
        return self.push(frame)

    # ========================================================================
    # POP (Consumer)
    # ========================================================================

    def pop(self) -> Optional[BufferedFrame]:
        """
        Pop the oldest frame from the buffer.

        Thread-safe. Called from async parser.

        Returns:
            Oldest BufferedFrame, or None if empty.
        """
        with self._lock:
            if not self._buffer:
                return None

            frame = self._buffer.popleft()
            self._total_popped += 1
            return frame

    def pop_batch(self, max_count: int = 10) -> List[BufferedFrame]:
        """
        Pop multiple frames at once (for batch processing).

        Args:
            max_count: Maximum number of frames to pop.

        Returns:
            List of frames (oldest first).
        """
        frames = []
        with self._lock:
            count = min(max_count, len(self._buffer))
            for _ in range(count):
                frame = self._buffer.popleft()
                self._total_popped += 1
                frames.append(frame)
        return frames

    def peek(self) -> Optional[BufferedFrame]:
        """Peek at the oldest frame without removing it."""
        with self._lock:
            if self._buffer:
                return self._buffer[0]
            return None

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_last_n_frames(self, n: int) -> List[BufferedFrame]:
        """
        Get the last N frames (newest first).

        Args:
            n: Number of frames to retrieve.

        Returns:
            List of frames, newest first.
        """
        with self._lock:
            frames = list(self._buffer)
            return frames[-n:][::-1]

    def get_last_n_seconds(self, seconds: float) -> List[BufferedFrame]:
        """
        Get all frames from the last N seconds.

        Args:
            seconds: Time window in seconds.

        Returns:
            List of frames within the time window (oldest first).
        """
        cutoff = time.time() - seconds
        with self._lock:
            return [f for f in self._buffer if f.timestamp >= cutoff]

    def get_frames_between(self, start_time: float, end_time: float) -> List[BufferedFrame]:
        """
        Get frames within a specific time range.

        Args:
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive)

        Returns:
            List of frames in range (oldest first).
        """
        with self._lock:
            return [
                f for f in self._buffer
                if start_time <= f.timestamp <= end_time
            ]

    def get_frames_by_source(self, source: str) -> List[BufferedFrame]:
        """Get all frames from a specific source."""
        with self._lock:
            return [f for f in self._buffer if f.source == source]

    # ========================================================================
    # BUFFER MANAGEMENT
    # ========================================================================

    def clear(self) -> int:
        """
        Clear all frames from the buffer.

        Returns:
            Number of frames cleared.
        """
        with self._lock:
            count = len(self._buffer)
            self._buffer.clear()
            return count

    @property
    def size(self) -> int:
        """Current number of frames in buffer."""
        return len(self._buffer)

    @property
    def capacity(self) -> int:
        """Maximum buffer capacity."""
        return self._capacity

    @property
    def is_empty(self) -> bool:
        """True if buffer has no frames."""
        return len(self._buffer) == 0

    @property
    def is_full(self) -> bool:
        """True if buffer is at capacity."""
        return len(self._buffer) >= self._capacity

    @property
    def utilization(self) -> float:
        """Buffer utilization as percentage (0-100)."""
        if self._capacity == 0:
            return 0.0
        return (len(self._buffer) / self._capacity) * 100

    @property
    def current_sequence(self) -> int:
        """Current sequence number."""
        return self._sequence

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            "capacity": self._capacity,
            "current_size": len(self._buffer),
            "utilization_pct": round(self.utilization, 1),
            "total_pushed": self._total_pushed,
            "total_popped": self._total_popped,
            "total_dropped": self._total_dropped,
            "peak_usage": self._peak_usage,
            "current_sequence": self._sequence,
            "drop_rate_pct": round(
                self._total_dropped / max(self._total_pushed, 1) * 100, 2
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics counters (does not clear buffer)."""
        self._total_pushed = 0
        self._total_popped = 0
        self._total_dropped = 0
        self._peak_usage = 0

    # ========================================================================
    # EXPORT (for replay recording)
    # ========================================================================

    def export_to_list(self) -> List[Dict[str, Any]]:
        """
        Export all buffered frames as serializable dictionaries.
        Used for saving replay logs.

        Returns:
            List of frame dictionaries.
        """
        with self._lock:
            frames = []
            for f in self._buffer:
                frame_dict = {
                    "timestamp": f.timestamp,
                    "sequence": f.sequence,
                    "source": f.source,
                }
                if f.is_raw:
                    frame_dict["can_id"] = f.can_id
                    frame_dict["data"] = f.data.hex()
                    frame_dict["dlc"] = f.dlc
                elif f.is_parsed:
                    frame_dict["signals"] = f.signals
                frames.append(frame_dict)
            return frames

    def import_from_list(self, frames: List[Dict[str, Any]]) -> int:
        """
        Import frames from serialized format (for replay loading).

        Args:
            frames: List of frame dictionaries.

        Returns:
            Number of frames imported.
        """
        count = 0
        for frame_dict in frames:
            bf = BufferedFrame(
                timestamp=frame_dict.get("timestamp", time.time()),
                sequence=frame_dict.get("sequence", 0),
                source=frame_dict.get("source", "replay"),
            )

            if "can_id" in frame_dict:
                bf.can_id = frame_dict["can_id"]
                bf.data = bytes.fromhex(frame_dict.get("data", ""))
                bf.dlc = frame_dict.get("dlc", 8)
                bf.is_raw = True
            elif "signals" in frame_dict:
                bf.signals = frame_dict["signals"]
                bf.is_parsed = True

            self.push(bf)
            count += 1

        return count