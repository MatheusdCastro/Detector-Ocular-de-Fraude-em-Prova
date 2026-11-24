import math
from dataclasses import dataclass

import cv2
import numpy as np

# Landmarks do modelo de 68 pontos do dlib usados na estimativa da pose da cabeça.
NOSE_TIP = 30
CHIN = 8
EYE_OUTER_CORNER_RIGHT = 36  # canto externo do olho direito da pessoa (esquerda na imagem)
EYE_OUTER_CORNER_LEFT = 45  # canto externo do olho esquerdo da pessoa (direita na imagem)
MOUTH_CORNER_RIGHT = 48  # extremidade da boca à direita da pessoa (esquerda na imagem)
MOUTH_CORNER_LEFT = 54  # extremidade da boca à esquerda da pessoa (direita na imagem)

LANDMARK_IDS = [
    NOSE_TIP,
    CHIN,
    EYE_OUTER_CORNER_RIGHT,
    EYE_OUTER_CORNER_LEFT,
    MOUTH_CORNER_RIGHT,
    MOUTH_CORNER_LEFT,
]

# Modelo 3D genérico de um rosto (proporções aproximadas, em mm), na mesma ordem de
# LANDMARK_IDS. Eixos iguais aos da câmera do OpenCV: x para a direita da imagem,
# y para baixo e z para dentro da cena. O nariz é a origem, então um rosto de frente
# para a câmera corresponde à rotação identidade.
MODEL_POINTS = np.array(
    [
        (0.0, 0.0, 0.0),  # ponta do nariz
        (0.0, 330.0, 65.0),  # queixo
        (-225.0, -170.0, 135.0),  # canto externo do olho (esquerda na imagem)
        (225.0, -170.0, 135.0),  # canto externo do olho (direita na imagem)
        (-150.0, 150.0, 125.0),  # extremidade da boca (esquerda na imagem)
        (150.0, 150.0, 125.0),  # extremidade da boca (direita na imagem)
    ],
    dtype=np.float64,
)


@dataclass(frozen=True)
class HeadPose:
    """Orientação da cabeça, em graus, do ponto de vista da pessoa.

    yaw:   positivo = cabeça virada para a direita da pessoa (mesma convenção de
           GazeTracking.is_right), negativo = para a esquerda.
    pitch: positivo = cabeça olhando para cima, negativo = para baixo.
    roll:  positivo = cabeça inclinada no sentido horário, como vista na imagem.
    """

    yaw: float
    pitch: float
    roll: float


class HeadPoseEstimator:
    """Estima a pose da cabeça com cv2.solvePnP a partir de landmarks faciais
    que o rastreamento de pupilas não utiliza: ponta do nariz, queixo,
    extremidades da boca e cantos externos dos olhos.
    """

    def estimate(self, landmarks, frame_size):
        """Retorna um HeadPose, ou None se não for possível estimar.

        Arguments:
            landmarks (dlib.full_object_detection): Landmarks faciais do rosto
            frame_size (tuple): (largura, altura) do frame analisado
        """
        width, height = frame_size
        image_points = np.array(
            [(landmarks.part(i).x, landmarks.part(i).y) for i in LANDMARK_IDS],
            dtype=np.float64,
        )

        # Câmera aproximada: distância focal ~ largura da imagem, sem distorção.
        camera_matrix = np.array(
            [[width, 0, width / 2], [0, width, height / 2], [0, 0, 1]],
            dtype=np.float64,
        )

        ok, rotation_vector, _ = cv2.solvePnP(
            MODEL_POINTS, image_points, camera_matrix, None, flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not ok:
            return None

        rotation, _ = cv2.Rodrigues(rotation_vector)

        # Vetor que sai do nariz em direção à câmera (-z do modelo) e eixo que
        # liga os dois olhos (+x do modelo), ambos em coordenadas da câmera.
        forward = -rotation[:, 2]
        eyes_axis = rotation[:, 0]

        yaw = math.degrees(math.atan2(-forward[0], -forward[2]))
        pitch = math.degrees(math.atan2(-forward[1], math.hypot(forward[0], forward[2])))
        roll = math.degrees(math.atan2(eyes_axis[1], eyes_axis[0]))
        return HeadPose(yaw=yaw, pitch=pitch, roll=roll)
