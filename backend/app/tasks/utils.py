"""Shared utilities for Celery task modules."""

import asyncio


def run_async(coro):
    """Run an async coroutine safely in a Celery forked worker process.

    Celery's prefork pool inherits a closed event loop from the parent.
    asyncio.run() can fail with 'Event loop is closed' in this context.
    This helper creates a fresh event loop every time.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
