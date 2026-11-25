from pathlib import Path

import cv2
import dlib

from .calibration import Calibration
from .eye import Eye
from .smoothing import ExponentialSmoothing


class GazeTracking:
    """
    This class tracks the user's gaze.
    It provides useful information like the position of the eyes
    and pupils and lets you know if the eyes are open or closed.
    """

    def __init__(self):
        self.frame = None
        self.eye_left = None
        self.eye_right = None
        self.calibration = Calibration()

        # _face_detector is used to detect faces
        self._face_detector = dlib.get_frontal_face_detector()

        # _predictor is used to get facial landmarks of a given face
        model_path = Path(__file__).parent / "trained_models" / "shape_predictor_68_face_landmarks.dat"
        self._predictor = dlib.shape_predictor(str(model_path))

        # Suavização temporal
        self._smooth_left = ExponentialSmoothing(alpha=0.4)
        self._smooth_right = ExponentialSmoothing(alpha=0.4)
        self._smooth_h = ExponentialSmoothing(alpha=0.4)
        self._smooth_v = ExponentialSmoothing(alpha=0.4)

    @property
    def pupils_located(self):
        """Check that the pupils have been located"""
        try:
            int(self.eye_left.pupil.x)
            int(self.eye_left.pupil.y)
            int(self.eye_right.pupil.x)
            int(self.eye_right.pupil.y)
            return True
        except (AttributeError, TypeError):
            return False

    def _analyze(self):
        """Detects the face and initializes Eye objects"""
        frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_detector(frame)

        try:
            landmarks = self._predictor(frame, faces[0])
            self.eye_left = Eye(frame, landmarks, 0, self.calibration)
            self.eye_right = Eye(frame, landmarks, 1, self.calibration)

        except (IndexError, ValueError, cv2.error):
            self.eye_left = None
            self.eye_right = None

        # Atualiza valores suavizados
        if self.pupils_located:
            raw_left = (self.eye_left.origin[0] + self.eye_left.pupil.x,
                        self.eye_left.origin[1] + self.eye_left.pupil.y)
            raw_right = (self.eye_right.origin[0] + self.eye_right.pupil.x,
                         self.eye_right.origin[1] + self.eye_right.pupil.y)
            self._smooth_left.update(raw_left)
            self._smooth_right.update(raw_right)

            h_left = self.eye_left.pupil.x / (self.eye_left.center[0] * 2 - 10)
            h_right = self.eye_right.pupil.x / (self.eye_right.center[0] * 2 - 10)
            self._smooth_h.update((h_left + h_right) / 2)

            v_left = self.eye_left.pupil.y / (self.eye_left.center[1] * 2 - 10)
            v_right = self.eye_right.pupil.y / (self.eye_right.center[1] * 2 - 10)
            self._smooth_v.update((v_left + v_right) / 2)

    def refresh(self, frame):
        """Refreshes the frame and analyzes it.

        Arguments:
            frame (numpy.ndarray): The frame to analyze
        """
        self.frame = frame
        self._analyze()

    def pupil_left_coords(self):
        """Returns the smoothed coordinates of the left pupil"""
        if self.pupils_located and self._smooth_left.value is not None:
            x, y = self._smooth_left.value
            return (int(x), int(y))

    def pupil_right_coords(self):
        """Returns the smoothed coordinates of the right pupil"""
        if self.pupils_located and self._smooth_right.value is not None:
            x, y = self._smooth_right.value
            return (int(x), int(y))

    def horizontal_ratio(self):
        """Returns a smoothed number between 0.0 and 1.0 that indicates the
        horizontal direction of the gaze. The extreme right is 0.0,
        the center is 0.5 and the extreme left is 1.0
        """
        if self.pupils_located and self._smooth_h.value is not None:
            return self._smooth_h.value

    def vertical_ratio(self):
        """Returns a smoothed number between 0.0 and 1.0 that indicates the
        vertical direction of the gaze. The extreme top is 0.0,
        the center is 0.5 and the extreme bottom is 1.0
        """
        if self.pupils_located and self._smooth_v.value is not None:
            return self._smooth_v.value

    def pupil_confidence(self):
        # Confiança combinada
        if self.pupils_located:
            left = self.eye_left.pupil.confidence
            right = self.eye_right.pupil.confidence
            return (left + right) / 2
        return 0.0

    def is_right(self):
        """Returns true if the user is looking to the right"""
        if self.pupils_located:
            return self.horizontal_ratio() <= 0.35

    def is_left(self):
        """Returns true if the user is looking to the left"""
        if self.pupils_located:
            return self.horizontal_ratio() >= 0.65

    def is_up(self):
        """Returns true if the user is looking up.

        The vertical range of pupil movement is smaller than the horizontal,
        so the thresholds are tighter (closer to 0.5).
        """
        if self.pupils_located:
            v = self.vertical_ratio()
            return v is not None and v <= 0.40

    def is_down(self):
        """Returns true if the user is looking down.

        The vertical range of pupil movement is smaller than the horizontal,
        so the thresholds are tighter (closer to 0.5).
        """
        if self.pupils_located:
            v = self.vertical_ratio()
            return v is not None and v >= 0.60

    def is_center(self):
        """Returns true if the user is looking at the center"""
        if self.pupils_located:
            return (self.is_right() is not True
                    and self.is_left() is not True
                    and self.is_up() is not True
                    and self.is_down() is not True)

    def is_blinking(self):
        """Returns true if the user closes his eyes"""
        if self.pupils_located:
            blinking_ratio = (self.eye_left.blinking + self.eye_right.blinking) / 2
            if blinking_ratio > 3.8:
                v_left = self.eye_left.pupil.y / (self.eye_left.center[1] * 2 - 10)
                v_right = self.eye_right.pupil.y / (self.eye_right.center[1] * 2 - 10)
                raw_v = (v_left + v_right) / 2
                if raw_v > 0.55 and self.pupil_confidence() > 0.35:
                    return False
                return True
        return False

    def annotated_frame(self):
        """Returns the main frame with pupils highlighted"""
        frame = self.frame.copy()

        if self.pupils_located:
            color = (0, 255, 0)
            x_left, y_left = self.pupil_left_coords()
            x_right, y_right = self.pupil_right_coords()
            cv2.line(frame, (x_left - 5, y_left), (x_left + 5, y_left), color)
            cv2.line(frame, (x_left, y_left - 5), (x_left, y_left + 5), color)
            cv2.line(frame, (x_right - 5, y_right), (x_right + 5, y_right), color)
            cv2.line(frame, (x_right, y_right - 5), (x_right, y_right + 5), color)

        return frame