"""Remote control TCP server for ICM2 ECG Recorder.

Allows a remote computer on the same LAN to control CSV recording
via simple text commands over TCP.

Protocol:
  AUTH:<token>\\n       — authenticate (must be first command)
  START_CSV\\n          — start CSV recording
  STOP_CSV\\n           — stop CSV recording
  DISCONNECT\\n         — disconnect cleanly

Constants (edit to configure):
  TCP_PORT   = 9527
  AUTH_TOKEN = "icm2024"
"""

import logging
import socket
import threading

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

TCP_PORT = 9527
AUTH_TOKEN = "icm2024"

_RECV_TIMEOUT = 1.0   # seconds — lets recv loop notice _running=False promptly
_ACCEPT_TIMEOUT = 1.0  # seconds — lets accept loop notice _running=False


class RemoteControlServer(QObject):
    """TCP server that emits Qt signals when remote commands are received.

    Signals are emitted from a background daemon thread; PyQt5 queues
    delivery to the Qt main thread automatically.
    """

    remote_connected = pyqtSignal()
    remote_disconnected = pyqtSignal()
    start_recording_requested = pyqtSignal()
    stop_recording_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server_sock: socket.socket | None = None
        self._client_sock: socket.socket | None = None
        self._client_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind TCP port and start the accept loop in a daemon thread.

        If the port is already in use (OSError) the error is logged as a
        warning and the server simply does not start — it does NOT crash.
        """
        if self._running:
            return

        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("", TCP_PORT))
            server.listen(1)
            server.settimeout(_ACCEPT_TIMEOUT)
            self._server_sock = server
        except OSError as exc:
            logger.warning("RemoteControlServer: cannot bind port %d — %s", TCP_PORT, exc)
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="RemoteServerThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("RemoteControlServer: listening on port %d", TCP_PORT)

    def stop(self) -> None:
        """Stop the server and close all sockets."""
        self._running = False

        # Close client socket first so the recv loop unblocks
        with self._client_lock:
            if self._client_sock is not None:
                try:
                    self._client_sock.close()
                except OSError:
                    pass
                self._client_sock = None

        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

        logger.info("RemoteControlServer: stopped")

    # ------------------------------------------------------------------
    # Internal — accept loop (daemon thread)
    # ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        """Wait for incoming connections while self._running is True."""
        server = self._server_sock
        if server is None:
            return
        while self._running:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue  # check _running flag and retry
            except OSError:
                break  # server socket was closed by stop()

            logger.debug("RemoteControlServer: incoming connection from %s", addr)

            # Only one client at a time — reject if already connected
            with self._client_lock:
                already_connected = self._client_sock is not None

            if already_connected:
                logger.warning(
                    "RemoteControlServer: rejecting %s — already have a client", addr
                )
                try:
                    conn.close()
                except OSError:
                    pass
                continue

            # Handle client in this same thread (blocking; one client at a time)
            self._handle_client(conn)

        logger.debug("RemoteControlServer: accept loop exited")

    # ------------------------------------------------------------------
    # Internal — client handler
    # ------------------------------------------------------------------

    def _handle_client(self, conn: socket.socket) -> None:
        """Authenticate then process commands from a single client."""
        conn.settimeout(_RECV_TIMEOUT)

        with self._client_lock:
            self._client_sock = conn

        try:
            # --- Auth phase ---
            raw = self._recv_line(conn)
            if raw is None:
                # Connection dropped before auth
                logger.debug("RemoteControlServer: client disconnected before auth")
                return

            if raw != f"AUTH:{AUTH_TOKEN}":
                logger.warning("RemoteControlServer: auth failed (got %r), closing", raw)
                return

            logger.info("RemoteControlServer: client authenticated")
            self.remote_connected.emit()

            # --- Command loop ---
            while self._running:
                raw = self._recv_line(conn)

                if raw is None:
                    # recv() returned empty bytes → client disconnected
                    logger.info("RemoteControlServer: client disconnected")
                    self.remote_disconnected.emit()
                    return

                if raw == "START_CSV":
                    logger.info("RemoteControlServer: START_CSV received")
                    self.start_recording_requested.emit()
                elif raw == "STOP_CSV":
                    logger.info("RemoteControlServer: STOP_CSV received")
                    self.stop_recording_requested.emit()
                elif raw == "DISCONNECT":
                    logger.info("RemoteControlServer: DISCONNECT received")
                    self.remote_disconnected.emit()
                    return
                else:
                    # Malformed / unknown command — ignore, keep connection
                    logger.debug("RemoteControlServer: unknown command %r, ignoring", raw)

        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self._client_lock:
                if self._client_sock is conn:
                    self._client_sock = None

    def _recv_line(self, conn: socket.socket) -> str | None:
        """Read bytes until newline, stripping whitespace.

        Returns:
            Stripped string if data received.
            None if the connection was closed (recv returned b"").
            Timeout loops internally until _running is False.
        """
        buf = b""
        while self._running:
            try:
                chunk = conn.recv(256)
            except socket.timeout:
                continue  # check _running and retry
            except OSError:
                return None  # connection reset / broken pipe

            if not chunk:
                return None  # peer closed connection

            buf += chunk
            if b"\n" in buf:
                line, _, _ = buf.partition(b"\n")
                return line.decode("utf-8", errors="replace").strip()

        return None  # _running became False
