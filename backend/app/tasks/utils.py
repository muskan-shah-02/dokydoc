"""Shared utilities for Celery task modules."""

import asyncio
import threading

# ------------------------------------------------------------------ #
# Dedicated AI Event-Loop Thread                                       #
# ------------------------------------------------------------------ #
# Problem: Celery uses a ThreadPoolExecutor to run batch analyses      #
# concurrently (BATCH_SIZE=3 threads). Each thread called             #
# asyncio.get_event_loop() and then loop.run_until_complete(), which  #
# is NOT thread-safe — asyncio loops cannot be driven from multiple   #
# threads simultaneously.                                              #
#                                                                      #
# Additionally, google.generativeai uses grpc.aio under the hood.     #
# grpc.aio binds its internal futures to the event loop that was      #
# active when the gRPC channel was first used. If a second thread     #
# tries to await those futures on a *different* loop, Python raises   #
# "Future attached to a different loop".                              #
#                                                                      #
# Fix: One dedicated background thread owns a single persistent        #
# event loop. ALL async AI coroutines are submitted to this loop via  #
# asyncio.run_coroutine_threadsafe(), which is explicitly designed    #
# for cross-thread coroutine submission and is fully thread-safe.     #
# ------------------------------------------------------------------ #

_ai_event_loop: asyncio.AbstractEventLoop | None = None
_ai_loop_thread: threading.Thread | None = None
_ai_loop_lock = threading.Lock()


def _run_ai_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Target function for the dedicated AI event-loop thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_ai_loop() -> asyncio.AbstractEventLoop:
    """
    Return the singleton AI event loop, starting its thread on first call.
    Thread-safe via a lock so multiple Celery workers don't race.
    """
    global _ai_event_loop, _ai_loop_thread

    if _ai_event_loop is not None and _ai_event_loop.is_running():
        return _ai_event_loop

    with _ai_loop_lock:
        # Double-checked locking — re-test after acquiring lock.
        if _ai_event_loop is not None and _ai_event_loop.is_running():
            return _ai_event_loop

        loop = asyncio.new_event_loop()
        _ai_event_loop = loop

        t = threading.Thread(
            target=_run_ai_loop,
            args=(loop,),
            daemon=True,
            name="dokydoc-ai-event-loop",
        )
        t.start()
        _ai_loop_thread = t

        # Wait until the loop is actually running before returning.
        import time
        deadline = time.monotonic() + 5.0  # 5-second safety timeout
        while not loop.is_running():
            if time.monotonic() > deadline:
                raise RuntimeError("AI event loop failed to start within 5 seconds")
            time.sleep(0.005)

    return _ai_event_loop


def run_async(coro):
    """
    Run an async coroutine safely from any Celery worker thread.

    Submits the coroutine to the shared AI event loop thread using
    asyncio.run_coroutine_threadsafe(), which is the only officially
    supported way to schedule a coroutine from a different thread.

    Benefits:
    - All gRPC / grpc.aio futures are created and awaited on the
      same event loop → no "Future attached to a different loop".
    - Multiple Celery task threads can call run_async() concurrently;
      each blocks only until its own coroutine finishes.
    - The loop never closes between calls, so gRPC channel state and
      aiohttp sessions are preserved across calls.
    """
    loop = _get_ai_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()  # blocks the calling thread until done
