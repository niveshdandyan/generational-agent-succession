#!/usr/bin/env python3
"""
HTTP Request Handler
====================
Asyncio-based HTTP server for serving static files and API endpoints.
"""
import asyncio
import json
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .gas_status import GASStatusGatherer
    from .websocket_handler import WebSocketManager

logger = logging.getLogger(__name__)

# Content types for common file extensions
CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
}

# Server start time for uptime tracking
SERVER_START_TIME = datetime.utcnow()


def get_content_type(file_path: str) -> str:
    """Get content type for a file based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return CONTENT_TYPES.get(ext, 'application/octet-stream')


class HTTPRequestHandler:
    """
    Handle HTTP requests asynchronously.
    """

    def __init__(
        self,
        status_gatherer: 'GASStatusGatherer',
        ws_manager: Optional['WebSocketManager'] = None,
        frontend_dir: Optional[str] = None
    ):
        self.status_gatherer = status_gatherer
        self.ws_manager = ws_manager

        # Determine frontend directory
        if frontend_dir:
            self.frontend_dir = Path(frontend_dir)
        else:
            # Default to frontend/ next to server/
            server_dir = Path(__file__).parent
            self.frontend_dir = server_dir.parent / 'frontend'

    async def handle_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: bytes = b''
    ) -> Tuple[int, Dict[str, str], bytes]:
        """
        Handle an HTTP request and return (status_code, headers, body).
        """
        # Route the request
        if path == '/' or path == '/index.html':
            return await self._serve_index()
        elif path == '/health':
            return await self._handle_health()
        elif path == '/api/status':
            return await self._handle_api_status()
        elif path.startswith('/api/agent/'):
            agent_id = path.split('/api/agent/')[-1].rstrip('/')
            return await self._handle_api_agent(agent_id)
        elif path == '/api/events':
            return await self._handle_api_events()
        elif path.startswith('/'):
            return await self._serve_static(path)
        else:
            return self._not_found()

    async def _serve_index(self) -> Tuple[int, Dict[str, str], bytes]:
        """Serve the main index.html page."""
        index_path = self.frontend_dir / 'index.html'

        if index_path.exists():
            try:
                content = index_path.read_bytes()
                return (
                    200,
                    {'Content-Type': 'text/html; charset=utf-8'},
                    content
                )
            except Exception as e:
                logger.error(f"Error reading index.html: {e}")
                return self._internal_error(str(e))

        # Return a placeholder if frontend not yet available
        placeholder = self._get_placeholder_html()
        return (
            200,
            {'Content-Type': 'text/html; charset=utf-8'},
            placeholder.encode('utf-8')
        )

    async def _serve_static(self, path: str) -> Tuple[int, Dict[str, str], bytes]:
        """Serve static files from the frontend directory."""
        # Sanitize path to prevent directory traversal
        safe_path = path.lstrip('/').replace('..', '')
        file_path = self.frontend_dir / safe_path

        if not file_path.exists() or not file_path.is_file():
            return self._not_found()

        # Check that path is within frontend directory
        try:
            file_path.resolve().relative_to(self.frontend_dir.resolve())
        except ValueError:
            return self._not_found()

        try:
            content = file_path.read_bytes()
            content_type = get_content_type(str(file_path))
            return (
                200,
                {
                    'Content-Type': content_type,
                    'Cache-Control': 'public, max-age=3600'
                },
                content
            )
        except Exception as e:
            logger.error(f"Error serving static file {file_path}: {e}")
            return self._internal_error(str(e))

    async def _handle_health(self) -> Tuple[int, Dict[str, str], bytes]:
        """Handle /health endpoint."""
        uptime_seconds = (datetime.utcnow() - SERVER_START_TIME).total_seconds()

        health_data = {
            'status': 'healthy',
            'uptime_seconds': round(uptime_seconds, 2),
            'server_start': SERVER_START_TIME.isoformat() + 'Z',
            'websocket_connections': (
                self.ws_manager.connection_count
                if self.ws_manager else 0
            ),
        }

        return self._json_response(health_data)

    async def _handle_api_status(self) -> Tuple[int, Dict[str, str], bytes]:
        """Handle /api/status endpoint - return full GAS status."""
        try:
            status = await self.status_gatherer.get_full_status()
            return self._json_response(status)
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return self._internal_error(str(e))

    async def _handle_api_agent(self, agent_id: str) -> Tuple[int, Dict[str, str], bytes]:
        """Handle /api/agent/{id} endpoint - return agent details."""
        try:
            agent_data = await self.status_gatherer.get_agent_details(agent_id)
            if agent_data is None:
                return self._not_found(f"Agent '{agent_id}' not found")
            return self._json_response(agent_data)
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}")
            return self._internal_error(str(e))

    async def _handle_api_events(self) -> Tuple[int, Dict[str, str], bytes]:
        """Handle /api/events endpoint - return recent live events."""
        try:
            events = await self.status_gatherer.get_recent_events()
            return self._json_response({'events': events})
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return self._internal_error(str(e))

    def _json_response(
        self,
        data: Any,
        status_code: int = 200
    ) -> Tuple[int, Dict[str, str], bytes]:
        """Create a JSON response."""
        content = json.dumps(data, indent=2, default=str)
        return (
            status_code,
            {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'no-cache'
            },
            content.encode('utf-8')
        )

    def _not_found(self, message: str = 'Not Found') -> Tuple[int, Dict[str, str], bytes]:
        """Return a 404 response."""
        return self._json_response({'error': message}, 404)

    def _internal_error(self, message: str) -> Tuple[int, Dict[str, str], bytes]:
        """Return a 500 response."""
        return self._json_response({'error': message}, 500)

    def _get_placeholder_html(self) -> str:
        """Return placeholder HTML when frontend is not yet available."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GAS Dashboard - Loading</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(180deg, #F9F6F1 0%, #F0EEE7 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #111827;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-family: 'Georgia', serif;
            font-size: 2.5rem;
            margin-bottom: 1rem;
        }
        p {
            color: #6b7280;
            margin-bottom: 1rem;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #e5e7eb;
            border-top-color: #FF6B4A;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 1rem auto;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .status {
            font-family: monospace;
            background: #fff;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>GAS Dashboard</h1>
        <p>Frontend files are still being generated...</p>
        <div class="spinner"></div>
        <div class="status">
            <p>API Status: <span id="status">Checking...</span></p>
        </div>
    </div>
    <script>
        async function checkStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('status').textContent =
                    data.swarm_name || 'Connected';
            } catch (e) {
                document.getElementById('status').textContent = 'Error: ' + e.message;
            }
        }
        checkStatus();
        setInterval(checkStatus, 5000);
    </script>
</body>
</html>'''


class AsyncHTTPServer:
    """
    Asyncio-based HTTP server.
    """

    def __init__(
        self,
        handler: HTTPRequestHandler,
        host: str = '0.0.0.0',
        port: int = 8080
    ):
        self.handler = handler
        self.host = host
        self.port = port
        self._server = None

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single client connection."""
        try:
            # Read request line
            request_line = await asyncio.wait_for(
                reader.readline(),
                timeout=30.0
            )
            if not request_line:
                return

            request_line = request_line.decode('utf-8', errors='replace').strip()
            parts = request_line.split(' ')
            if len(parts) < 2:
                return

            method = parts[0]
            path = parts[1].split('?')[0]  # Remove query string

            # Read headers
            headers = {}
            while True:
                header_line = await asyncio.wait_for(
                    reader.readline(),
                    timeout=10.0
                )
                if not header_line or header_line == b'\r\n':
                    break
                header_line = header_line.decode('utf-8', errors='replace').strip()
                if ':' in header_line:
                    key, value = header_line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Read body if present
            body = b''
            content_length = int(headers.get('content-length', 0))
            if content_length > 0:
                body = await asyncio.wait_for(
                    reader.read(content_length),
                    timeout=30.0
                )

            # Handle the request
            status_code, response_headers, response_body = await self.handler.handle_request(
                method, path, headers, body
            )

            # Send response
            status_text = {
                200: 'OK',
                404: 'Not Found',
                500: 'Internal Server Error',
            }.get(status_code, 'Unknown')

            response_lines = [f'HTTP/1.1 {status_code} {status_text}']
            response_headers['Content-Length'] = str(len(response_body))
            response_headers['Connection'] = 'close'
            response_headers['Access-Control-Allow-Origin'] = '*'

            for key, value in response_headers.items():
                response_lines.append(f'{key}: {value}')

            response_lines.append('')
            response_header = '\r\n'.join(response_lines) + '\r\n'

            writer.write(response_header.encode('utf-8'))
            writer.write(response_body)
            await writer.drain()

        except asyncio.TimeoutError:
            logger.debug("Client connection timeout")
        except ConnectionResetError:
            logger.debug("Client connection reset")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> asyncio.Server:
        """Start the HTTP server."""
        self._server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
            reuse_address=True
        )
        return self._server

    def close(self) -> None:
        """Close the server."""
        if self._server:
            self._server.close()

    async def wait_closed(self) -> None:
        """Wait for server to close."""
        if self._server:
            await self._server.wait_closed()


async def create_http_server(
    host: str,
    port: int,
    status_gatherer: 'GASStatusGatherer',
    ws_manager: Optional['WebSocketManager'] = None,
    frontend_dir: Optional[str] = None
) -> AsyncHTTPServer:
    """
    Create and start an HTTP server.
    Returns the server instance.
    """
    handler = HTTPRequestHandler(
        status_gatherer=status_gatherer,
        ws_manager=ws_manager,
        frontend_dir=frontend_dir
    )

    server = AsyncHTTPServer(handler, host, port)
    await server.start()
    return server
