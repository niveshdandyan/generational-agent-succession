#!/usr/bin/env python3
"""
WebSocket Handler
=================
WebSocket connection management for real-time streaming updates.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None
    ConnectionClosed = Exception

from .config import WEBSOCKET_PING_INTERVAL

if TYPE_CHECKING:
    from .gas_status import GASStatusGatherer

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Track state for a single WebSocket connection."""
    websocket: Any
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: Optional[datetime] = None
    client_id: str = ''
    subscriptions: Set[str] = field(default_factory=lambda: {'status_update', 'agent_update', 'live_event'})


class WebSocketManager:
    """
    Manage WebSocket connections and broadcast messages.
    """

    def __init__(self, status_gatherer: 'GASStatusGatherer'):
        self.status_gatherer = status_gatherer
        self._connections: Set[WebSocketConnection] = set()
        self._lock = asyncio.Lock()
        self._server = None
        self._ping_task: Optional[asyncio.Task] = None
        self._connection_id_counter = 0

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    async def start_server(self, host: str, port: int) -> Any:
        """Start the WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("websockets library not available, WebSocket server disabled")
            return None

        self._server = await websockets.serve(
            self._handle_connection,
            host,
            port,
            ping_interval=WEBSOCKET_PING_INTERVAL,
            ping_timeout=WEBSOCKET_PING_INTERVAL * 2,
        )

        # Start ping task to keep connections alive
        self._ping_task = asyncio.create_task(self._ping_connections())

        logger.info(f"WebSocket server started on ws://{host}:{port}")
        return self._server

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handle a new WebSocket connection."""
        async with self._lock:
            self._connection_id_counter += 1
            conn = WebSocketConnection(
                websocket=websocket,
                client_id=f"client_{self._connection_id_counter}"
            )
            self._connections.add(conn)

        logger.info(f"WebSocket client connected: {conn.client_id} (total: {len(self._connections)})")

        try:
            # Send initial status
            await self._send_initial_status(conn)

            # Handle incoming messages
            async for message in websocket:
                await self._handle_message(conn, message)

        except ConnectionClosed:
            logger.info(f"WebSocket client disconnected: {conn.client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {conn.client_id}: {e}")
        finally:
            async with self._lock:
                self._connections.discard(conn)

    async def _send_initial_status(self, conn: WebSocketConnection) -> None:
        """Send initial status to a newly connected client."""
        try:
            status = await self.status_gatherer.get_full_status()
            message = self._create_message('status_update', status)
            await conn.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending initial status: {e}")

    async def _handle_message(self, conn: WebSocketConnection, message: str) -> None:
        """Handle an incoming message from a client."""
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')

            if msg_type == 'subscribe':
                # Subscribe to specific event types
                events = data.get('events', [])
                if events:
                    conn.subscriptions = set(events)
                    logger.debug(f"Client {conn.client_id} subscribed to: {events}")

            elif msg_type == 'unsubscribe':
                # Unsubscribe from event types
                events = data.get('events', [])
                for event in events:
                    conn.subscriptions.discard(event)

            elif msg_type == 'ping':
                # Respond to ping
                await conn.websocket.send(json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }))

            elif msg_type == 'request_status':
                # Send current status
                await self._send_initial_status(conn)

            elif msg_type == 'request_agent':
                # Send agent details
                agent_id = data.get('agent_id')
                if agent_id:
                    agent_data = await self.status_gatherer.get_agent_details(agent_id)
                    if agent_data:
                        message = self._create_message('agent_update', {
                            'agent_id': agent_id,
                            'data': agent_data
                        })
                        await conn.websocket.send(json.dumps(message))

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {conn.client_id}: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling message from {conn.client_id}: {e}")

    def _create_message(self, msg_type: str, data: Any) -> Dict[str, Any]:
        """Create a standardized message format."""
        return {
            'type': msg_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    async def broadcast(self, msg_type: str, data: Any) -> None:
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        message = self._create_message(msg_type, data)
        message_json = json.dumps(message)

        async with self._lock:
            to_remove = set()
            for conn in self._connections:
                # Check if client is subscribed to this message type
                if msg_type not in conn.subscriptions:
                    continue

                try:
                    await conn.websocket.send(message_json)
                except ConnectionClosed:
                    to_remove.add(conn)
                except Exception as e:
                    logger.error(f"Error broadcasting to {conn.client_id}: {e}")
                    to_remove.add(conn)

            # Remove dead connections
            for conn in to_remove:
                self._connections.discard(conn)

    async def broadcast_status_update(self, status: Dict[str, Any]) -> None:
        """Broadcast a status update to all clients."""
        await self.broadcast('status_update', status)

    async def broadcast_agent_update(self, agent_id: str, agent_data: Dict[str, Any]) -> None:
        """Broadcast an agent update to all clients."""
        await self.broadcast('agent_update', {
            'agent_id': agent_id,
            'data': agent_data
        })

    async def broadcast_live_event(self, event: Dict[str, Any]) -> None:
        """Broadcast a live event to all clients."""
        await self.broadcast('live_event', event)

    async def _ping_connections(self) -> None:
        """Periodically ping connections to keep them alive."""
        while True:
            try:
                await asyncio.sleep(WEBSOCKET_PING_INTERVAL)

                async with self._lock:
                    to_remove = set()
                    for conn in self._connections:
                        try:
                            # Send ping
                            await conn.websocket.send(json.dumps({
                                'type': 'ping',
                                'timestamp': datetime.utcnow().isoformat() + 'Z'
                            }))
                            conn.last_ping = datetime.utcnow()
                        except ConnectionClosed:
                            to_remove.add(conn)
                        except Exception as e:
                            logger.error(f"Error pinging {conn.client_id}: {e}")
                            to_remove.add(conn)

                    for conn in to_remove:
                        self._connections.discard(conn)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping task: {e}")

    async def close_all(self) -> None:
        """Close all WebSocket connections."""
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for conn in self._connections:
                try:
                    await conn.websocket.close(1001, "Server shutting down")
                except Exception:
                    pass
            self._connections.clear()

        logger.info("All WebSocket connections closed")


class FileChangeNotifier:
    """
    Watch for file changes and notify via WebSocket.
    Integrates with FilePositionTracker for incremental reading.
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        status_gatherer: 'GASStatusGatherer'
    ):
        self.ws_manager = ws_manager
        self.status_gatherer = status_gatherer
        self._running = False

    async def start(self, interval: float = 0.5) -> None:
        """Start watching for file changes."""
        self._running = True

        while self._running:
            try:
                # Check for file changes
                has_changes = await self.status_gatherer.check_for_changes()

                if has_changes:
                    # Get updated status and broadcast
                    status = await self.status_gatherer.get_full_status()
                    await self.ws_manager.broadcast_status_update(status)

                    # Get and broadcast any new live events
                    events = await self.status_gatherer.get_new_events()
                    for event in events:
                        await self.ws_manager.broadcast_live_event(event)

            except Exception as e:
                logger.error(f"Error in file change notifier: {e}")

            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
