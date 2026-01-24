"""
Distributed locking service using Redis.
Prevents race conditions in concurrent document processing.

Key Features:
- Prevents duplicate processing of the same document
- Auto-expiring locks (prevents deadlocks)
- Graceful timeout handling
- Multi-tenancy aware

Fix for FLAW-10: Distributed Locks (Redis)
"""
import redis
from redis.exceptions import RedisError, LockError
from typing import Optional, Any
from contextlib import contextmanager
import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("lock_service")


class DistributedLockService:
    """
    Redis-based distributed lock service for preventing race conditions.

    Use Cases:
        - Document processing (prevent duplicate Celery tasks)
        - Tenant billing updates (prevent concurrent balance modifications)
        - Cache invalidation (prevent cache stampede)

    Lock Key Strategy:
        document:process:{document_id}
        tenant:billing:{tenant_id}
        cache:invalidate:{cache_key}
    """

    def __init__(self):
        """Initialize Redis connection for distributed locks."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # Locks need binary mode
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis lock service connected: {settings.REDIS_URL}")
        except RedisError as e:
            logger.error(f"❌ Redis lock connection failed: {e}")
            self.redis_client = None  # Graceful degradation

    def acquire_lock(
        self,
        lock_key: str,
        timeout: int = 300,
        blocking_timeout: Optional[float] = None
    ) -> Optional[redis.lock.Lock]:
        """
        Acquire a distributed lock.

        Args:
            lock_key: Unique identifier for the lock
            timeout: Lock expiration time in seconds (default: 5 minutes)
            blocking_timeout: How long to wait for lock (None = non-blocking)

        Returns:
            Lock object if acquired, None if Redis unavailable or lock acquisition failed

        Example:
            lock = lock_service.acquire_lock("document:process:123", timeout=300, blocking_timeout=5.0)
            if lock:
                try:
                    # Critical section
                    process_document(123)
                finally:
                    lock_service.release_lock(lock)
        """
        if not self.redis_client:
            logger.warning(f"Redis unavailable - lock '{lock_key}' cannot be acquired (graceful degradation)")
            return None

        try:
            lock = self.redis_client.lock(
                lock_key,
                timeout=timeout,
                blocking_timeout=blocking_timeout
            )

            acquired = lock.acquire(blocking=blocking_timeout is not None)

            if acquired:
                logger.info(f"🔒 Lock acquired: {lock_key} (timeout={timeout}s)")
                return lock
            else:
                logger.warning(f"⏳ Lock already held: {lock_key}")
                return None

        except LockError as e:
            logger.error(f"❌ Lock acquisition failed for '{lock_key}': {e}")
            return None
        except RedisError as e:
            logger.error(f"❌ Redis error acquiring lock '{lock_key}': {e}")
            return None

    def release_lock(self, lock: redis.lock.Lock) -> bool:
        """
        Release a distributed lock.

        Args:
            lock: Lock object to release

        Returns:
            True if released successfully, False otherwise
        """
        if not lock:
            return False

        try:
            lock.release()
            logger.info(f"🔓 Lock released: {lock.name.decode() if isinstance(lock.name, bytes) else lock.name}")
            return True
        except LockError as e:
            logger.warning(f"⚠️ Lock release warning (may have expired): {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error releasing lock: {e}")
            return False

    @contextmanager
    def lock(
        self,
        lock_key: str,
        timeout: int = 300,
        blocking_timeout: Optional[float] = None
    ):
        """
        Context manager for distributed locks.

        Args:
            lock_key: Unique identifier for the lock
            timeout: Lock expiration time in seconds
            blocking_timeout: How long to wait for lock (None = non-blocking)

        Yields:
            True if lock acquired, False otherwise

        Example:
            with lock_service.lock("document:process:123", timeout=300) as acquired:
                if acquired:
                    # Critical section - only one worker executes this
                    process_document(123)
                else:
                    # Lock not acquired - another worker is processing
                    logger.info("Document already being processed")
        """
        lock = self.acquire_lock(lock_key, timeout, blocking_timeout)
        acquired = lock is not None

        try:
            yield acquired
        finally:
            if acquired:
                self.release_lock(lock)

    def is_locked(self, lock_key: str) -> bool:
        """
        Check if a lock is currently held.

        Args:
            lock_key: Lock identifier to check

        Returns:
            True if locked, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            # A lock exists if the key exists in Redis
            return self.redis_client.exists(lock_key) > 0
        except RedisError as e:
            logger.error(f"❌ Error checking lock status for '{lock_key}': {e}")
            return False

    def extend_lock(self, lock: redis.lock.Lock, additional_time: int) -> bool:
        """
        Extend lock expiration time (for long-running operations).

        Args:
            lock: Lock object to extend
            additional_time: Additional seconds to add

        Returns:
            True if extended, False otherwise
        """
        if not lock:
            return False

        try:
            lock.extend(additional_time)
            logger.info(f"⏱️ Lock extended: {lock.name} (+{additional_time}s)")
            return True
        except LockError as e:
            logger.error(f"❌ Failed to extend lock: {e}")
            return False

    # --- Convenience Methods for Common Use Cases ---

    def lock_document_processing(self, document_id: int, timeout: int = 600):
        """
        Lock for document processing (prevents duplicate processing).

        Args:
            document_id: Document ID to lock
            timeout: Lock timeout in seconds (default: 10 minutes for large docs)

        Returns:
            Context manager
        """
        return self.lock(f"document:process:{document_id}", timeout=timeout)

    def lock_tenant_billing(self, tenant_id: int, timeout: int = 30):
        """
        Lock for tenant billing updates (prevents race conditions in balance updates).

        Args:
            tenant_id: Tenant ID to lock
            timeout: Lock timeout in seconds (default: 30 seconds)

        Returns:
            Context manager
        """
        return self.lock(f"tenant:billing:{tenant_id}", timeout=timeout)

    def lock_cache_invalidation(self, cache_key: str, timeout: int = 10):
        """
        Lock for cache invalidation (prevents cache stampede).

        Args:
            cache_key: Cache key to lock
            timeout: Lock timeout in seconds (default: 10 seconds)

        Returns:
            Context manager
        """
        return self.lock(f"cache:invalidate:{cache_key}", timeout=timeout)


# Singleton instance
_lock_service_instance = None


def get_lock_service() -> DistributedLockService:
    """
    Get singleton instance of DistributedLockService.

    Returns:
        DistributedLockService instance
    """
    global _lock_service_instance
    if _lock_service_instance is None:
        _lock_service_instance = DistributedLockService()
    return _lock_service_instance


# Convenience alias
lock_service = get_lock_service()
