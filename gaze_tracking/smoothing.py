class ExponentialSmoothing:
    """Exponential moving average (EMA) filter.

    Works with scalars and tuples/lists of any length.
    For 2-D coordinates, pass ``(x, y)`` tuples.

    Arguments:
        alpha (float): Smoothing factor in (0, 1].
            Higher values follow the raw signal more closely (less smoothing).
    """

    def __init__(self, alpha: float = 0.4):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._value = None

    def update(self, raw):
        """Feed a new raw measurement and return the smoothed value.

        If *raw* is ``None`` the internal state is unchanged and the
        last smoothed value (or ``None``) is returned.
        """
        if raw is None:
            return self._value

        if self._value is None:
            self._value = raw
        elif isinstance(raw, (tuple, list)):
            self._value = tuple(
                self.alpha * r + (1 - self.alpha) * s
                for r, s in zip(raw, self._value)
            )
        else:
            self._value = self.alpha * raw + (1 - self.alpha) * self._value

        return self._value

    def reset(self):
        """Clear the internal state."""
        self._value = None

    @property
    def value(self):
        """Last smoothed value, or ``None`` if no data has been fed yet."""
        return self._value
