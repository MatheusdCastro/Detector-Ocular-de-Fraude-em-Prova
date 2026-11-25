import cv2
import numpy as np
import math


class Pupil:
    """
    This class detects the iris of an eye and estimates
    the position of the pupil
    """
    # Esses valores tê de ser calibrados
    # Só inicial 
    MIN_AREA = 0.05
    MAX_AREA = 0.70
    LIM_CIRC = 0.50

    def __init__(self, eye_frame, threshold):
        self.iris_frame = None
        self.threshold = threshold
        self.x = None
        self.y = None
        self.valid = False
        self.area_ratio = None
        self.circularity = None

        self.detect_iris(eye_frame)

    @property
    def confidence(self):
        # Medida de confiança da detecção da pupila
        if not self.valid:
            return 0.0
        ideal_area = (self.MIN_AREA + self.MAX_AREA) / 2
        area_range = (self.MAX_AREA - self.MIN_AREA) / 2
        area_score = max(0.0, 1.0 - abs(self.area_ratio - ideal_area) / area_range)
        return round(min(1.0, self.circularity * area_score), 3)
    
    @staticmethod
    def image_processing(eye_frame, threshold):
        """Performs operations on the eye frame to isolate the iris

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
            threshold (int): Threshold value used to binarize the eye frame

        Returns:
            A frame with a single element representing the iris
        """
        kernel = np.ones((3, 3), np.uint8)
        new_frame = cv2.bilateralFilter(eye_frame, 10, 15, 15)
        new_frame = cv2.erode(new_frame, kernel, iterations=3)
        new_frame = cv2.threshold(new_frame, threshold, 255, cv2.THRESH_BINARY)[1]

        return new_frame

    def detect_iris(self, eye_frame):
        """Detects the iris and estimates the position of the pupil by
        calculating the centroid.

        Arguments:
            eye_frame (numpy.ndarray): Frame containing an eye and nothing else
        """
        self.iris_frame = self.image_processing(eye_frame, self.threshold)

        self.x = None
        self.y = None
        self.valid = False
        self.area_ratio = None
        self.circularity = None

        frame_area = self.iris_frame.shape[0] * self.iris_frame.shape[1]
        best = None
        best_score = 0.0
        contours, _ = cv2.findContours(self.iris_frame, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)[-2:]

        for contour in contours:
            # Área relativa
            area = cv2.contourArea(contour)
            area_ratio = area / frame_area
            if not (self.MIN_AREA <= area_ratio <= self.MAX_AREA):
                continue

            # Circularidade
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * math.pi * area / (perimeter ** 2)
            if circularity < self.LIM_CIRC:
                continue

            # Encontrar o candidato com maior área x circularidade
            score = area * circularity
            if score > best_score:
                best_score = score
                best = (contour, area_ratio, circularity)

        if best is None:
            return 
            
        contour, area_ratio, circularity = best
        moments = cv2.moments(contour)
        if moments['m00'] == 0:
            return

        self.x = int(moments['m10'] / moments['m00'])
        self.y = int(moments['m01'] / moments['m00'])
        self.area_ratio = area_ratio
        self.circularity = circularity
        self.valid = True
