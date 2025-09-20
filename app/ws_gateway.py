"""
OpChat WebSocket Gateway

This is a minimal WebSocket gateway for testing Docker setup.
Real implementation will be added incrementally.
"""

import asyncio
import json
import logging
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active connections
active_connections: Set[WebSocketServerProtocol] = set()


async def handle_connection(websocket: WebSocketServerProtocol, path: str):
    """Handle a new WebSocket connection."""
    active_connections.add(websocket)
    client_address = websocket.remote_address
    logger.info(f"New WebSocket connection from {client_address}")

    try:
        # Send welcome message
        await websocket.send(
            json.dumps(
                {
                    "type": "connection.established",
                    "message": "Connected to OpChat WebSocket Gateway",
                }
            )
        )

        # Keep connection alive and handle messages
        async for message in websocket:
            try:
                data = json.loads(message)
                await handle_message(websocket, data)
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps({"type": "error", "message": "Invalid JSON format"})
                )
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await websocket.send(
                    json.dumps({"type": "error", "message": "Internal server error"})
                )

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"WebSocket connection closed: {client_address}")
    finally:
        active_connections.discard(websocket)


async def handle_message(websocket: WebSocketServerProtocol, data: Dict):
    """Handle incoming WebSocket messages."""
    message_type = data.get("type")

    if message_type == "ping":
        await websocket.send(json.dumps({"type": "pong"}))
    elif message_type == "subscribe":
        chat_id = data.get("chat_id")
        if chat_id:
            await websocket.send(
                json.dumps({"type": "subscription.confirmed", "chat_id": chat_id})
            )
        else:
            await websocket.send(
                json.dumps(
                    {"type": "error", "message": "Missing chat_id for subscription"}
                )
            )
    else:
        await websocket.send(
            json.dumps(
                {"type": "error", "message": f"Unknown message type: {message_type}"}
            )
        )


async def main():
    """Start the WebSocket server."""
    logger.info("Starting OpChat WebSocket Gateway on port 8001")

    server = await websockets.serve(
        handle_connection, "0.0.0.0", 8001, ping_interval=20, ping_timeout=10
    )

    logger.info("WebSocket Gateway is running on ws://0.0.0.0:8001")

    # Keep the server running
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
