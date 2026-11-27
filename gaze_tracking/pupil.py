import cv2
import numpy as np


class Pupil:
    """
    This class detects the iris of an eye and estimates
    the position of the pupil
    """

    # Fator de ampliação do recorte do olho: os recortes da webcam são minúsculos
    # (~40x20 px) e ampliá-los dá mais precisão ao centroide.
    SCALE = 4
    # Fração da área do olho que a região escura deve ocupar para ser aceita.
    MIN_AREA_RATIO = 0.03
    MAX_AREA_RATIO = 0.85

    def __init__(self, eye_frame, threshold, eye_mask=None):
        """
        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
            threshold (int): Limiar da calibração, usado só como reserva caso o
                limiar automático (Otsu) não encontre a íris
            eye_mask (numpy.ndarray): Máscara (255 dentro do olho) com o mesmo
                tamanho de eye_frame. Se None, usa o frame inteiro
        """
        self.iris_frame = None
        self.threshold = threshold
        self.x = None
        self.y = None

        if not self._detect_dark_region(eye_frame, eye_mask):
            self.detect_iris(eye_frame)

    def _detect_dark_region(self, eye_frame, eye_mask):
        """Finds the iris as the largest dark blob inside the eye, using a
        threshold computed from this very frame (Otsu), so it adapts to the
        lighting instead of depending on a calibration made in the first frames.

        Returns True if the pupil position was found.
        """
        if eye_frame.size == 0:
            return False

        scale = self.SCALE
        big = cv2.resize(eye_frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        big = cv2.GaussianBlur(big, (5, 5), 0)

        if eye_mask is None:
            mask = np.full(big.shape[:2], 255, np.uint8)
        else:
            mask = cv2.resize(eye_mask, (big.shape[1], big.shape[0]), interpolation=cv2.INTER_NEAREST)
            # Afasta a borda para ignorar sombra de pálpebra e cílios
            mask = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * scale + 1, 2 * scale + 1)))

        values = big[mask > 0]
        if values.size < 50:
            return False

        otsu, _ = cv2.threshold(values.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        dark = ((big <= otsu) & (mask > 0)).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * scale + 1, 2 * scale + 1))
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(dark)
        if count < 2:
            return False

        best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area_ratio = stats[best, cv2.CC_STAT_AREA] / float(np.count_nonzero(mask))
        if not self.MIN_AREA_RATIO <= area_ratio <= self.MAX_AREA_RATIO:
            return False

        cx, cy = centroids[best]
        # Centro do pixel ampliado -> coordenada no recorte original
        self.x = int(round((cx + 0.5) / scale - 0.5))
        self.y = int(round((cy + 0.5) / scale - 0.5))
        self.threshold = int(otsu)
        self.iris_frame = cv2.resize(
            (labels != best).astype(np.uint8) * 255,
            (eye_frame.shape[1], eye_frame.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
        return True

    @staticmethod
    def preprocess(eye_frame):
        """Suaviza e erode o recorte do olho antes da binarização.
        Separado de image_processing para a calibração poder pré-processar
        uma vez e testar vários limiares."""
        kernel = np.ones((3, 3), np.uint8)
        new_frame = cv2.bilateralFilter(eye_frame, 10, 15, 15)
        return cv2.erode(new_frame, kernel, iterations=3)

    @staticmethod
    def image_processing(eye_frame, threshold):
        """Performs operations on the eye frame to isolate the iris

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
            threshold (int): Threshold value used to binarize the eye frame

        Returns:
            A frame with a single element representing the iris
        """
        new_frame = Pupil.preprocess(eye_frame)
        return cv2.threshold(new_frame, threshold, 255, cv2.THRESH_BINARY)[1]

    def detect_iris(self, eye_frame):
        """Detects the iris and estimates the position of the pupil by
        calculating the centroid.

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
        """
        if eye_frame.size == 0:
            return
        self.iris_frame = self.image_processing(eye_frame, self.threshold)

        contours, _ = cv2.findContours(self.iris_frame, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)[-2:]
        contours = sorted(contours, key=cv2.contourArea)

        try:
            moments = cv2.moments(contours[-2])
            self.x = int(moments['m10'] / moments['m00'])
            self.y = int(moments['m01'] / moments['m00'])
        except (IndexError, ZeroDivisionError):
            pass