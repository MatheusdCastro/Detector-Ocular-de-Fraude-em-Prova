from collections import deque

import numpy as np

from .pupil import Pupil


class Calibration:
    """
    Calibra o limiar de binarização usado para isolar a íris (método de reserva
    do Pupil, quando o Otsu não encontra a região escura).

    A versão original media apenas os primeiros 20 frames e congelava o valor,
    o que deixa de funcionar quando a iluminação muda durante a prova. Aqui a
    calibração é contínua: cada frame válido gera um limiar ótimo, os mais
    recentes ficam numa janela deslizante por olho e o limiar usado é a mediana
    dessa janela. Assim:
      - mudanças graduais de luz são acompanhadas automaticamente;
      - frames ruins isolados (piscadas, desfoque) não afetam o resultado;
      - mudanças bruscas (luz acesa/apagada) zeram o histórico e o limiar
        se adapta em poucos frames.
    """

    # Fração do recorte do olho que a íris costuma ocupar após a binarização.
    AVERAGE_IRIS_SIZE = 0.48
    # Tamanho da janela deslizante (~1 s a 30 fps).
    WINDOW_SIZE = 30
    # Amostras mínimas por olho para considerar a calibração pronta.
    MIN_SAMPLES = 10
    # Limiar usado enquanto ainda não há amostras.
    DEFAULT_THRESHOLD = 50
    # Mudança brusca: se o limiar ótimo ficar a mais de JUMP níveis de cinza da
    # mediana atual por JUMP_FRAMES frames seguidos, o histórico antigo é descartado.
    JUMP = 25
    JUMP_FRAMES = 5
    # Razão largura/altura do olho acima da qual ele é considerado fechado
    # (mesmo valor usado em GazeTracking.is_blinking).
    BLINKING_RATIO = 3.8
    # Margem ignorada nas bordas do recorte ao medir a íris.
    BORDER = 5

    def __init__(self):
        self._samples = (deque(maxlen=self.WINDOW_SIZE), deque(maxlen=self.WINDOW_SIZE))
        self._jump_streak = [0, 0]

    def is_complete(self):
        """Retorna True se os dois olhos já têm amostras suficientes."""
        return all(len(samples) >= self.MIN_SAMPLES for samples in self._samples)

    def threshold(self, side):
        """Retorna o limiar atual do olho indicado.

        Argument:
            side: 0 para o olho esquerdo, 1 para o direito
        """
        samples = self._samples[side]
        if not samples:
            return self.DEFAULT_THRESHOLD
        return int(np.median(samples))

    def reset(self):
        """Descarta todo o histórico (ex.: troca de usuário ou de câmera)."""
        for samples in self._samples:
            samples.clear()
        self._jump_streak = [0, 0]

    @staticmethod
    def iris_size(frame):
        """Retorna a fração do recorte ocupada pela íris (pixels pretos).

        Argument:
            frame (numpy.ndarray): Recorte do olho já binarizado
        """
        frame = frame[5:-5, 5:-5]
        if frame.size == 0:
            return 0.0
        return 1.0 - np.count_nonzero(frame) / frame.size

    @classmethod
    def find_best_threshold(cls, eye_frame):
        """Calcula o limiar que faz a íris ocupar AVERAGE_IRIS_SIZE do recorte.

        Em vez de binarizar a imagem para cada limiar candidato, pré-processa
        uma vez e usa o histograma acumulado: após a binarização com limiar t,
        os pixels pretos são exatamente os com valor <= t. Isso permite testar
        todos os limiares de 1 a 254 (o original ia só até 95, insuficiente com
        iluminação forte) com custo de uma única passada.

        Retorna None se o recorte for inválido.

        Argument:
            eye_frame (numpy.ndarray): Recorte do olho
        """
        if eye_frame is None or eye_frame.size == 0:
            return None

        processed = Pupil.preprocess(eye_frame)
        inner = processed[cls.BORDER:-cls.BORDER, cls.BORDER:-cls.BORDER]
        if inner.size == 0:
            return None

        histogram = np.bincount(inner.ravel(), minlength=256)
        iris_sizes = np.cumsum(histogram) / inner.size  # iris_sizes[t] = fração de pixels <= t
        candidates = np.arange(1, 255)
        best = candidates[np.argmin(np.abs(iris_sizes[candidates] - cls.AVERAGE_IRIS_SIZE))]
        return int(best)

    def evaluate(self, eye_frame, side, eye_closed=False):
        """Atualiza a calibração com o frame atual do olho.

        Arguments:
            eye_frame (numpy.ndarray): Recorte do olho
            side: 0 para o olho esquerdo, 1 para o direito
            eye_closed (bool): Se True o frame é ignorado (pálpebra fechada
                não tem íris e estragaria a média)
        """
        if eye_closed:
            return

        best = self.find_best_threshold(eye_frame)
        if best is None:
            return

        samples = self._samples[side]
        if samples and abs(best - np.median(samples)) > self.JUMP:
            self._jump_streak[side] += 1
        else:
            self._jump_streak[side] = 0

        samples.append(best)

        if self._jump_streak[side] >= self.JUMP_FRAMES:
            # Iluminação mudou de forma brusca: mantém só os frames recentes.
            recent = list(samples)[-self.JUMP_FRAMES:]
            samples.clear()
            samples.extend(recent)
            self._jump_streak[side] = 0
