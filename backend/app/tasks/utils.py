"""Shared utilities for Celery task modules."""

import asyncio


def run_async(coro):
    """Run an async coroutine safely in a Celery forked worker process.

    Celery's prefork pool inherits a closed event loop from the parent.
    asyncio.run() can fail with 'Event loop is closed' in this context.

    This helper reuses a single event loop per worker process. We must NOT
    close the loop after each call because libraries like google.generativeai
    cache aiohttp sessions bound to the loop — closing it invalidates those
    sessions and causes 'Event loop is closed' on subsequent calls.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
