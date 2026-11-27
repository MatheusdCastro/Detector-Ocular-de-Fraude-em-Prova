"""
Calibração de tela — janela fullscreen com pontos de referência.

Adaptado do visual do demo_olhar (calibracao.py + interface.py) para PySide6,
usando o GazeTracking (dlib) do sistema principal.

Fluxo (para cada um dos 5 pontos):
  1. Preparo (2 s)      — o ponto acende; o usuário se prepara para olhar
  2. Captura (3 s)       — o sistema grava os ângulos do olhar (yaw, pitch)
  3. Verificação (2 s)   — quadros reservados para medir a acurácia

No fim calcula:
  • Médias de (yaw, pitch) por direção
  • Offset do centro (para corrigir o ponto zero do olhar)
  • Limiares ótimos para classificar esquerda/direita e cima/baixo
  • Acurácia medida nos quadros de verificação
"""

import time

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

# ── alvos (posições relativas na tela, x e y) ──────────────────────────────
TARGETS = {
    "centro":   (0.50, 0.50),
    "esquerda": (0.05, 0.50),
    "direita":  (0.95, 0.50),
    "cima":     (0.50, 0.08),
    "baixo":    (0.50, 0.92),
    "sup esq":  (0.05, 0.08),
    "sup dir":  (0.95, 0.08),
    "inf esq":  (0.05, 0.92),
    "inf dir":  (0.95, 0.92),
}

# Agrupamento por lado — usado para calcular limiares com mais amostras
LEFT_TARGETS = ("esquerda", "sup esq", "inf esq")
RIGHT_TARGETS = ("direita", "sup dir", "inf dir")
TOP_TARGETS = ("cima", "sup esq", "sup dir")
BOTTOM_TARGETS = ("baixo", "inf esq", "inf dir")



# ── fases e duração (segundos) ──────────────────────────────────────────────
PHASES = ("preparo", "captura", "verificacao")
PHASE_DURATIONS = (2.0, 3.0, 2.0)

# ── cores (RGB, Qt) ────────────────────────────────────────────────────────
BG      = QColor(9, 10, 47)
AREA    = QColor(0, 0, 0)
BORDER  = QColor(200, 182, 248)
WHITE   = QColor(255, 255, 255)
GREEN   = QColor(51, 209, 122)
GRAY    = QColor(120, 124, 160)
BLUE    = QColor(2, 182, 248)
AMBER   = QColor(245, 158, 11)
RED     = QColor(220, 38, 38)

PHASE_LABELS = {
    "preparo": "Prepare-se…",
    "captura": "Capturando…",
    "verificacao": "Verificando…",
}


class CalibrationOverlay(QWidget):
    """Janela fullscreen de calibração de tela com pontos de referência."""

    # Emitido ao fechar: dict com dados de calibração, ou None se cancelado.
    finished = Signal(object)

    def __init__(self, gaze, capture, parent=None):
        super().__init__(parent)
        self.gaze = gaze
        self.capture = capture

        # estado da calibração
        self.target_names = list(TARGETS.keys())
        self.current_target_idx = 0
        self.current_phase_idx = 0
        self.phase_start_time = 0.0

        self.samples = {n: [] for n in TARGETS}
        self.reserved = {n: [] for n in TARGETS}
        self.current_frame = None
        self.calibration_data = None
        self.mode = "calibrating"       # → "result"
        self._signal_emitted = False

        # timer de atualização (~33 fps)
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)

        self.setWindowTitle("Calibração de Tela")

    # ── controle ────────────────────────────────────────────────────────────
    def start(self):
        """Mostra a tela cheia e começa a calibração."""
        self.showFullScreen()
        self.phase_start_time = time.monotonic()
        self.timer.start()

    def _target(self):
        if self.current_target_idx < len(self.target_names):
            return self.target_names[self.current_target_idx]
        return None

    def _phase(self):
        return PHASES[self.current_phase_idx]

    # ── loop principal ──────────────────────────────────────────────────────
    def _tick(self):
        ok, frame = self.capture.read()
        if not ok:
            return

        self.gaze.refresh(frame)
        self.current_frame = frame

        if self.mode != "calibrating":
            self.update()
            return

        target = self._target()
        phase = self._phase()
        elapsed = time.monotonic() - self.phase_start_time

        if elapsed >= PHASE_DURATIONS[self.current_phase_idx]:
            self._advance()
        elif phase in ("captura", "verificacao"):
            if not self.gaze.is_blinking():
                angles = self.gaze.gaze_angles()
                if angles is not None:
                    sample = {"yaw": angles[0], "pitch": angles[1]}
                    if phase == "captura":
                        self.samples[target].append(sample)
                    else:
                        self.reserved[target].append(sample)

        self.update()

    def _advance(self):
        """Avança para a próxima fase ou próximo alvo."""
        self.current_phase_idx += 1
        if self.current_phase_idx >= len(PHASES):
            self.current_phase_idx = 0
            self.current_target_idx += 1
            if self.current_target_idx >= len(self.target_names):
                self._compute()
                return
        self.phase_start_time = time.monotonic()

    # ── cálculo da calibração ───────────────────────────────────────────────
    def _compute(self):
        """Calcula médias, offsets, limiares e acurácia."""
        if any(len(s) < 3 for s in self.samples.values()):
            self.calibration_data = None
            self.mode = "result"
            self.update()
            return

        # médias por direção
        medias = {}
        for name, lst in self.samples.items():
            medias[name] = {
                "yaw":   float(np.mean([s["yaw"]   for s in lst])),
                "pitch": float(np.mean([s["pitch"] for s in lst])),
            }

        # offset do centro (corrige o ponto zero)
        center_yaw = medias["centro"]["yaw"]
        center_pitch = medias["centro"]["pitch"]

        # limiares = distância real do centro às bordas da tela + margem
        # Assim o limiar representa a borda do monitor, não a metade da tela.
        # Só é classificado como "fora" quem olha ALÉM da tela.
        left_yaws = [medias[n]["yaw"] for n in LEFT_TARGETS]
        right_yaws = [medias[n]["yaw"] for n in RIGHT_TARGETS]
        top_pitches = [medias[n]["pitch"] for n in TOP_TARGETS]
        bottom_pitches = [medias[n]["pitch"] for n in BOTTOM_TARGETS]

        h_dists = [abs(y - center_yaw) for y in left_yaws + right_yaws]
        v_dists = [abs(p - center_pitch) for p in top_pitches + bottom_pitches]

        # Margem de tolerância (graus) para não disparar alarme na borda da tela
        MARGIN_DEG = 2.0
        h_thresh = max(3.0, float(np.mean(h_dists)) + MARGIN_DEG)
        v_thresh = max(2.0, float(np.mean(v_dists)) + MARGIN_DEG)

        verificacao = self._verify(center_yaw, center_pitch, h_thresh, v_thresh)

        self.calibration_data = {
            "medias": medias,
            "offsets": {"yaw": center_yaw, "pitch": center_pitch},
            "thresholds": {"horizontal": h_thresh, "vertical": v_thresh},
            "amostras": {n: len(s) for n, s in self.samples.items()},
            "verificacao": verificacao,
        }
        self.mode = "result"
        self.update()

    def _verify(self, center_yaw, center_pitch, h_thresh, v_thresh):
        """Mede a cobertura: verifica se os pontos na tela são detectados como
        'dentro da tela'. Se um ponto na borda aparece como 'fora', o limiar
        pode estar apertado demais e gerar falsos positivos de fraude."""
        por_direcao = {}
        total_ok = 0
        total_all = 0

        for name in self.reserved:
            acertos = 0
            total_ponto = 0
            for s in self.reserved[name]:
                yaw_corr = s["yaw"] - center_yaw
                pitch_corr = s["pitch"] - center_pitch
                dentro = abs(yaw_corr) <= h_thresh and abs(pitch_corr) <= v_thresh
                if dentro:
                    acertos += 1
                total_ponto += 1

            por_direcao[name] = float(acertos / max(total_ponto, 1))
            total_ok += acertos
            total_all += total_ponto

        return {
            "acuracia": float(total_ok / max(total_all, 1)),
            "por_direcao": por_direcao,
        }

    # ── desenho (paintEvent) ────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # fundo
        p.fillRect(0, 0, w, h, BG)

        # área dos pontos (retângulo preto com borda lilás)
        margin = 40
        ax, ay = margin, margin
        aw, ah = w - 2 * margin, h - 100
        p.fillRect(ax, ay, aw, ah, AREA)
        p.setPen(QPen(BORDER, 1))
        p.drawRect(ax, ay, aw, ah)

        target = self._target()
        phase = self._phase() if self.mode == "calibrating" else None

        # ── pontos ──────────────────────────────────────────────────────────
        for name, (rx, ry) in TARGETS.items():
            px = int(ax + rx * aw)
            py = int(ay + ry * ah)

            if self.mode == "calibrating" and name == target:
                # alvo atual — círculo branco grande
                p.setBrush(WHITE)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(px - 18, py - 18, 36, 36)

                if phase == "verificacao":
                    # anel azul na verificação
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(BLUE, 3))
                    p.drawEllipse(px - 28, py - 28, 56, 56)

                # rótulo abaixo
                p.setPen(WHITE)
                p.setFont(QFont("Segoe UI", 11))
                fm = p.fontMetrics()
                label = name.upper()
                p.drawText(px - fm.horizontalAdvance(label) // 2, py + 50, label)

            elif self.mode == "calibrating":
                # outros pontos — verde se já foi, cinza se ainda não
                idx = self.target_names.index(name)
                done = idx < self.current_target_idx
                color = GREEN if done else GRAY
                r = 8 if done else 5
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(px - r, py - r, 2 * r, 2 * r)

                p.setPen(GRAY)
                p.setFont(QFont("Segoe UI", 9))
                fm = p.fontMetrics()
                p.drawText(px - fm.horizontalAdvance(name) // 2, py + 22, name)

            elif self.mode == "result" and self.calibration_data:
                # resultado — cor do acerto (verde ≥ 80 %, âmbar ≥ 50 %, vermelho)
                rate = self.calibration_data["verificacao"]["por_direcao"][name]
                color = GREEN if rate >= 0.8 else AMBER if rate >= 0.5 else RED
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(px - 26, py - 26, 52, 52)

                p.setPen(WHITE)
                p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                fm = p.fontMetrics()
                label = f"{name.upper()} {rate:.0%}"
                p.drawText(px - fm.horizontalAdvance(label) // 2, py + 50, label)

        # ── preview da câmera (centro-direita, abaixo dos pontos superiores) ──
        if self.current_frame is not None and self.mode == "calibrating":
            ann = self.gaze.annotated_frame() if self.gaze.pupils_located else self.current_frame
            pw, ph = 213, 160
            resized = cv2.resize(ann, (pw, ph))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            qimg = QImage(
                rgb.data, pw, ph, rgb.strides[0], QImage.Format.Format_RGB888
            ).copy()
            cam_x = w - pw - margin - 5
            cam_y = ay + int(0.25 * ah)
            p.drawImage(cam_x, cam_y, qimg)

            # dados ao vivo abaixo do preview
            angles = self.gaze.gaze_angles()
            if angles and target:
                p.setPen(WHITE)
                p.setFont(QFont("Consolas", 10))
                tx = cam_x
                ty = cam_y + ph + 20
                p.drawText(tx, ty,      f"Yaw:   {angles[0]:+.1f}°")
                p.drawText(tx, ty + 20, f"Pitch: {angles[1]:+.1f}°")
                n_amostras = len(self.samples[target])
                p.drawText(tx, ty + 40, f"Amostras: {n_amostras}")

        # ── barra de status ─────────────────────────────────────────────────
        p.setPen(WHITE)
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        fm = p.fontMetrics()

        if self.mode == "calibrating" and target:
            elapsed = time.monotonic() - self.phase_start_time
            remaining = max(0, PHASE_DURATIONS[self.current_phase_idx] - elapsed)
            n_samples = len(self.samples[target])
            status = (
                f"Olhe para: {target.upper()}   |   "
                f"{PHASE_LABELS.get(phase, '')} ({remaining:.0f}s)   |   "
                f"Amostras: {n_samples}   |   "
                f"Ponto {self.current_target_idx + 1}/{len(self.target_names)}"
            )
        elif self.calibration_data:
            acc = self.calibration_data["verificacao"]["acuracia"]
            ht = self.calibration_data["thresholds"]["horizontal"]
            vt = self.calibration_data["thresholds"]["vertical"]
            status = (
                f"Calibração concluída!   |   Cobertura: {acc:.0%}   |   "
                f"Bordas da tela: H={ht:.1f}°  V={vt:.1f}°   |   "
                f"Pressione qualquer tecla para aplicar"
            )
        else:
            status = "Calibração falhou (amostras insuficientes). Pressione qualquer tecla para fechar."

        p.drawText((w - fm.horizontalAdvance(status)) // 2, h - 30, status)
        p.end()

    # ── teclado e fechamento ────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if self.mode == "result":
            self._emit_and_close(self.calibration_data)
        elif event.key() == Qt.Key.Key_Escape:
            self._emit_and_close(None)

    def closeEvent(self, event):
        self.timer.stop()
        if not self._signal_emitted:
            self._signal_emitted = True
            self.finished.emit(None)
        super().closeEvent(event)

    def _emit_and_close(self, data):
        self.timer.stop()
        if not self._signal_emitted:
            self._signal_emitted = True
            self.finished.emit(data)
        self.close()
