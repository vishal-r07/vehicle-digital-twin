"""
============================================================================
AutoTwin AI - CAN Log Replay Engine
============================================================================
Plays back recorded CAN data for diagnostics and demonstration.

Features:
  - Load recorded CAN logs (JSON format)
  - Play at variable speed (0.5x, 1x, 2x, 4x, 10x)
  - Pause/resume/seek
  - Timeline scrubbing
  - Emit frames as if they were live

Log Format (JSON):
  {
    "metadata": {"vehicle": "toyota_corolla", "duration_s": 120, ...},
    "frames": [
      {"timestamp": 1000.0, "signals": {"speed": 58, "rpm": 2450, ...}},
      {"timestamp": 1000.05, "signals": {"speed": 58.5, ...}},
      ...
    ]
  }

Usage:
    replay = ReplayEngine(event_bus)
    await replay.load("path/to/log.json")
    await replay.play(speed=1.0)
    await replay.seek(45.0)  # Jump to 45 seconds
    await replay.stop()
============================================================================
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import EventType
from app.core.event_bus import EventBus


# ============================================================================
# REPLAY ENGINE
# ============================================================================


class ReplayEngine:
    """
    Plays back recorded CAN/signal data.

    Supports variable speed, pause, seek, and timeline scrubbing.
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

        # Loaded log data
        self._frames: List[Dict[str, Any]] = []
        self._metadata: Dict[str, Any] = {}
        self._duration_s: float = 0.0
        self._loaded: bool = False

        # Playback state
        self._playing: bool = False
        self._paused: bool = False
        self._speed: float = 1.0
        self._position_s: float = 0.0
        self._frame_index: int = 0
        self._task: Optional[asyncio.Task] = None

        # Statistics
        self._frames_played: int = 0
        self._replays_completed: int = 0

    # ========================================================================
    # LOG LOADING
    # ========================================================================

    async def load(self, file_path: str) -> bool:
        """
        Load a CAN log file for replay.

        Args:
            file_path: Path to JSON log file

        Returns:
            True if loaded successfully
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"ReplayEngine: file not found: {file_path}")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._metadata = data.get("metadata", {})
            self._frames = data.get("frames", [])
            self._duration_s = self._metadata.get("duration_s", 0.0)

            # Calculate duration from frames if not in metadata
            if self._duration_s == 0 and self._frames:
                first_ts = self._frames[0].get("timestamp", 0)
                last_ts = self._frames[-1].get("timestamp", 0)
                self._duration_s = last_ts - first_ts

            self._loaded = True
            self._position_s = 0.0
            self._frame_index = 0

            logger.info(
                f"ReplayEngine: loaded {len(self._frames)} frames, "
                f"duration={self._duration_s:.1f}s"
            )
            return True

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"ReplayEngine: failed to load {file_path}: {e}")
            return False

    def load_from_frames(self, frames: List[Dict], metadata: Optional[Dict] = None) -> bool:
        """Load frames directly (for testing or database replay)."""
        self._frames = frames
        self._metadata = metadata or {}
        self._duration_s = self._metadata.get("duration_s", 0)

        if self._duration_s == 0 and frames:
            self._duration_s = frames[-1].get("timestamp", 0) - frames[0].get("timestamp", 0)

        self._loaded = True
        self._position_s = 0.0
        self._frame_index = 0
        return True

    # ========================================================================
    # PLAYBACK CONTROL
    # ========================================================================

    async def play(self, speed: float = 1.0) -> bool:
        """Start or resume playback."""
        if not self._loaded:
            logger.warning("ReplayEngine: no log loaded")
            return False

        if self._playing and not self._paused:
            return True  # Already playing

        self._playing = True
        self._paused = False
        self._speed = max(0.1, min(speed, 10.0))

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._playback_loop())

        await self._event_bus.publish(
            EventType.REPLAY_STARTED,
            data={
                "duration_s": self._duration_s,
                "frame_count": len(self._frames),
                "speed": self._speed,
            },
            source="replay_engine",
        )

        logger.info(f"ReplayEngine: playing at {self._speed}x")
        return True

    async def pause(self) -> None:
        """Pause playback."""
        self._paused = True
        await self._event_bus.publish(
            EventType.REPLAY_PAUSED,
            data={"position_s": self._position_s},
            source="replay_engine",
        )

    async def resume(self) -> None:
        """Resume paused playback."""
        self._paused = False

    async def stop(self) -> None:
        """Stop playback completely."""
        self._playing = False
        self._paused = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._event_bus.publish(
            EventType.REPLAY_STOPPED,
            data={"position_s": self._position_s, "frames_played": self._frames_played},
            source="replay_engine",
        )

        logger.info(f"ReplayEngine: stopped at {self._position_s:.1f}s")

    async def seek(self, position_s: float) -> None:
        """Seek to a specific position in the log."""
        if not self._loaded:
            return

        self._position_s = max(0.0, min(position_s, self._duration_s))

        # Find frame index for this position
        self._frame_index = self._find_frame_at(self._position_s)

        await self._event_bus.publish(
            EventType.REPLAY_SEEKED,
            data={"position_s": self._position_s},
            source="replay_engine",
        )

    def set_speed(self, speed: float) -> None:
        """Set playback speed multiplier."""
        self._speed = max(0.1, min(speed, 10.0))

    # ========================================================================
    # PLAYBACK LOOP
    # ========================================================================

    async def _playback_loop(self) -> None:
        """Main playback loop."""
        try:
            last_time = time.time()

            while self._playing and self._frame_index < len(self._frames):
                if self._paused:
                    await asyncio.sleep(0.01)
                    continue

                now = time.time()
                dt = (now - last_time) * self._speed
                last_time = now

                self._position_s += dt

                # Emit frames up to current position
                while (self._frame_index < len(self._frames) and
                       self._frames[self._frame_index].get("timestamp", 0) <= self._position_s):

                    frame = self._frames[self._frame_index]
                    signals = frame.get("signals", {})

                    if signals:
                        await self._event_bus.publish_nowait(
                            EventType.STATE_UPDATED,
                            data={
                                "changed_signals": signals,
                                "source": "replay",
                                "replay_position_s": self._position_s,
                            },
                            source="replay_engine",
                        )
                        self._frames_played += 1

                    self._frame_index += 1

                # Check completion
                if self._position_s >= self._duration_s:
                    self._playing = False
                    self._replays_completed += 1
                    await self._event_bus.publish(
                        EventType.REPLAY_STOPPED,
                        data={"completed": True, "frames_played": self._frames_played},
                        source="replay_engine",
                    )
                    return

                await asyncio.sleep(0.01)  # ~100 Hz tick rate

        except asyncio.CancelledError:
            pass

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _find_frame_at(self, position_s: float) -> int:
        """Binary search for frame index at given position."""
        lo, hi = 0, len(self._frames) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            ts = self._frames[mid].get("timestamp", 0)
            if ts < position_s:
                lo = mid + 1
            else:
                hi = mid - 1
        return lo

    # ========================================================================
    # PROPERTIES & STATS
    # ========================================================================

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def position(self) -> float:
        return self._position_s

    @property
    def progress(self) -> float:
        if self._duration_s == 0:
            return 0.0
        return self._position_s / self._duration_s

    @property
    def duration(self) -> float:
        return self._duration_s

    def get_stats(self) -> Dict[str, Any]:
        return {
            "loaded": self._loaded,
            "playing": self.is_playing,
            "paused": self._paused,
            "speed": self._speed,
            "position_s": round(self._position_s, 2),
            "duration_s": round(self._duration_s, 2),
            "progress_pct": round(self.progress * 100, 1),
            "frame_count": len(self._frames),
            "frames_played": self._frames_played,
            "replays_completed": self._replays_completed,
        }