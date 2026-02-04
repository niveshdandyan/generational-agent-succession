#!/usr/bin/env python3
"""
GAS Dashboard Server - Main Entry Point
========================================
Asyncio-based server with HTTP and WebSocket support for real-time streaming.
"""
import asyncio
import signal
import logging
from typing import Optional
from functools import partial

from .config import PORT, HOST, GAS_NAME, FILE_WATCH_INTERVAL
from .http_handler import create_http_server, HTTPRequestHandler
from .websocket_handler import WebSocketManager
from .gas_status import GASStatusGatherer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DashboardServer:
    """
    Main server coordinating HTTP, WebSocket, and file watching.
    """

    def __init__(self, host: str = HOST, port: int = PORT):
        self.host = host
        self.port = port
        self.ws_manager: Optional[WebSocketManager] = None
        self.status_gatherer: Optional[GASStatusGatherer] = None
        self.http_server = None
        self.ws_server = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._watch_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start all server components."""
        logger.info(f"Starting GAS Dashboard Server for: {GAS_NAME}")

        self._shutdown_event = asyncio.Event()

        # Initialize components
        self.status_gatherer = GASStatusGatherer()
        self.ws_manager = WebSocketManager(self.status_gatherer)

        # Create HTTP server
        self.http_server = await create_http_server(
            host=self.host,
            port=self.port,
            status_gatherer=self.status_gatherer,
            ws_manager=self.ws_manager
        )

        # Create WebSocket server
        self.ws_server = await self.ws_manager.start_server(
            host=self.host,
            port=self.port + 1  # WebSocket on port+1
        )

        # Start file watching for status updates
        self._watch_task = asyncio.create_task(self._watch_files())

        logger.info(f"HTTP server running at http://{self.host}:{self.port}")
        logger.info(f"WebSocket server running at ws://{self.host}:{self.port + 1}")
        logger.info("Dashboard is ready!")

    async def _watch_files(self) -> None:
        """Watch for file changes and broadcast updates."""
        while not self._shutdown_event.is_set():
            try:
                # Check for changes and broadcast if any
                has_changes = await self.status_gatherer.check_for_changes()
                if has_changes and self.ws_manager:
                    status = await self.status_gatherer.get_full_status()
                    await self.ws_manager.broadcast_status_update(status)

            except Exception as e:
                logger.error(f"Error in file watcher: {e}")

            # Wait before next check
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=FILE_WATCH_INTERVAL
                )
            except asyncio.TimeoutError:
                pass  # Expected, continue watching

    async def stop(self) -> None:
        """Gracefully stop all server components."""
        logger.info("Shutting down dashboard server...")

        if self._shutdown_event:
            self._shutdown_event.set()

        # Cancel watch task
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket server
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()

        # Close HTTP server
        if self.http_server:
            self.http_server.close()
            await self.http_server.wait_closed()

        # Close all WebSocket connections
        if self.ws_manager:
            await self.ws_manager.close_all()

        logger.info("Dashboard server stopped.")

    async def run_forever(self) -> None:
        """Run the server until shutdown is requested."""
        await self.start()

        # Wait for shutdown event
        if self._shutdown_event:
            await self._shutdown_event.wait()


async def main():
    """Main entry point."""
    server = DashboardServer()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def signal_handler(sig):
        logger.info(f"Received signal {sig.name}, initiating shutdown...")
        asyncio.create_task(server.stop())

    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, partial(signal_handler, sig))

    try:
        await server.start()

        # Keep running until shutdown
        if server._shutdown_event:
            await server._shutdown_event.wait()

    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        await server.stop()


def run():
    """Entry point for running as a script or module."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise


if __name__ == '__main__':
    run()
