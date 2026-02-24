"""
Redis-based caching service for AI analysis results.
Provides content-based caching to reduce API costs by 80-90%.
"""
import hashlib
import json
from typing import Optional, Any
import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("cache_service")


class CacheService:
    """
    Content-based caching service using Redis with multi-tenancy support.

    Cache Key Strategy:
        analysis:{tenant_id}:{content_hash}:{prompt_type}

    Example:
        "analysis:1:8f7d9a2c3e5b...:code_analysis"
    """

    def __init__(self):
        """Initialize Redis connection with error handling."""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis cache connected: {settings.REDIS_URL}")
        except RedisError as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None  # Graceful degradation - no caching

    def generate_content_hash(self, content: str) -> str:
        """
        Generate SHA-256 hash of content for cache key.

        Args:
            content: Text content to hash

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]  # First 16 chars

    def _build_cache_key(self, content_hash: str, analysis_type: str, tenant_id: int = 1) -> str:
        """Build cache key from content hash, analysis type, and tenant ID for isolation."""
        return f"analysis:{tenant_id}:{content_hash}:{analysis_type}"

    def get_cached_analysis(
        self,
        content: str,
        analysis_type: str,
        tenant_id: int = 1
    ) -> Optional[dict]:
        """
        Retrieve cached analysis result if exists.

        Args:
            content: The text content being analyzed
            analysis_type: Type of analysis (e.g., "code_analysis", "document_segmentation")
            tenant_id: Tenant ID for multi-tenancy isolation (default: 1)

        Returns:
            Cached result dict or None if cache miss
        """
        if not self.redis_client:
            return None  # No caching available

        try:
            content_hash = self.generate_content_hash(content)
            cache_key = self._build_cache_key(content_hash, analysis_type, tenant_id)

            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                logger.info(f"✅ Cache HIT: {analysis_type} (hash: {content_hash})")
                return json.loads(cached_data)
            else:
                logger.info(f"❌ Cache MISS: {analysis_type} (hash: {content_hash})")
                return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache retrieval error: {e}")
            return None  # Fail gracefully

    def set_cached_analysis(
        self,
        content: str,
        analysis_type: str,
        result: dict,
        ttl_seconds: int = 2592000,  # 30 days default
        tenant_id: int = 1
    ) -> bool:
        """
        Cache analysis result with TTL.

        Args:
            content: The text content that was analyzed
            analysis_type: Type of analysis
            result: Analysis result to cache (must be JSON-serializable)
            ttl_seconds: Time to live in seconds (default: 30 days)
            tenant_id: Tenant ID for multi-tenancy isolation (default: 1)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.redis_client:
            return False  # No caching available

        try:
            content_hash = self.generate_content_hash(content)
            cache_key = self._build_cache_key(content_hash, analysis_type, tenant_id)

            # Serialize result to JSON
            cached_value = json.dumps(result)

            # Store with TTL
            self.redis_client.setex(
                name=cache_key,
                time=ttl_seconds,
                value=cached_value
            )

            logger.info(f"💾 Cache SET: {analysis_type} (hash: {content_hash}, TTL: {ttl_seconds}s)")
            return True

        except (RedisError, TypeError) as e:
            logger.error(f"Cache storage error: {e}")
            return False  # Fail gracefully

    def invalidate_cache(self, content: str, analysis_type: str, tenant_id: int = 1) -> bool:
        """
        Invalidate specific cached analysis.

        Args:
            content: The text content
            analysis_type: Type of analysis to invalidate
            tenant_id: Tenant ID for multi-tenancy isolation (default: 1)

        Returns:
            True if deleted, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            content_hash = self.generate_content_hash(content)
            cache_key = self._build_cache_key(content_hash, analysis_type, tenant_id)

            result = self.redis_client.delete(cache_key)

            if result > 0:
                logger.info(f"🗑️ Cache INVALIDATED: {analysis_type} (hash: {content_hash})")
                return True
            else:
                return False

        except RedisError as e:
            logger.error(f"Cache invalidation error: {e}")
            return False

    def clear_all_analysis_cache(self) -> int:
        """
        Clear ALL analysis cache (use with caution!).

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            # Find all analysis:* keys
            keys = self.redis_client.keys("analysis:*")

            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.warning(f"🗑️ Cleared ALL analysis cache: {deleted_count} keys deleted")
                return deleted_count
            else:
                logger.info("No analysis cache keys to delete")
                return 0

        except RedisError as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    # ============================================================
    # BRANCH PREVIEW METHODS (Sprint 4 Phase 4)
    # ============================================================

    def _build_preview_key(self, tenant_id: int, repo_id: int, branch: str) -> str:
        """Build Redis key for branch preview graph."""
        return f"preview_graph:{tenant_id}:{repo_id}:{branch}"

    def set_branch_preview(
        self,
        *,
        tenant_id: int,
        repo_id: int,
        branch: str,
        preview_data: dict,
        ttl_seconds: int = 604800,  # 7 days
    ) -> bool:
        """
        Store ephemeral branch preview graph in Redis.

        Args:
            tenant_id: Tenant ID for isolation
            repo_id: Repository ID
            branch: Branch name (e.g., "feature/add-payment")
            preview_data: Extracted entities/relationships from branch
            ttl_seconds: Time to live (default 7 days)

        Returns:
            True if stored successfully
        """
        if not self.redis_client:
            return False

        try:
            key = self._build_preview_key(tenant_id, repo_id, branch)
            self.redis_client.setex(
                name=key,
                time=ttl_seconds,
                value=json.dumps(preview_data, default=str),
            )
            logger.info(
                f"Branch preview SET: {key} "
                f"({len(preview_data.get('entities', []))} entities, TTL: {ttl_seconds}s)"
            )
            return True
        except (RedisError, TypeError) as e:
            logger.error(f"Branch preview storage error: {e}")
            return False

    def get_branch_preview(
        self,
        *,
        tenant_id: int,
        repo_id: int,
        branch: str,
    ) -> Optional[dict]:
        """
        Retrieve branch preview graph from Redis.

        Returns:
            Preview data dict or None if not found / expired
        """
        if not self.redis_client:
            return None

        try:
            key = self._build_preview_key(tenant_id, repo_id, branch)
            data = self.redis_client.get(key)
            if data:
                logger.info(f"Branch preview HIT: {key}")
                return json.loads(data)
            else:
                logger.info(f"Branch preview MISS: {key}")
                return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Branch preview retrieval error: {e}")
            return None

    def delete_branch_preview(
        self,
        *,
        tenant_id: int,
        repo_id: int,
        branch: str,
    ) -> bool:
        """
        Clean up preview when branch is merged or deleted.

        Returns:
            True if deleted, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            key = self._build_preview_key(tenant_id, repo_id, branch)
            result = self.redis_client.delete(key)
            if result > 0:
                logger.info(f"Branch preview DELETED: {key}")
                return True
            return False
        except RedisError as e:
            logger.error(f"Branch preview deletion error: {e}")
            return False

    def list_branch_previews(
        self,
        *,
        tenant_id: int,
        repo_id: int,
    ) -> list:
        """
        List all active branch previews for a repo.

        Returns:
            List of branch names with active previews
        """
        if not self.redis_client:
            return []

        try:
            pattern = f"preview_graph:{tenant_id}:{repo_id}:*"
            keys = self.redis_client.keys(pattern)
            branches = []
            prefix = f"preview_graph:{tenant_id}:{repo_id}:"
            for key in keys:
                branch_name = key[len(prefix):]
                branches.append(branch_name)
            return branches
        except RedisError as e:
            logger.error(f"Branch preview listing error: {e}")
            return []

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        if not self.redis_client:
            return {"status": "unavailable"}

        try:
            info = self.redis_client.info()
            analysis_keys = len(self.redis_client.keys("analysis:*"))

            return {
                "status": "connected",
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "total_keys": info.get("db0", {}).get("keys", 0),
                "analysis_cache_keys": analysis_keys,
                "connected_clients": info.get("connected_clients", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except RedisError as e:
            logger.error(f"Cache stats error: {e}")
            return {"status": "error", "error": str(e)}


# Global cache service instance
cache_service = CacheService()
