"""Backend entry point for AI GitHub Repository Health Analyzer"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, history, repository

app = FastAPI(title="AI GitHub Repository Health Analyzer", version="0.1.0")

# CORS settings – allow frontend origin (localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analyze.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(repository.router, prefix="/api")

# Root health check
@app.get("/ping")
async def ping():
    return {"message": "pong"}
