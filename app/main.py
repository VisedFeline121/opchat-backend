"""OpChat Backend main application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import get_logger, log_startup_info, setup_logging

# Initialize logging first
setup_logging()

# Get logger after setup
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    log_startup_info()
    logger.info("FastAPI application started successfully")
    yield
    # Shutdown
    logger.info("FastAPI application shutting down")


app = FastAPI(
    title="OpChat Backend",
    description="Real-time messaging backend",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint for health checks."""
    logger.info("Health check endpoint accessed")
    return {"message": "OpChat Backend is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    logger.info("Detailed health check accessed")
    return {"status": "healthy", "service": "opchat-backend", "version": "0.1.0"}
