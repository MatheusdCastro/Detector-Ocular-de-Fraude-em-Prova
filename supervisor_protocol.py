import json


SUPERVISOR_HOST = "127.0.0.1"
SUPERVISOR_PORT = 8765
SUPERVISOR_URL = f"ws://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}"
VIDEO_SIZE = (640, 480)

DIRECTION_LABELS = {
    "left": "Olhando para a esquerda",
    "right": "Olhando para a direita",
    "center": "Olhando para o centro",
    "blinking": "Piscando",
    "not_detected": "Rosto/pupilas não detectados",
}


def encode_status(camera_active, direction):
    return json.dumps({
        "type": "status",
        "camera_active": camera_active,
        "direction": direction,
    })


def decode_status(message):
    try:
        status = json.loads(message)
    except (ValueError, RecursionError):
        return None

    if not isinstance(status, dict) or status.get("type") != "status":
        return None
    if type(status.get("camera_active")) is not bool or "direction" not in status:
        return None

    camera_active = status["camera_active"]
    direction = status["direction"]
    if direction is not None:
        if not camera_active or not isinstance(direction, str) or direction not in DIRECTION_LABELS:
            return None
    return camera_active, direction
