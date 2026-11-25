import sys

from PySide6.QtCore import QTime, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from supervisor_protocol import DIRECTION_LABELS, VIDEO_SIZE
from supervisor_server import SupervisorServer


HISTORY_LIMIT = 100


class SupervisorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Supervisor")
        self._camera_active = False
        self._direction = None

        self.server = SupervisorServer(self)
        self.server.connection_changed.connect(self._update_connection)
        self.server.status_received.connect(self._update_status)
        self.server.frame_received.connect(self._show_frame)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.video_label = QLabel("Sem vídeo")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(*VIDEO_SIZE)
        self.video_label.setStyleSheet("background-color: #202020; color: #cccccc;")
        layout.addWidget(self.video_label, alignment=Qt.AlignCenter)

        self.connection_label = QLabel("Servidor parado")
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)

        self.server_button = QPushButton("Iniciar servidor")
        self.server_button.clicked.connect(self.server.toggle_server)
        layout.addWidget(self.server_button)

        tabs = QTabWidget()
        notifications = QWidget()
        notification_layout = QVBoxLayout(notifications)
        self.direction_label = QLabel("Direção indisponível")
        notification_layout.addWidget(self.direction_label)
        self.history = QListWidget()
        self.history.setFixedHeight(100)
        notification_layout.addWidget(self.history)
        tabs.addTab(notifications, "Notificações")
        layout.addWidget(tabs)

    def _update_connection(self, listening, connected, message):
        self.connection_label.setText(message)
        self.server_button.setText("Parar servidor" if listening else "Iniciar servidor")
        self._camera_active = False
        self._direction = None
        self.video_label.setText("Aguardando estado da câmera" if connected else "Sem vídeo")
        self.direction_label.setText("Direção indisponível")

    def _update_status(self, camera_active, direction):
        if not camera_active:
            self.video_label.setText("Câmera desligada")
        elif not self._camera_active:
            self.video_label.setText("Aguardando vídeo")
        self._camera_active = camera_active

        description = DIRECTION_LABELS.get(direction, "Direção indisponível")
        self.direction_label.setText(description)
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
            self.video_label.setPixmap(pixmap)

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
