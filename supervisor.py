import sys

from PySide6.QtCore import QTime
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QListWidget, QWidget

from ocular_ui import Card, State, Workspace, action, heading, video_card
from supervisor_protocol import DIRECTION_LABELS
from supervisor_server import SupervisorServer


HISTORY_LIMIT = 100


class SupervisorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._camera_active = False
        self._direction = None

        self.server = SupervisorServer(self)
        self.server.connection_changed.connect(self._update_connection)
        self.server.status_received.connect(self._update_status)
        self.server.frame_received.connect(self._show_frame)

        self._build_ui()

    def _build_ui(self):
        self.workspace = Workspace(self, "Painel de supervisão", "Supervisor")
        video, self.video_label = video_card("Transmissão do participante", "Sem vídeo")
        self.server_button = action("Iniciar servidor", "connection", primary=True)
        self.server_button.clicked.connect(self.server.toggle_server)
        video.body.addWidget(self.server_button)

        events = Card("Monitoramento e eventos", "history")
        self.connection_state = State("Conexão", "Servidor parado", "connection")
        self.connection_label = self.connection_state.value
        self.camera_state = State("Câmera do participante", "Indisponível", "camera")
        self.direction_state = State("Direção do olhar", "Indisponível", "eye")
        for state in (self.connection_state, self.camera_state, self.direction_state):
            events.body.addWidget(state)

        events.body.addWidget(heading("Histórico de eventos", "sectionLabel"))
        self.history = QListWidget()
        self.history.setAccessibleName("Histórico de eventos")
        self.history.setMinimumHeight(120)
        events.body.addWidget(self.history, 1)
        self.workspace.set_panels(video, events)

    def _update_connection(self, listening, connected, message):
        tone = "positive" if connected else "progress" if listening else "neutral"
        if message.startswith("Erro"):
            tone = "notice"
        self.connection_state.set_state(message, tone)
        self.server_button.setText("Parar servidor" if listening else "Iniciar servidor")
        self._camera_active = False
        self._direction = None
        self.video_label.setText("Aguardando estado da câmera" if connected else "Sem vídeo")
        self.direction_state.set_state("Indisponível")
        self.camera_state.set_state(
            "Aguardando estado" if connected else "Indisponível",
            "progress" if connected else "neutral",
        )

    def _update_status(self, camera_active, direction):
        if not camera_active:
            self.video_label.setText("Câmera desligada")
        elif not self._camera_active:
            self.video_label.setText("Aguardando vídeo")
        self._camera_active = camera_active
        self.camera_state.set_state(
            "Ligada" if camera_active else "Desligada",
            "positive" if camera_active else "neutral",
        )

        description = DIRECTION_LABELS.get(direction, "Direção indisponível")
        tone = "notice" if direction == "not_detected" else "neutral"
        self.direction_state.set_state(description, tone)
        if direction is not None and direction != self._direction:
            time = QTime.currentTime().toString("HH:mm:ss")
            self.history.addItem(f"{time}  {description}")
            if self.history.count() > HISTORY_LIMIT:
                self.history.takeItem(0)
            self.history.scrollToBottom()
        self._direction = direction

    def _show_frame(self, jpeg):
        if not self._camera_active:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(jpeg, "JPEG"):
            self.video_label.set_frame(pixmap)

    def closeEvent(self, event):
        self.server.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = SupervisorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
