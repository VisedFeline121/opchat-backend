"""
OpChat Backend - Main FastAPI Application

This is a minimal FastAPI application for testing Docker setup.
Real implementation will be added incrementally.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OpChat API",
    description="Real-time messaging backend",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "OpChat API is running", "status": "healthy"}


@app.get("/health")
async def health():
    """Health check endpoint for Docker health checks."""
    return {"status": "healthy", "service": "opchat-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
