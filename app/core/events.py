import asyncio
from typing import Callable, List, Dict, Any, Type, Awaitable

class EventDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}

    def subscribe(self, event_type: str, listener: Callable[[Any], Awaitable[None]]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    async def emit(self, event_type: str, data: Any):
        if event_type in self._listeners:
            # For each listener, we can run them in a separate task or await them
            for listener in self._listeners[event_type]:
                # We can handle exceptions here so one listener doesn't break the chain
                try:
                    await listener(data)
                except Exception as e:
                    print(f"Error in listener for {event_type}: {e}")

# Global instance of dispatcher
event_bus = EventDispatcher()

# Event notification types
BILLING_GENERATED = "invoice.created"
BILLING_PAID = "invoice.paid"
BILLING_FAILED = "invoice.failed"
BILLING_OVERDUE = "invoice.overdue"
