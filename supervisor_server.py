from PySide6.QtCore import QByteArray, QObject, Signal, Slot
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocketProtocol, QWebSocketServer

from supervisor_protocol import SUPERVISOR_HOST, SUPERVISOR_PORT, decode_status


class SupervisorServer(QObject):
    connection_changed = Signal(bool, bool, str)
    status_received = Signal(bool, object)
    frame_received = Signal(QByteArray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server = QWebSocketServer(
            "Supervisor", QWebSocketServer.SslMode.NonSecureMode, self
        )
        self._server.newConnection.connect(self._accept_connections)
        self._client = None

    def toggle_server(self):
        if self._server.isListening():
            self.stop()
        else:
            self.start()

    def start(self):
        if self._server.listen(QHostAddress(SUPERVISOR_HOST), SUPERVISOR_PORT):
            self.connection_changed.emit(True, False, "Aguardando usuário")
        else:
            self.connection_changed.emit(
                False, False, f"Erro ao iniciar servidor: {self._server.errorString()}"
            )

    def stop(self):
        self._server.close()
        if self._client is not None:
            client = self._client
            self._client = None
            client.close(QWebSocketProtocol.CloseCode.CloseCodeGoingAway, "Servidor parado.")
            client.deleteLater()
        self.connection_changed.emit(False, False, "Servidor parado")

    def _accept_connections(self):
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            client.setParent(self)
            if self._client is not None:
                client.close(
                    QWebSocketProtocol.CloseCode.CloseCodePolicyViolated, "Supervisor ocupado."
                )
                client.deleteLater()
                continue

            self._client = client
            client.disconnected.connect(self._on_disconnected)
            client.textMessageReceived.connect(self._receive_status)
            client.binaryMessageReceived.connect(self.frame_received)
            self.connection_changed.emit(True, True, "Usuário conectado")

    @Slot()
    def _on_disconnected(self):
        client = self.sender()
        if self._client is not None and client is self._client:
            self._client = None
            client.deleteLater()
            self.connection_changed.emit(True, False, "Usuário desconectado. Aguardando usuário")

    def _receive_status(self, message):
        status = decode_status(message)
        if status is not None:
            self.status_received.emit(*status)
