"""Shared Qt widgets and visual styles for the Ocular desktop windows."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


STYLE = """
QWidget#ocular, QScrollArea#workspace, QWidget#content { background: #101722; }
QWidget { color: #eaf0f8; }
QScrollArea#workspace { border: none; }
QLabel#brand { font-size: 20px; font-weight: 700; }
QLabel#role, QLabel#sectionLabel { color: #a1b2c8; font-size: 12px; }
QLabel#pageTitle { font-size: 30px; font-weight: 700; }
QLabel#sectionTitle { font-size: 17px; font-weight: 700; }
QLabel#stateValue { font-size: 14px; font-weight: 600; }
QLabel#stateValue[tone="positive"] { color: #75dfbf; }
QLabel#stateValue[tone="progress"] { color: #92bfff; }
QLabel#stateValue[tone="notice"] { color: #f0c487; }
QFrame#card { background: #192536; border: 1px solid #2b3b51; border-radius: 16px; }
QFrame#state { background: #202e41; border: 1px solid #314159; border-radius: 11px; }
QFrame#videoSurface { background: #0b111b; border: 1px solid #283850; border-radius: 12px; }
QWidget#ocular QLabel#video { color: #a6b7cd; font-size: 14px; }
QPushButton {
    background: #26364d; border: 1px solid #3c506d; border-radius: 8px;
    padding: 8px 12px; font-weight: 600; min-height: 20px;
}
QPushButton:hover { background: #304564; }
QPushButton:pressed { background: #24344b; }
QPushButton[primary="true"] { background: #225cbd; border-color: #3776d4; }
QPushButton[primary="true"]:hover { background: #286bd6; }
QPushButton[primary="true"]:pressed { background: #1c4e9e; }
QPushButton:focus, QLineEdit:focus, QListWidget:focus { border: 1px solid #92bfff; }
QLineEdit, QListWidget {
    background: #121d2c; border: 1px solid #384b65; border-radius: 8px;
    padding: 8px; selection-background-color: #225cbd;
}
QLineEdit:read-only { color: #a1b2c8; }
QListWidget::item { padding: 9px 4px; border-bottom: 1px solid #25364d; }
QScrollBar:vertical { width: 12px; background: #101722; }
QScrollBar::handle:vertical { background: #425975; min-height: 24px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def icon(name, color="#92bfff", size=20):
    """Draw the small line icons used by both windows."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    pen = QPen(QColor(color))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    if name == "eye":
        painter.drawArc(QRectF(2, 7, 20, 13), 0, 180 * 16)
        painter.drawArc(QRectF(2, 4, 20, 13), 180 * 16, 180 * 16)
        painter.drawEllipse(QRectF(9, 9, 6, 6))
    elif name == "camera":
        painter.drawRoundedRect(QRectF(3, 6, 13, 12), 2, 2)
        painter.drawLine(16, 10, 21, 7)
        painter.drawLine(21, 7, 21, 17)
        painter.drawLine(21, 17, 16, 14)
    elif name == "target":
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        painter.drawEllipse(QRectF(9, 9, 6, 6))
    elif name == "connection":
        painter.drawArc(QRectF(3, 6, 18, 14), 35 * 16, 110 * 16)
        painter.drawArc(QRectF(7, 10, 10, 8), 35 * 16, 110 * 16)
        painter.drawPoint(12, 16)
    elif name == "history":
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        painter.drawLine(12, 8, 12, 12)
        painter.drawLine(12, 12, 15, 14)
    painter.end()
    return pixmap


def heading(text, style, symbol=None):
    label = QLabel(text)
    label.setObjectName(style)
    if symbol is None:
        return label
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    glyph = QLabel()
    glyph.setPixmap(icon(symbol))
    layout.addWidget(glyph)
    layout.addWidget(label, 1)
    return row


def action(text, symbol, *, primary=False):
    button = QPushButton(QIcon(icon(symbol, "#eaf0f8", 17)), text)
    button.setProperty("primary", primary)
    return button


class Card(QFrame):
    def __init__(self, title, symbol):
        super().__init__()
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 16, 16, 16)
        self.body.setSpacing(12)
        self.body.addWidget(heading(title, "sectionTitle", symbol))


class State(QFrame):
    def __init__(self, title, value, symbol):
        super().__init__()
        self.setObjectName("state")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.addWidget(heading(title, "sectionLabel", symbol))
        self.value = QLabel()
        self.value.setObjectName("stateValue")
        self.value.setWordWrap(True)
        layout.addWidget(self.value)
        self.set_state(value)

    def set_state(self, text, tone="neutral"):
        self.value.setText(text)
        if self.value.property("tone") != tone:
            self.value.setProperty("tone", tone)
            self.value.style().unpolish(self.value)
            self.value.style().polish(self.value)
            self.value.update()


class VideoLabel(QLabel):
    """Retain the source frame so resize always scales from the original."""

    def __init__(self, text):
        super().__init__(text)
        self.setObjectName("video")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._source = QPixmap()

    def sizeHint(self):
        return QSize(640, 420)

    def setText(self, text):
        self._source = QPixmap()
        super().setText(text)

    def set_frame(self, source):
        self._source = source
        self._fit_frame()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_frame()

    def _fit_frame(self):
        if not self._source.isNull() and not self.contentsRect().size().isEmpty():
            self.setPixmap(self._source.scaled(
                self.contentsRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))


def video_card(title, placeholder):
    card = Card(title, "camera")
    surface = QFrame()
    surface.setObjectName("videoSurface")
    layout = QVBoxLayout(surface)
    layout.setContentsMargins(8, 8, 8, 8)
    video = VideoLabel(placeholder)
    layout.addWidget(video)
    card.body.addWidget(surface, 1)
    return card, video


class Workspace(QScrollArea):
    def __init__(self, window, title, role):
        super().__init__()
        window.setObjectName("ocular")
        window.setWindowTitle(f"Ocular — {role}")
        window.setWindowIcon(QIcon(icon("eye", size=32)))
        window.setFont(QFont("Inter", 10))
        window.setStyleSheet(STYLE)
        window.setMinimumSize(360, 440)
        window.resize(1180, 760)
        root = QVBoxLayout(window)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self)

        self.setObjectName("workspace")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 20, 24, 24)
        body.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(heading("Ocular", "brand", "eye"))
        header.addStretch()
        header.addWidget(heading(role, "role"))
        body.addLayout(header)
        body.addWidget(heading(title, "pageTitle"))
        self.panels = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.panels.setSpacing(16)
        body.addLayout(self.panels, 1)
        self.setWidget(content)

    def set_panels(self, main, side):
        self.panels.addWidget(main, 3)
        self.panels.addWidget(side, 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = (QBoxLayout.Direction.LeftToRight if event.size().width() >= 800
                     else QBoxLayout.Direction.TopToBottom)
        self.panels.setDirection(direction)
