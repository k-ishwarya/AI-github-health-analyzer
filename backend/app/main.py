"""Backend entry point for AI GitHub Repository Health Analyzer with enterprise security hardening."""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from dotenv import load_dotenv

from app.api.routes import analyze, history, repository
from app.core.security import RateLimitMiddleware, SecurityHeadersMiddleware

load_dotenv()

# Environment flag (turn off docs and verbose debug details in production)
is_production = os.getenv("ENVIRONMENT", "").lower() in ("production", "prod")

app = FastAPI(
    title="AI GitHub Repository Health Analyzer",
    version="0.1.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# 1. OWASP Security Headers (Nosniff, Frame-Options, XSS, Referrer-Policy, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Sliding Window IP Rate Limiting (30 requests/minute per client IP)
app.add_middleware(RateLimitMiddleware)

# 3. Explicit CORS Protection (No wildcard credentials or open proxying)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "Accept"],
    max_age=600,
)

# 4. Include secured routers
app.include_router(analyze.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(repository.router, prefix="/api")

# 5. Global unhandled error sanitization (suppresses stack traces in production)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if is_production:
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Error: {str(exc)}"}
    )

# 6. Health check endpoint
@app.get("/ping")
async def ping():
    return {"message": "pong", "environment": "production" if is_production else "development"}
