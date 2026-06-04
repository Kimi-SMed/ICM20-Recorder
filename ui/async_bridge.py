"""Asyncio-Qt bridge for ICM2 BLE ECG Recorder.

Architecture:
  - asyncio event loop runs in a daemon background thread via loop.run_forever()
  - BLE notify callbacks (in asyncio thread) put parsed data into queue.Queue
  - Qt main thread QTimer (50ms) drains queue and updates UI

Threading rules (MUST follow):
  - NEVER call asyncio.run() or run_until_complete() from Qt slots
  - NEVER call Qt widget methods from asyncio callbacks
  - ALWAYS use asyncio.run_coroutine_threadsafe(coro, loop) from Qt thread
  - ALWAYS use queue.Queue.put_nowait() from asyncio callbacks
"""

import asyncio
import queue
import threading
import logging
from typing import Optional, Any
from concurrent.futures import Future

logger = logging.getLogger(__name__)


class AsyncBridge:
    """Manages the asyncio event loop in a background thread and provides
    a thread-safe queue for data flowing from asyncio to Qt."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.data_queue: queue.Queue[Any] = queue.Queue()
        self._started: bool = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the running asyncio event loop. Only valid after start()."""
        if self._loop is None:
            raise RuntimeError("AsyncBridge not started. Call start() first.")
        return self._loop

    def start(self) -> None:
        """Start the asyncio event loop in a daemon thread."""
        if self._started:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="AsyncBridgeThread",
            daemon=True,
        )
        self._thread.start()
        self._started = True
        logger.info("AsyncBridge started")

    def stop(self) -> None:
        """Stop the asyncio event loop and join the thread."""
        if not self._started or self._loop is None:
            return
        _ = self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._started = False
        logger.info("AsyncBridge stopped")

    def submit_coro(self, coro: Any) -> Future[Any]:
        """Submit a coroutine to be run in the asyncio thread.

        Safe to call from the Qt main thread.
        Returns a concurrent.futures.Future wrapping the coroutine.
        """
        if not self._started or self._loop is None:
            raise RuntimeError("AsyncBridge not started.")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def put_data(self, item: Any) -> None:
        """Put data item into the thread-safe queue.

        Called from asyncio BLE notify callbacks. Never blocks.
        """
        try:
            self.data_queue.put_nowait(item)
        except queue.Full:
            logger.warning("Data queue full - dropping packet")

    def _run_loop(self) -> None:
        """Entry point for the background thread."""
        if self._loop is None:
            return
        asyncio.set_event_loop(self._loop)
        logger.info("AsyncBridge event loop starting")
        self._loop.run_forever()
        logger.info("AsyncBridge event loop stopped")
