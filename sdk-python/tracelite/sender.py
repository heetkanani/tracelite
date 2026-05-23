"""
Background batched sender for tracelite.

Owns a Queue + a daemon thread that pulls spans off the queue,
batches them, and POSTs to the backend. The user's code path
never blocks on network I/O.
"""
import atexit
import queue
import threading
import time
from typing import Optional

import httpx

from tracelite.span import Span


# Tunable knobs
MAX_QUEUE_SIZE = 10_000     # spans before we start dropping
BATCH_SIZE = 20             # spans per HTTP POST
FLUSH_INTERVAL_SEC = 1.0    # max time a span waits before being sent
HTTP_TIMEOUT_SEC = 5.0


class BackgroundSender:
    """
    One per Client. Started on init(), stopped on shutdown.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._queue: "queue.Queue[Span]" = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="tracelite-sender",
            daemon=True,
        )
        self._thread.start()
        # Ensure pending spans are flushed at interpreter exit
        atexit.register(self.shutdown)

    # -------- public API ----------------------------------------------------

    def submit(self, span: Span) -> None:
        """
        Non-blocking enqueue. Drops the span if the queue is full.
        Called from the user's thread — must return in microseconds.
        """
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            # Best-effort by design. Don't crash user code.
            pass

    def shutdown(self, timeout: float = 30.0) -> None:
        """
        Flush remaining spans and stop the worker thread.

        Bumped the default timeout to 30s because the worker drains the queue
        one span per HTTP call (no batch endpoint yet). For 100s of spans
        that can take a few seconds. Set lower if you don't care.
        """
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._thread.join(timeout=timeout)

    # -------- worker (background thread) ------------------------------------

    def _worker_loop(self) -> None:
        """Drain the queue forever (until stop), batching as we go."""
        batch: list[Span] = []
        last_flush = time.monotonic()

        while not self._stop_event.is_set():
            timeout = max(0.0, FLUSH_INTERVAL_SEC - (time.monotonic() - last_flush))
            try:
                span = self._queue.get(timeout=timeout)
                batch.append(span)
            except queue.Empty:
                pass

            time_to_flush = (time.monotonic() - last_flush) >= FLUSH_INTERVAL_SEC
            size_to_flush = len(batch) >= BATCH_SIZE

            if batch and (time_to_flush or size_to_flush):
                self._send_batch(batch)
                batch = []
                last_flush = time.monotonic()

        # Stop event set — drain anything still in the queue, then exit
        # Stop event set — drain anything still in the queue, then exit.
        # We also flush whatever was in the in-progress batch.
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
            # Send in chunks of BATCH_SIZE so a huge queue doesn't get
            # POSTed as a single mega-batch.
            if len(batch) >= BATCH_SIZE:
                self._send_batch(batch)
                batch = []
        if batch:
            self._send_batch(batch)

    def _send_batch(self, batch: list[Span]) -> None:
        """POST a batch to the backend. Swallows errors."""
        payloads = [s.to_payload() for s in batch]
        try:
            # Phase 3 backend only supports single-span POST.
            # We'll loop for now; switch to a batch endpoint later.
            with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as http:
                for payload in payloads:
                    resp = http.post(
                        f"{self.base_url}/v1/spans",
                        json=payload,
                        headers={"X-API-Key": self.api_key},
                    )
                    if resp.status_code >= 400:
                        # Log to stderr-ish — never raise from the worker
                        print(f"[tracelite] backend rejected span: "
                              f"{resp.status_code} {resp.text[:200]}")
        except Exception as e:
            # Network errors, timeouts, etc. — best-effort, don't crash.
            print(f"[tracelite] sender error: {type(e).__name__}: {e}")