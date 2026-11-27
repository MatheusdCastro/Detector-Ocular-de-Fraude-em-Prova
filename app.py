import sys

import cv2
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from gaze_tracking.gaze_tracking import GazeTracking
from ocular_ui import Card, State, Workspace, action, video_card
from screen_calibration import CalibrationOverlay
from supervisor_client import SupervisorClient
from supervisor_protocol import DIRECTION_LABELS, SUPERVISOR_URL

CAMERA_INDEX = 0
FRAME_INTERVAL_MS = 15  # intervalo entre leituras da câmera (~60 fps no máximo)


class App(QWidget):
    def __init__(self):
        super().__init__()

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
        self.workspace = Workspace(self, "Monitoramento", "Participante")
        camera, self.video_label = video_card("Prévia da câmera", "Câmera desligada")
        self.camera_button = action("Ligar câmera", "camera", primary=True)
        self.camera_button.clicked.connect(self.toggle_camera)
        camera.body.addWidget(self.camera_button)

        monitor = Card("Estado do monitoramento", "eye")
        self.camera_state = State("Câmera", "Desligada", "camera")
        self.calibration_state = State("Calibração", "Não realizada", "target")
        self.gaze_state = State("Direção do olhar", "Aguardando câmera", "eye")
        self.connection_state = State(
            "Conexão com o supervisor", "Desconectado do supervisor.", "connection"
        )
        self.connection_label = self.connection_state.value
        for state in (self.camera_state, self.calibration_state, self.gaze_state,
                      self.connection_state):
            monitor.body.addWidget(state)

        self.calibrate_button = action("Calibrar tela", "target")
        self.calibrate_button.clicked.connect(self.start_screen_calibration)
        self.calibration_state.layout().addWidget(self.calibrate_button)

        address_label = QLabel("Endereço do supervisor")
        address_label.setObjectName("sectionLabel")
        self.supervisor_address = QLineEdit(SUPERVISOR_URL)
        address_label.setBuddy(self.supervisor_address)
        self.connection_button = action("Conectar", "connection", primary=True)
        self.connection_button.clicked.connect(self._toggle_supervisor_connection)
        for control in (address_label, self.supervisor_address, self.connection_button):
            self.connection_state.layout().addWidget(control)

        monitor.body.addStretch()
        self.workspace.set_panels(camera, monitor)

    def _toggle_supervisor_connection(self):
        self.supervisor.toggle_connection(self.supervisor_address.text())

    def _update_supervisor_connection(self, connecting_or_connected, message):
        self.supervisor_address.setReadOnly(connecting_or_connected)
        self.connection_button.setText(
            "Desconectar" if connecting_or_connected else "Conectar"
        )
        tone = "neutral"
        if connecting_or_connected:
            tone = "positive" if message == "Conectado ao supervisor." else "progress"
        elif message.startswith(("Erro", "Endereço")):
            tone = "notice"
        self.connection_state.set_state(message, tone)

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
            self.camera_state.set_state("Câmera indisponível", "notice")
            QMessageBox.critical(self, "Erro", "Não foi possível acessar a câmera.")
            return

        if self.gaze is None:
            self.gaze = GazeTracking()

        self.capture = capture
        self.running = True
        self.camera_button.setText("Desligar câmera")
        self.camera_state.set_state("Ligada", "positive")
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
        self.camera_state.set_state("Desligada")
        self.gaze_state.set_state("Aguardando câmera")
        self.camera_button.setText("Ligar câmera")
        self.supervisor.set_status(False)

    def _update_frame(self):
        ok, frame = self.capture.read()
        if not ok:
            self.stop_camera()
            self.camera_state.set_state("Falha de leitura", "notice")
            QMessageBox.critical(self, "Erro", "Falha ao ler imagem da câmera.")
            return

        self.gaze.refresh(frame)
        annotated = self.gaze.annotated_frame()
        direction, description = self._gaze_status()
        tone = "notice" if direction == "not_detected" else "neutral"
        self.gaze_state.set_state(description, tone)

        height, width = annotated.shape[:2]
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, width, height, 3 * width, QImage.Format_RGB888)
        self.video_label.set_frame(QPixmap.fromImage(image))

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
        """Abre a tela de calibração fullscreen com pontos de referência."""
        if self.gaze is None:
            self.gaze = GazeTracking()

        # Abrir câmera se necessário
        self._cal_opened_camera = False
        if self.capture is None or not self.capture.isOpened():
            capture = cv2.VideoCapture(CAMERA_INDEX)
            if not capture.isOpened():
                capture.release()
                QMessageBox.critical(self, "Erro", "Não foi possível acessar a câmera.")
                return
            self.capture = capture
            self._cal_opened_camera = True

        # Pausar o loop principal durante a calibração
        self._cal_was_running = self.running
        self.running = False
        self.timer.stop()

        # Abrir a tela de calibração
        overlay = CalibrationOverlay(self.gaze, self.capture)
        overlay.finished.connect(self._on_calibration_done)
        self._calibration_overlay = overlay
        self._prior_calibration_text = self.calibration_state.value.text()
        self._prior_calibration_tone = self.calibration_state.value.property("tone")
        self.calibration_state.set_state("Em andamento", "progress")
        overlay.start()

    def _on_calibration_done(self, data):
        """Aplica os resultados da calibração ao GazeTracking."""
        if data is not None:
            # Aplicar offsets do centro (corrige o ponto zero)
            self.gaze._yaw_offset = data["offsets"]["yaw"]
            self.gaze._pitch_offset = data["offsets"]["pitch"]
            # Aplicar limiares calibrados
            self.gaze.HORIZONTAL_THRESHOLD_DEG = data["thresholds"]["horizontal"]
            self.gaze.VERTICAL_THRESHOLD_DEG = data["thresholds"]["vertical"]

            acc = data["verificacao"]["acuracia"]
            self.calibration_state.set_state(f"Aplicada · cobertura {acc:.0%}", "positive")
            h_t = data["thresholds"]["horizontal"]
            v_t = data["thresholds"]["vertical"]
            msg = (
                "Calibração aplicada!\n\n"
                "Cobertura da tela: {:.0%}\n"
                "Borda horizontal: {:.1f}°\n"
                "Borda vertical: {:.1f}°"
            ).format(acc, h_t, v_t)
            QMessageBox.information(self, "Calibração", msg)
        else:
            self.calibration_state.set_state(
                self._prior_calibration_text, self._prior_calibration_tone
            )

        # Retomar câmera se estava ligada, ou liberar se foi aberta só para calibrar
        if self._cal_was_running:
            self.running = True
            self.timer.start()
        elif self._cal_opened_camera:
            self.capture.release()
            self.capture = None

        self._calibration_overlay = None

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
