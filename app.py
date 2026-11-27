import sys

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaze_tracking.gaze_tracking import GazeTracking
from supervisor_client import SupervisorClient
from supervisor_protocol import DIRECTION_LABELS, SUPERVISOR_URL, VIDEO_SIZE

CAMERA_INDEX = 0
FRAME_INTERVAL_MS = 15  # intervalo entre leituras da câmera (~60 fps no máximo)


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Detector Ocular de Fraude em Prova")

        self.gaze = None  # criado apenas ao ligar a câmera (carrega o modelo dlib)
        self.capture = None
        self.running = False

        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_INTERVAL_MS)
        self.timer.timeout.connect(self._update_frame)

        self.supervisor = SupervisorClient(self)
        self.supervisor.connection_changed.connect(self._update_supervisor_connection)

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Área de vídeo
        self.video_label = QLabel("Câmera desligada")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(*VIDEO_SIZE)
        self.video_label.setStyleSheet("background-color: #202020; color: #cccccc;")
        layout.addWidget(self.video_label, alignment=Qt.AlignCenter)

        # Informações do rastreamento
        self.status_label = QLabel("Aguardando...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Botões
        buttons = QHBoxLayout()
        self.camera_button = QPushButton("Ligar câmera")
        self.camera_button.clicked.connect(self.toggle_camera)
        buttons.addWidget(self.camera_button)

        self.calibrate_button = QPushButton("Calibrar tela")
        self.calibrate_button.clicked.connect(self.start_screen_calibration)
        buttons.addWidget(self.calibrate_button)
        layout.addLayout(buttons)

        connection = QHBoxLayout()
        address_label = QLabel("Endereço do supervisor")
        self.supervisor_address = QLineEdit(SUPERVISOR_URL)
        address_label.setBuddy(self.supervisor_address)
        self.connection_button = QPushButton("Conectar")
        self.connection_button.clicked.connect(self._toggle_supervisor_connection)
        connection.addWidget(address_label)
        connection.addWidget(self.supervisor_address, stretch=1)
        connection.addWidget(self.connection_button)
        layout.addLayout(connection)

        self.connection_label = QLabel("Desconectado do supervisor.")
        self.connection_label.setAlignment(Qt.AlignCenter)
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)

    def _toggle_supervisor_connection(self):
        self.supervisor.toggle_connection(self.supervisor_address.text())

    def _update_supervisor_connection(self, connecting_or_connected, message):
        self.supervisor_address.setReadOnly(connecting_or_connected)
        self.connection_button.setText(
            "Desconectar" if connecting_or_connected else "Conectar"
        )
        self.connection_label.setText(message)

    # -------------------------------------------------------------- câmera
    def toggle_camera(self):
        if self.running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        capture = cv2.VideoCapture(CAMERA_INDEX)
        if not capture.isOpened():
            capture.release()
            QMessageBox.critical(self, "Erro", "Não foi possível acessar a câmera.")
            return

        if self.gaze is None:
            self.gaze = GazeTracking()

        self.capture = capture
        self.running = True
        self.camera_button.setText("Desligar câmera")
        self.supervisor.set_status(True)
        self.timer.start()

    def stop_camera(self):
        self.running = False
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.video_label.clear()
        self.video_label.setText("Câmera desligada")
        self.status_label.setText("Aguardando...")
        self.camera_button.setText("Ligar câmera")
        self.supervisor.set_status(False)

    def _update_frame(self):
        ok, frame = self.capture.read()
        if not ok:
            self.stop_camera()
            QMessageBox.critical(self, "Erro", "Falha ao ler imagem da câmera.")
            return

        self.gaze.refresh(frame)
        annotated = self.gaze.annotated_frame()
        direction, description = self._gaze_status()
        self.status_label.setText(description)

        height, width = annotated.shape[:2]
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, width, height, 3 * width, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

        self.supervisor.publish_frame(annotated, direction)

    REGION_LABELS = {
        "left": "esquerda",
        "right": "direita",
        "up": "cima",
        "down": "baixo",
        "center": "centro",
    }

    def _gaze_status(self):
        if self.gaze.is_blinking():
            return "blinking", DIRECTION_LABELS["blinking"]

        region = self.gaze.gaze_region()
        if region is None:
            return "not_detected", DIRECTION_LABELS["not_detected"]

        horizontal, vertical = region
        yaw, pitch = self.gaze.gaze_angles()
        pose = self.gaze.head_pose
        description = (
            f"Olhando para: {self.REGION_LABELS[horizontal]} / {self.REGION_LABELS[vertical]}"
            f"  (olhar: {yaw:+.0f}° / {pitch:+.0f}° | cabeça: {pose.yaw:+.0f}° / {pose.pitch:+.0f}°)"
        )
        return horizontal, description

    # ----------------------------------------------------------- calibração
    def start_screen_calibration(self):
        # conectar à calibração do tamanho da tela e às etapas de calibração quando o povo fizer
        QMessageBox.information(
            self, "Calibrar tela", "Ainda tem que implementar :( :("
        )

    # ------------------------------------------------------------- encerrar
    def closeEvent(self, event):
        self.stop_camera()
        self.supervisor.disconnect_from_supervisor()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
