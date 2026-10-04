"""Security utilities, authentication dependencies, and security middleware."""

import os
import time
import secrets
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# --- Authentication & Access Control ---

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

def verify_admin_access(
    header_key: Optional[str] = Security(admin_key_header),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> bool:
    """
    Authenticate administrative endpoints via X-Admin-Key header or Bearer token.
    Uses constant-time comparison to prevent timing attacks.
    """
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        # If no admin key is configured, forbid access defensively
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin functionality is disabled. Set ADMIN_API_KEY in environment to enable."
        )

    provided_token = None
    if header_key:
        provided_token = header_key.strip()
    elif bearer_creds:
        provided_token = bearer_creds.credentials.strip()

    if not provided_token or not secrets.compare_digest(provided_token, admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing administrative credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return True


# --- In-Memory Sliding Window Rate Limiter ---

class RateLimiter:
    """Sliding-window IP rate limiter to protect against DoS and quota exhaustion."""

    def __init__(self, requests_per_minute: int = 30):
        self.rpm = requests_per_minute
        self.window_seconds = 60
        self._records: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup(self, now: float):
        """Periodically prune stale records to prevent memory growth."""
        if now - self._last_cleanup > 300:  # Every 5 minutes
            cutoff = now - self.window_seconds
            for ip in list(self._records.keys()):
                valid_timestamps = [t for t in self._records[ip] if t > cutoff]
                if valid_timestamps:
                    self._records[ip] = valid_timestamps
                else:
                    del self._records[ip]
            self._last_cleanup = now

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        now = time.time()
        self._cleanup(now)

        cutoff = now - self.window_seconds
        # Filter timestamps to the current window
        self._records[client_ip] = [t for t in self._records[client_ip] if t > cutoff]

        if len(self._records[client_ip]) >= self.rpm:
            oldest = self._records[client_ip][0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return False, retry_after

        self._records[client_ip].append(now)
        return True, 0


global_rate_limiter = RateLimiter(requests_per_minute=30)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforces rate limiting on sensitive API endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Exclude health check and preflight OPTIONS from rate limiting
        if request.url.path in ("/ping", "/docs", "/openapi.json") or request.method == "OPTIONS":
            return await call_next(request)

        # Extract client IP (respecting forward headers from proxies/reverse proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        allowed, retry_after = global_rate_limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Maximum 30 requests per minute.",
                    "retry_after_seconds": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        return await call_next(request)


# --- OWASP Security Headers Middleware ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies OWASP-recommended HTTP security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Protect against MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking by disallowing framing
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS protection filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Restrict referrer leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser feature access
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Enforce HTTPS HSTS if running in production
        if os.getenv("ENVIRONMENT", "").lower() in ("production", "prod"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
