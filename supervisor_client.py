from time import monotonic

import cv2
from PySide6.QtCore import QByteArray, QObject, Qt, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket

from supervisor_protocol import VIDEO_SIZE, encode_status


FRAME_INTERVAL = 0.1
JPEG_QUALITY = 75
MAX_QUEUED_STATUS_BYTES = 64 * 1024


class SupervisorClient(QObject):
    connection_changed = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._socket = None
        self._status = (False, None)
        self._sent_status = None
        self._next_frame_at = 0

    def toggle_connection(self, address):
        if self._socket is not None:
            self.disconnect_from_supervisor()
            return

        url = QUrl(address.strip(), QUrl.ParsingMode.StrictMode)
        if not url.isValid() or url.scheme() != "ws" or not url.host():
            self.connection_changed.emit(False, "Endereço WebSocket inválido.")
            return

        socket = QWebSocket(parent=self)
        self._socket = socket
        socket.connected.connect(lambda: self._on_connected(socket))
        # Qt can emit disconnected before reporting the error of a failed connection.
        socket.disconnected.connect(
            lambda: self._on_disconnected(socket), Qt.ConnectionType.QueuedConnection
        )
        socket.errorOccurred.connect(lambda _error: self._on_error(socket))
        socket.bytesWritten.connect(self._flush_status)
        self.connection_changed.emit(True, "Conectando ao supervisor…")
        socket.open(url)

    def disconnect_from_supervisor(self):
        if self._socket is not None:
            self._close_socket("Desconectado do supervisor.")

    def set_status(self, camera_active, direction=None):
        self._status = (camera_active, direction)
        self._flush_status()

    def publish_frame(self, frame, direction):
        socket = self._socket
        has_backlog = socket is not None and socket.bytesToWrite() > 0
        self.set_status(True, direction)

        if socket is None or socket.state() != QAbstractSocket.SocketState.ConnectedState:
            return

        now = monotonic()
        if now < self._next_frame_at or has_backlog:
            return
        self._next_frame_at = now + FRAME_INTERVAL

        height, width = frame.shape[:2]
        scale = min(VIDEO_SIZE[0] / width, VIDEO_SIZE[1] / height)
        if scale < 1:
            size = (max(1, round(width * scale)), max(1, round(height * scale)))
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if ok:
            socket.sendBinaryMessage(QByteArray(jpeg.tobytes()))

    def _flush_status(self):
        socket = self._socket
        if socket is None or socket.state() != QAbstractSocket.SocketState.ConnectedState:
            return
        if self._status == self._sent_status or socket.bytesToWrite() >= MAX_QUEUED_STATUS_BYTES:
            return
        # Keep only the latest unsent state while the socket output is congested.
        self._sent_status = self._status
        socket.sendTextMessage(encode_status(*self._status))

    def _on_connected(self, socket):
        if socket is self._socket:
            self._sent_status = None
            self._next_frame_at = 0
            self._flush_status()
            self.connection_changed.emit(True, "Conectado ao supervisor.")

    def _on_disconnected(self, socket):
        if socket is self._socket:
            reason = socket.closeReason()
            message = "Conexão com o supervisor encerrada."
            if reason:
                message = f"{message} {reason}"
            self._close_socket(message)

    def _on_error(self, socket):
        if socket is self._socket:
            self._close_socket(f"Erro na conexão com o supervisor: {socket.errorString()}")

    def _close_socket(self, message):
        socket = self._socket
        self._socket = None
        socket.close()
        socket.deleteLater()
        self.connection_changed.emit(False, message)
