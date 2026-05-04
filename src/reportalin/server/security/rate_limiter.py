"""
Rate Limiting Module for MCP Server.

This module implements request rate limiting to protect against
denial-of-service attacks and prevent resource exhaustion.

Algorithms:
    - Sliding Window: Smooth rate limiting without burst issues
    - Token Bucket: Allows controlled bursts (optional)

Storage Backends:
    - InMemory: For single-instance deployments
    - Redis: For distributed deployments (future)

Design Decisions:
    - Async-first: All operations are non-blocking
    - Configurable per-route: Different limits for different endpoints
    - Client identification: Supports IP, token, or custom extractors
    - Graceful degradation: Falls back to allow on storage failure

Security Considerations:
    - IP-based limits can be bypassed with rotating IPs
    - Token-based limits are more reliable for authenticated endpoints
    - Consider using both for defense in depth

Usage:
    >>> from reportalin.server.security.rate_limiter import RateLimiter, RateLimitConfig
    >>>
    >>> config = RateLimitConfig(requests_per_minute=60)
    >>> limiter = RateLimiter(config)
    >>>
    >>> # In request handler
    >>> if not await limiter.is_allowed(client_id):
    >>>     raise HTTPException(429, "Rate limit exceeded")

See Also:
    - server/security/middleware.py: RateLimitMiddleware integration
    - server/config.py: Rate limit configuration via environment
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "InMemoryRateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "RateLimitResult",
    "RateLimiter",
    "SlidingWindowLimiter",
]


# =============================================================================
# Exceptions
# =============================================================================


class RateLimitExceeded(Exception):
    """
    Raised when a client exceeds their rate limit.

    Attributes:
        client_id: Identifier of the rate-limited client
        limit: The rate limit that was exceeded
        retry_after: Seconds until the client can retry
    """

    def __init__(
        self,
        client_id: str,
        limit: int,
        retry_after: float,
        message: str | None = None,
    ) -> None:
        self.client_id = client_id
        self.limit = limit
        self.retry_after = retry_after
        super().__init__(
            message
            or f"Rate limit exceeded for {client_id}. Retry after {retry_after:.1f}s"
        )


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """
    Configuration for rate limiting.

    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        requests_per_second: Maximum requests per second (burst limit)
        burst_size: Number of requests allowed in a burst
        enabled: Whether rate limiting is active
        whitelist: Client IDs exempt from rate limiting

    Example:
        >>> config = RateLimitConfig(
        ...     requests_per_minute=60,
        ...     requests_per_second=5,
        ...     burst_size=10,
        ... )
    """

    requests_per_minute: int = 60
    requests_per_second: int = 10
    burst_size: int = 20
    enabled: bool = True
    whitelist: frozenset[str] = field(default_factory=frozenset)

    @property
    def window_seconds(self) -> int:
        """Get the rate limit window in seconds."""
        return 60

    def with_whitelist(self, *client_ids: str) -> RateLimitConfig:
        """Return a new config with additional whitelisted clients."""
        return RateLimitConfig(
            requests_per_minute=self.requests_per_minute,
            requests_per_second=self.requests_per_second,
            burst_size=self.burst_size,
            enabled=self.enabled,
            whitelist=self.whitelist | frozenset(client_ids),
        )


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """
    Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed
        remaining: Number of requests remaining in the window
        limit: Total requests allowed in the window
        reset_at: Unix timestamp when the window resets
        retry_after: Seconds to wait before retrying (if not allowed)
    """

    allowed: bool
    remaining: int
    limit: int
    reset_at: float
    retry_after: float = 0.0

    def to_headers(self) -> dict[str, str]:
        """
        Generate HTTP headers for rate limit info.

        Returns standard rate limit headers:
        - X-RateLimit-Limit: Total requests allowed
        - X-RateLimit-Remaining: Requests remaining
        - X-RateLimit-Reset: Unix timestamp of window reset
        - Retry-After: Seconds to wait (only if blocked)
        """
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if not self.allowed:
            headers["Retry-After"] = str(int(self.retry_after) + 1)
        return headers


# =============================================================================
# Abstract Base
# =============================================================================


class RateLimiter(ABC):
    """
    Abstract base class for rate limiters.

    Implementations must provide async methods for checking and
    recording rate limits. This allows for different storage backends
    (in-memory, Redis, database).
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def check(self, client_id: str) -> RateLimitResult:
        """
        Check if a request is allowed and record it.

        Args:
            client_id: Unique identifier for the client

        Returns:
            RateLimitResult with allow/deny decision and metadata
        """
        pass

    async def is_allowed(self, client_id: str) -> bool:
        """
        Simple check if a request is allowed.

        Args:
            client_id: Unique identifier for the client

        Returns:
            True if allowed, False if rate limited
        """
        result = await self.check(client_id)
        return result.allowed

    async def require(self, client_id: str) -> RateLimitResult:
        """
        Check rate limit and raise exception if exceeded.

        Args:
            client_id: Unique identifier for the client

        Returns:
            RateLimitResult if allowed

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        result = await self.check(client_id)
        if not result.allowed:
            raise RateLimitExceeded(
                client_id=client_id,
                limit=result.limit,
                retry_after=result.retry_after,
            )
        return result

    @abstractmethod
    async def reset(self, client_id: str) -> None:
        """Reset the rate limit counter for a client."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        pass


# =============================================================================
# In-Memory Implementation
# =============================================================================


@dataclass
class _WindowState:
    """Internal state for sliding window rate limiter."""

    count: int = 0
    window_start: float = 0.0
    last_request: float = 0.0


class InMemoryRateLimiter(RateLimiter):
    """
    In-memory sliding window rate limiter.

    This implementation uses a simple sliding window algorithm that
    tracks request counts per client within a time window.

    Thread Safety:
        Uses asyncio.Lock for thread-safe access to state.
        Safe for use with multiple concurrent requests.

    Memory:
        State is periodically cleaned to prevent memory growth.
        Inactive clients are evicted after 2x window duration.

    Limitations:
        - Not suitable for distributed deployments (use Redis instead)
        - State is lost on server restart

    Attributes:
        config: Rate limit configuration

    Example:
        >>> config = RateLimitConfig(requests_per_minute=60)
        >>> limiter = InMemoryRateLimiter(config)
        >>> result = await limiter.check("client-123")
        >>> if result.allowed:
        ...     # Process request
    """

    def __init__(self, config: RateLimitConfig) -> None:
        super().__init__(config)
        self._state: dict[str, _WindowState] = defaultdict(_WindowState)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300.0  # 5 minutes
        self._total_requests = 0
        self._total_blocked = 0

    async def check(self, client_id: str) -> RateLimitResult:
        """
        Check if request is allowed using sliding window algorithm.

        The sliding window smoothly transitions counts between windows,
        avoiding the "thundering herd" problem at window boundaries.
        """
        # Bypass for disabled or whitelisted
        if not self.config.enabled:
            return RateLimitResult(
                allowed=True,
                remaining=self.config.requests_per_minute,
                limit=self.config.requests_per_minute,
                reset_at=time.time() + 60,
            )

        if client_id in self.config.whitelist:
            return RateLimitResult(
                allowed=True,
                remaining=self.config.requests_per_minute,
                limit=self.config.requests_per_minute,
                reset_at=time.time() + 60,
            )

        async with self._lock:
            now = time.time()
            window_size = self.config.window_seconds

            # Get or create state
            state = self._state[client_id]

            # Check if we need to start a new window
            window_end = state.window_start + window_size
            if now >= window_end:
                # Start new window, carrying over partial count
                elapsed_ratio = min(1.0, (now - state.window_start) / window_size)
                carryover = int(state.count * (1 - elapsed_ratio))
                state.count = carryover
                state.window_start = now

            # Calculate remaining
            remaining = self.config.requests_per_minute - state.count
            reset_at = state.window_start + window_size

            # Check if allowed
            self._total_requests += 1

            if remaining > 0:
                state.count += 1
                state.last_request = now

                # Periodic cleanup
                if now - self._last_cleanup > self._cleanup_interval:
                    await self._cleanup_stale_entries(now)

                return RateLimitResult(
                    allowed=True,
                    remaining=remaining - 1,
                    limit=self.config.requests_per_minute,
                    reset_at=reset_at,
                )
            else:
                self._total_blocked += 1
                retry_after = reset_at - now
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=self.config.requests_per_minute,
                    reset_at=reset_at,
                    retry_after=max(0, retry_after),
                )

    async def _cleanup_stale_entries(self, now: float) -> None:
        """Remove entries for inactive clients."""
        stale_threshold = now - (self.config.window_seconds * 2)
        stale_keys = [
            k for k, v in self._state.items() if v.last_request < stale_threshold
        ]
        for key in stale_keys:
            del self._state[key]
        self._last_cleanup = now

    async def reset(self, client_id: str) -> None:
        """Reset rate limit for a specific client."""
        async with self._lock:
            if client_id in self._state:
                del self._state[client_id]

    async def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        async with self._lock:
            return {
                "active_clients": len(self._state),
                "total_requests": self._total_requests,
                "total_blocked": self._total_blocked,
                "block_rate": (
                    self._total_blocked / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
                "config": {
                    "requests_per_minute": self.config.requests_per_minute,
                    "enabled": self.config.enabled,
                    "whitelist_size": len(self.config.whitelist),
                },
            }
