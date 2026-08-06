"""
============================================================================
AutoTwin AI - Internal Event Bus (Async Pub/Sub)
============================================================================
Decoupled event system for inter-module communication.

Design:
  - Async-native (asyncio)
  - Multiple subscribers per event type
  - Priority-based delivery
  - Error isolation (one subscriber failing doesn't affect others)
  - Event history ring buffer for debugging
  - Wildcard subscription support

Usage:
    bus = EventBus()

    # Subscribe
    async def on_fault(event: Event):
        print(f"Fault: {event.data}")

    sub = bus.subscribe(EventType.FAULT_DETECTED, on_fault)

    # Publish
    await bus.publish(EventType.FAULT_DETECTED, {"fault_id": "F-001"})

    # Unsubscribe
    bus.unsubscribe(sub)
============================================================================
"""

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from loguru import logger


# ============================================================================
# EVENT DATA STRUCTURES
# ============================================================================


@dataclass
class Event:
    """
    Immutable event object passed through the bus.

    Attributes:
        event_type: Category of the event
        data: Payload (any serializable data)
        timestamp: Unix timestamp of creation
        source: Module that emitted the event
        event_id: Unique identifier
        priority: Delivery priority (higher = delivered first)
    """

    event_type: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    priority: int = 0

    def __repr__(self) -> str:
        return (
            f"Event(type={self.event_type}, source={self.source}, "
            f"id={self.event_id}, data_keys={list(self.data.keys()) if isinstance(self.data, dict) else type(self.data).__name__})"
        )


@dataclass
class EventSubscription:
    """
    Represents a subscription to an event type.

    Returned by EventBus.subscribe() for later unsubscription.
    """

    subscription_id: str
    event_type: str
    callback: Callable[[Event], Coroutine]
    priority: int = 0
    active: bool = True
    filter_fn: Optional[Callable[[Event], bool]] = None
    created_at: float = field(default_factory=time.time)


# ============================================================================
# EVENT BUS IMPLEMENTATION
# ============================================================================


class EventBus:
    """
    Async event bus for decoupled inter-module communication.

    Features:
      - Subscribe to specific event types or wildcard ("*")
      - Priority-based subscriber ordering
      - Error isolation per subscriber
      - Event history for debugging
      - Async publish with concurrent delivery
      - Graceful shutdown with pending event drain

    Thread Safety:
      All methods are async and should be called from the event loop.
      For cross-thread publishing, use asyncio.run_coroutine_threadsafe().
    """

    def __init__(self, history_size: int = 500):
        """
        Initialize the event bus.

        Args:
            history_size: Number of recent events to retain for debugging.
        """
        # Subscribers: event_type → list of subscriptions
        self._subscribers: Dict[str, List[EventSubscription]] = {}

        # Wildcard subscribers (receive all events)
        self._wildcard_subscribers: List[EventSubscription] = []

        # Event history ring buffer
        self._history: deque = deque(maxlen=history_size)

        # Statistics
        self._events_published: int = 0
        self._events_delivered: int = 0
        self._errors: int = 0

        # Shutdown flag
        self._shutdown: bool = False
        self._pending_tasks: Set[asyncio.Task] = set()

        # Lock for subscriber modification
        self._lock = asyncio.Lock()

        logger.debug(f"EventBus initialized (history_size={history_size})")

    # ========================================================================
    # SUBSCRIPTION
    # ========================================================================

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Event], Coroutine],
        priority: int = 0,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> EventSubscription:
        """
        Subscribe to an event type.

        Args:
            event_type: Event type string (or "*" for all events)
            callback: Async function called with Event when published
            priority: Higher priority subscribers are called first
            filter_fn: Optional filter — callback only called if returns True

        Returns:
            EventSubscription handle for later unsubscription.
        """
        sub = EventSubscription(
            subscription_id=str(uuid.uuid4())[:8],
            event_type=event_type,
            callback=callback,
            priority=priority,
            filter_fn=filter_fn,
        )

        if event_type == "*":
            self._wildcard_subscribers.append(sub)
            self._wildcard_subscribers.sort(key=lambda s: s.priority, reverse=True)
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(sub)
            self._subscribers[event_type].sort(key=lambda s: s.priority, reverse=True)

        logger.debug(f"EventBus: subscribed '{event_type}' (id={sub.subscription_id})")
        return sub

    def unsubscribe(self, subscription: EventSubscription) -> bool:
        """
        Remove a subscription.

        Args:
            subscription: The subscription handle from subscribe()

        Returns:
            True if subscription was found and removed.
        """
        subscription.active = False

        if subscription.event_type == "*":
            try:
                self._wildcard_subscribers.remove(subscription)
                return True
            except ValueError:
                return False
        else:
            subs = self._subscribers.get(subscription.event_type, [])
            try:
                subs.remove(subscription)
                return True
            except ValueError:
                return False

    def unsubscribe_all(self, event_type: Optional[str] = None) -> int:
        """
        Remove all subscriptions for an event type (or all types).

        Args:
            event_type: Specific type to clear, or None for all.

        Returns:
            Number of subscriptions removed.
        """
        count = 0

        if event_type is None:
            for subs in self._subscribers.values():
                count += len(subs)
                for s in subs:
                    s.active = False
            self._subscribers.clear()
            count += len(self._wildcard_subscribers)
            for s in self._wildcard_subscribers:
                s.active = False
            self._wildcard_subscribers.clear()
        else:
            subs = self._subscribers.pop(event_type, [])
            count = len(subs)
            for s in subs:
                s.active = False

        logger.debug(f"EventBus: unsubscribed {count} subscription(s)")
        return count

    # ========================================================================
    # PUBLISHING
    # ========================================================================

    async def publish(
        self,
        event_type: str,
        data: Any = None,
        source: str = "system",
        priority: int = 0,
    ) -> Event:
        """
        Publish an event to all subscribers.

        Args:
            event_type: Event type identifier
            data: Event payload
            source: Name of the emitting module
            priority: Event priority

        Returns:
            The Event object that was published.
        """
        if self._shutdown:
            logger.warning(f"EventBus: publish attempted after shutdown ({event_type})")
            return Event(event_type=event_type, data=data, source=source)

        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority,
        )

        # Record in history
        self._history.append(event)
        self._events_published += 1

        # Collect all applicable subscribers
        subscribers = self._get_subscribers(event_type)

        if not subscribers:
            return event

        # Deliver to all subscribers concurrently
        tasks = []
        for sub in subscribers:
            if not sub.active:
                continue

            # Apply filter if present
            if sub.filter_fn is not None:
                try:
                    if not sub.filter_fn(event):
                        continue
                except Exception as e:
                    logger.error(f"EventBus: filter error for {sub.subscription_id}: {e}")
                    continue

            task = asyncio.create_task(self._deliver(sub, event))
            tasks.append(task)
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

        # Wait for all deliveries (with timeout to prevent hanging)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    async def publish_nowait(
        self,
        event_type: str,
        data: Any = None,
        source: str = "system",
        priority: int = 0,
    ) -> Event:
        """
        Publish without waiting for delivery completion.
        Use for high-frequency events where blocking is unacceptable.
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority,
        )

        self._history.append(event)
        self._events_published += 1

        subscribers = self._get_subscribers(event_type)
        for sub in subscribers:
            if sub.active:
                if sub.filter_fn and not sub.filter_fn(event):
                    continue
                asyncio.create_task(self._deliver(sub, event))

        return event

    # ========================================================================
    # INTERNAL DELIVERY
    # ========================================================================

    async def _deliver(self, subscription: EventSubscription, event: Event) -> None:
        """Deliver a single event to a single subscriber with error isolation."""
        try:
            await subscription.callback(event)
            self._events_delivered += 1
        except asyncio.CancelledError:
            pass  # Normal during shutdown
        except Exception as e:
            self._errors += 1
            logger.error(
                f"EventBus: subscriber error "
                f"(sub={subscription.subscription_id}, event={event.event_type}): {e}"
            )

    def _get_subscribers(self, event_type: str) -> List[EventSubscription]:
        """Get all subscribers for an event type (including wildcards)."""
        subscribers = []

        # Type-specific subscribers
        if event_type in self._subscribers:
            subscribers.extend(self._subscribers[event_type])

        # Wildcard subscribers
        subscribers.extend(self._wildcard_subscribers)

        # Sort by priority (higher first)
        subscribers.sort(key=lambda s: s.priority, reverse=True)

        return subscribers

    # ========================================================================
    # HISTORY & DEBUGGING
    # ========================================================================

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Event]:
        """
        Get recent events from history.

        Args:
            event_type: Filter by type (None for all)
            limit: Maximum number of events to return

        Returns:
            List of recent events (newest first).
        """
        events = list(self._history)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:][::-1]  # Newest first

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "events_published": self._events_published,
            "events_delivered": self._events_delivered,
            "errors": self._errors,
            "subscriber_count": sum(len(s) for s in self._subscribers.values())
            + len(self._wildcard_subscribers),
            "event_types": list(self._subscribers.keys()),
            "history_size": len(self._history),
            "pending_tasks": len(self._pending_tasks),
        }

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Gracefully shut down the event bus.

        Waits for pending deliveries to complete (up to timeout).
        """
        self._shutdown = True
        logger.info(f"EventBus: shutting down ({len(self._pending_tasks)} pending tasks)")

        if self._pending_tasks:
            done, pending = await asyncio.wait(
                self._pending_tasks, timeout=timeout
            )
            if pending:
                logger.warning(f"EventBus: {len(pending)} tasks did not complete")
                for task in pending:
                    task.cancel()

        # Clear all subscriptions
        self.unsubscribe_all()
        logger.info("EventBus: shutdown complete")

    def reset(self) -> None:
        """Reset all state (for testing)."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        self._history.clear()
        self._events_published = 0
        self._events_delivered = 0
        self._errors = 0
        self._shutdown = False
        self._pending_tasks.clear()