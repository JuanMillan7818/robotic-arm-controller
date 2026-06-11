"""
app/gesture/hand_tracker.py
MediaPipe 0.10.35 Tasks API — 5-axis gesture detection.

Gesture mapping (single hand):
  BASE           wrist X position in frame      → 0–180°
  BASE_PRINCIPAL wrist Y position (inverted)    → 10–170°
  EXT1           middle-finger extension ratio  → 0–180°
  EXT2           hand roll (knuckle line angle) → 10–160°
  PINZA          pinky(+ring) extension         → 110–145°

Callbacks fire from background thread — caller must post to event loop.
"""

from __future__ import annotations

import base64
import logging
import math
import sys
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)

_WRIST = 0
_THUMB_TIP = 4
_INDEX_MCP = 5
_INDEX_TIP = 8
_MID_MCP = 9
_MID_TIP = 12
_RING_MCP = 13
_RING_TIP = 16
_PINKY_MCP = 17
_PINKY_TIP = 20

_PINZA_DIST_MIN = 0.03
_PINZA_DIST_MAX = 0.18
_EXT1_RATIO_MIN = 1.2   # slightly above fist ratio → fist clamps to 0°
_EXT1_RATIO_MAX = 1.9   # slightly below open ratio → open hand clamps to 180°
_FINGER_EXT_THRESH = 1.5  # ratio threshold: finger considered extended
_BP_OPEN_MIN = 1.3  # fist: avg finger ratio ~1.0–1.3
_BP_OPEN_MAX = 2.2  # fully open: avg ratio ~2.0–2.5
_EXT2_X_MIN = 15.0   # wrist near right edge → 10°
_EXT2_X_MAX = 180.0  # wrist near left edge → 160°


def _check_camera_permission() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam",
        )
        value, _ = winreg.QueryValueEx(key, "Value")
        winreg.CloseKey(key)
        if value != "Allow":
            return (
                "Acceso a cámara bloqueado en Windows. "
                "Ve a Configuración → Privacidad → Cámara y actívalo."
            )
    except Exception:
        pass
    return None


def _dist(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _ext_ratio(wrist, mcp, tip) -> float:
    r = max(0.01, _dist(wrist, mcp))
    return _dist(wrist, tip) / r


def _detect_left(lm: list) -> dict[str, int]:
    """Left hand → BASE (wrist X) + BASE_PRINCIPAL (hand openness)."""
    wrist = lm[_WRIST]
    idx_mcp = lm[_INDEX_MCP]
    idx_tip = lm[_INDEX_TIP]
    mid_mcp = lm[_MID_MCP]
    mid_tip = lm[_MID_TIP]
    rng_mcp = lm[_RING_MCP]
    rng_tip = lm[_RING_TIP]
    pky_mcp = lm[_PINKY_MCP]
    pky_tip = lm[_PINKY_TIP]

    raw_base = wrist.x * 180
    BASE_MIN_REAL = 15
    BASE_MAX_REAL = 180

    base = int(
        (raw_base - BASE_MIN_REAL)
        * 180
        / (BASE_MAX_REAL - BASE_MIN_REAL)
    )

    base = max(0, min(180, base))

    avg_open = (
        _ext_ratio(wrist, idx_mcp, idx_tip)
        + _ext_ratio(wrist, mid_mcp, mid_tip)
        + _ext_ratio(wrist, rng_mcp, rng_tip)
        + _ext_ratio(wrist, pky_mcp, pky_tip)
    ) / 4.0
    avg_c = max(_BP_OPEN_MIN, min(_BP_OPEN_MAX, avg_open))
    bp = int((avg_c - _BP_OPEN_MIN) / (_BP_OPEN_MAX - _BP_OPEN_MIN) * 160 + 10)

    return {"BASE": base, "BASE_PRINCIPAL": bp}


def _detect_right(lm: list) -> dict[str, int]:
    """Right hand → EXT1 (open/close) + EXT2 (wrist X) + PINZA (finger count)."""
    wrist = lm[_WRIST]
    idx_mcp = lm[_INDEX_MCP]
    idx_tip = lm[_INDEX_TIP]
    mid_mcp = lm[_MID_MCP]
    mid_tip = lm[_MID_TIP]
    rng_mcp = lm[_RING_MCP]
    rng_tip = lm[_RING_TIP]
    pky_mcp = lm[_PINKY_MCP]
    pky_tip = lm[_PINKY_TIP]

    # EXT1: full hand open/close — abierta=180°, puño=0°
    avg_open = (
        _ext_ratio(wrist, idx_mcp, idx_tip)
        + _ext_ratio(wrist, mid_mcp, mid_tip)
        + _ext_ratio(wrist, rng_mcp, rng_tip)
        + _ext_ratio(wrist, pky_mcp, pky_tip)
    ) / 4.0
    avg_c = max(_EXT1_RATIO_MIN, min(_EXT1_RATIO_MAX, avg_open))
    ext1 = int((avg_c - _EXT1_RATIO_MIN) /
               (_EXT1_RATIO_MAX - _EXT1_RATIO_MIN) * 180)

    # EXT2: wrist X position — izquierda=160°, derecha=10° (same convention as BASE on left hand)
    raw_ext2 = wrist.x * 180
    ext2 = int((raw_ext2 - _EXT2_X_MIN) * 150 /
               (_EXT2_X_MAX - _EXT2_X_MIN) + 10)
    ext2 = max(10, min(160, ext2))

    # PINZA: meñique/anular con índice+medio ABAJO (no dispara en mano abierta)
    #   solo meñique estirado, índice+medio cerrados  → abrir (110°)
    #   meñique+anular estirados, índice+medio cerrados → cerrar (145°)
    idx_up = _ext_ratio(wrist, idx_mcp, idx_tip) > _FINGER_EXT_THRESH
    mid_up = _ext_ratio(wrist, mid_mcp, mid_tip) > _FINGER_EXT_THRESH
    rng_up = _ext_ratio(wrist, rng_mcp, rng_tip) > _FINGER_EXT_THRESH
    pky_up = _ext_ratio(wrist, pky_mcp, pky_tip) > _FINGER_EXT_THRESH
    hand_open = idx_up or mid_up  # bloquea PINZA durante EXT1

    result: dict[str, int] = {"EXT1": ext1, "EXT2": ext2}
    if not hand_open:
        if pky_up and rng_up:
            result["PINZA"] = 145   # meñique+anular, resto cerrado → cerrar
        elif pky_up:
            result["PINZA"] = 110   # solo meñique, resto cerrado → abrir
    # else: mano abierta/semiabierta → no actualizar PINZA
    return result


class HandTracker:
    """OpenCV + MediaPipe gesture tracker (Desktop only)."""

    def __init__(
        self,
        on_frame: Callable[[str], None],
        on_gesture: Callable[[dict[str, int]], None],
        fps_limit: int = 20,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_frame = on_frame
        self._on_gesture = on_gesture
        self._on_error = on_error
        self._fps_limit = fps_limit
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="HandTracker"
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        try:
            self._run_inner()
        except Exception as exc:
            log.error("HandTracker crashed: %s", exc, exc_info=True)
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._running = False

    def _run_inner(self) -> None:
        perm_err = _check_camera_permission()
        if perm_err:
            if self._on_error:
                self._on_error(perm_err)
            return

        import urllib.request
        from pathlib import Path
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        model_path = (
            Path(__file__).parent.parent.parent /
            "assets" / "hand_landmarker.task"
        )
        model_path.parent.mkdir(parents=True, exist_ok=True)
        if not model_path.exists():
            log.info("Descargando modelo hand_landmarker.task...")
            url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
            )
            urllib.request.urlretrieve(url, model_path)
            log.info("Modelo descargado: %s", model_path)

        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.65,
            min_hand_presence_confidence=0.65,
            min_tracking_confidence=0.65,
        )
        landmarker = mp_vision.HandLandmarker.create_from_options(options)
        # Try DirectShow first (avoids MSMF -1072873822 grab errors on Windows)
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)  # fallback to default backend
        if not cap.isOpened():
            landmarker.close()
            if self._on_error:
                self._on_error("No se pudo abrir la cámara (índice 0)")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        interval = 1.0 / self._fps_limit
        last_t = 0.0
        start_t = time.monotonic()

        CONNECTIONS = [
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),
            (0, 5),
            (5, 6),
            (6, 7),
            (7, 8),
            (0, 9),
            (9, 10),
            (10, 11),
            (11, 12),
            (0, 13),
            (13, 14),
            (14, 15),
            (15, 16),
            (0, 17),
            (17, 18),
            (18, 19),
            (19, 20),
            (5, 9),
            (9, 13),
            (13, 17),
        ]
        HIGHLIGHT = {_THUMB_TIP, _INDEX_TIP,
                     _MID_TIP, _WRIST, _INDEX_MCP, _PINKY_MCP}

        consecutive_failures = 0
        try:
            while self._running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= 10:
                        break  # camera truly lost
                    time.sleep(0.05)
                    continue
                consecutive_failures = 0

                now = time.monotonic()
                if now - last_t < interval:
                    continue
                last_t = now

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts_ms = int((now - start_t) * 1000)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(mp_img, ts_ms)

                gestures: dict[str, int] = {}
                h, w = frame.shape[:2]
                detected_labels: list[str] = []

                for idx, lm in enumerate(result.hand_landmarks):
                    # handedness[idx].classification[0].label: "Left" or "Right"
                    # Note: MediaPipe uses camera-mirror convention — "Left" in result = right hand physically
                    try:
                        label = result.handedness[idx][
                            0
                        ].category_name  # "Left"/"Right"
                    except Exception:
                        label = "Right"

                    # Mirror-corrected: MediaPipe "Left" = physical right hand (frame is flipped)
                    is_right = label == "Left"

                    detected_labels.append("Der" if is_right else "Izq")
                    color_hand = (0, 212, 255) if is_right else (124, 58, 237)
                    pts = [(int(p.x * w), int(p.y * h)) for p in lm]
                    for a, b in CONNECTIONS:
                        cv2.line(frame, pts[a], pts[b], color_hand, 2)
                    for i, pt in enumerate(pts):
                        col = (0, 212, 255) if i in HIGHLIGHT else (
                            200, 200, 200)
                        cv2.circle(frame, pt, 5, col, -1)

                    if is_right:
                        gestures.update(_detect_right(lm))
                    else:
                        gestures.update(_detect_left(lm))

                # HUD
                cv2.rectangle(frame, (0, 0), (w, 120), (10, 14, 26), -1)
                if gestures:
                    hands_str = " · ".join(
                        detected_labels) if detected_labels else ""
                    cv2.putText(
                        frame,
                        hands_str,
                        (10, 18),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (160, 160, 160),
                        1,
                        cv2.LINE_AA,
                    )
                    hud = [
                        (
                            f"BASE:{gestures.get('BASE', -1):3d}  BP:{gestures.get('BASE_PRINCIPAL', -1):3d}",
                            (0, 212, 255),
                        ),
                        (
                            f"EXT1:{gestures.get('EXT1', -1):3d}  EXT2:{gestures.get('EXT2', -1):3d}",
                            (0, 180, 220),
                        ),
                        (f"PINZA:{gestures.get('PINZA', -1):3d}",
                         (0, 150, 190)),
                    ]
                    for i, (txt, col) in enumerate(hud):
                        cv2.putText(
                            frame,
                            txt,
                            (10, 38 + i * 28),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.75,
                            col,
                            2,
                            cv2.LINE_AA,
                        )
                else:
                    cv2.putText(
                        frame,
                        "Sin manos detectadas",
                        (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.85,
                        (100, 116, 139),
                        2,
                        cv2.LINE_AA,
                    )

                if gestures:
                    self._on_gesture(gestures)

                _, buf = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                self._on_frame(base64.b64encode(buf.tobytes()).decode("ascii"))

        finally:
            cap.release()
            landmarker.close()
