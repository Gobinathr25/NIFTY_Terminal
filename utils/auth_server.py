"""
Local OAuth2 callback server.
Starts a temporary HTTP server on localhost that captures the Fyers
auth_code automatically from the redirect URL — no manual copy-pasting.

Usage:
    token = run_local_auth_flow(client_id, secret_key, redirect_url)

The redirect URL in your Fyers API portal should be set to:
    http://127.0.0.1:8085/callback
"""

from __future__ import annotations
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Optional
import time

from utils.logger import get_logger

log = get_logger(__name__)

LOCAL_PORT     = 8085
CALLBACK_PATH  = "/callback"
LOCAL_REDIRECT = f"http://127.0.0.1:{LOCAL_PORT}{CALLBACK_PATH}"

# Shared state between server thread and main thread
_auth_code: Optional[str] = None
_server_done = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    """Handles the single redirect from Fyers after login."""

    def do_GET(self):
        global _auth_code
        parsed = urlparse(self.path)
        if parsed.path == CALLBACK_PATH:
            params = parse_qs(parsed.query)
            code = params.get("auth_code", [None])[0] or params.get("code", [None])[0]
            if code:
                _auth_code = code
                log.info("Auth code captured automatically.")
                self._respond(200, "✅ Auth code captured! You can close this tab and return to the app.")
            else:
                self._respond(400, "❌ No auth_code in URL. Please try again.")
        else:
            self._respond(404, "Not found")
        _server_done.set()

    def _respond(self, status: int, message: str) -> None:
        body = f"""
        <html><body style='font-family:sans-serif;text-align:center;padding:60px;'>
        <h2>{message}</h2>
        <p>Return to your <b>NIFTY Terminal</b> app.</p>
        </body></html>
        """.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # suppress server console output


def _start_server() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", LOCAL_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    return server


def capture_auth_code(timeout: int = 120) -> Optional[str]:
    """
    Start local server and wait up to `timeout` seconds for the redirect.
    Returns auth_code string or None on timeout.
    """
    global _auth_code, _server_done
    _auth_code = None
    _server_done.clear()

    _start_server()
    log.info("Local auth server started on %s", LOCAL_REDIRECT)

    _server_done.wait(timeout=timeout)
    return _auth_code


def run_local_auth_flow(client_id: str, secret_key: str) -> Optional[str]:
    """
    Full auto flow:
    1. Build auth URL using LOCAL_REDIRECT as redirect_uri
    2. Open browser
    3. Wait for callback
    4. Exchange code for access token
    5. Return access token

    Returns access_token or None on failure.
    """
    from data.fyers_client import FyersClient

    auth_url = FyersClient.generate_auth_url(client_id, LOCAL_REDIRECT, secret_key)
    log.info("Opening browser for Fyers login: %s", auth_url)
    webbrowser.open(auth_url)

    code = capture_auth_code(timeout=180)
    if not code:
        log.error("Auth code not received within timeout.")
        return None

    token = FyersClient.exchange_auth_code(client_id, secret_key, code)
    return token
