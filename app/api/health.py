"""Health check endpoints for system monitoring."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.messaging.broker import get_message_broker
from app.db.db import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "opchat-backend"}


@router.get("/health/messaging")
async def messaging_health():
    """Health check for messaging infrastructure."""
    try:
        broker = get_message_broker()

        # Check broker connection
        broker_connected = broker.is_connected()

        # Check DLQ message count
        dlq_count = broker.get_dlq_message_count()
        dlq_healthy = (
            dlq_count < 100
        )  # Consider unhealthy if more than 100 messages in DLQ

        # Overall messaging health
        messaging_healthy = broker_connected and dlq_healthy

        return {
            "status": "healthy" if messaging_healthy else "unhealthy",
            "broker_connected": broker_connected,
            "dlq_message_count": dlq_count,
            "dlq_healthy": dlq_healthy,
            "messaging_healthy": messaging_healthy,
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "broker_connected": False,
            "dlq_healthy": False,
            "messaging_healthy": False,
        }


@router.get("/health/database")
async def database_health(db: Session = Depends(get_db)):
    """Health check for database connection."""
    try:
        # Simple query to test database connection
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database_connected": True}
    except Exception as e:
        return {"status": "unhealthy", "database_connected": False, "error": str(e)}


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check for Kubernetes/container orchestration."""
    try:
        # Check database
        db.execute(text("SELECT 1"))

        # Check messaging
        broker = get_message_broker()
        broker_connected = broker.is_connected()

        # Check DLQ
        dlq_count = broker.get_dlq_message_count()
        dlq_healthy = dlq_count < 1000  # More lenient for readiness

        ready = broker_connected and dlq_healthy

        if ready:
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {str(e)}",
        ) from e


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes/container orchestration."""
    return {"status": "alive"}
