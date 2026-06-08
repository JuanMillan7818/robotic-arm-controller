"""
app/gesture/hand_tracker.py
MediaPipe Hands-based gesture tracker running in a background thread.

Tracks landmarks 4 (Thumb Tip) and 8 (Index Tip).
Maps their euclidean distance → servo angle for PINZA control:
  - fingers close (dist < DIST_MIN) → angle  0  (grip closed)
  - fingers apart (dist > DIST_MAX) → angle 180  (grip open)

Callbacks are invoked from the background thread — update Flet controls
with control.update() which is thread-safe in Flet ≥ 0.24.
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


def _check_camera_permission() -> str | None:
    """
    Returns an error message if camera access is blocked, else None.
    Only checks on Windows via CapabilityAccessManager registry key.
    """
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
        pass  # registry key absent = no restriction
    return None


class HandTracker:
    """OpenCV + MediaPipe Hands gesture tracker (Desktop/Web only)."""

    THUMB_TIP = 4
    INDEX_TIP = 8
    DIST_MIN = 0.03  # normalized distance → grip fully closed
    DIST_MAX = 0.18  # normalized distance → grip fully open

    def __init__(
        self,
        on_frame: Callable[[str], None],
        on_angle: Callable[[int], None],
        fps_limit: int = 20,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """
        Args:
            on_frame:  called with base64-encoded JPEG string each frame.
            on_angle:  called with pinza angle (0–180) when hand detected.
            fps_limit: max frames per second to process (reduces CPU load).
            on_error:  called with error message if camera fails.
        """
        self._on_frame = on_frame
        self._on_angle = on_angle
        self._on_error = on_error
        self._fps_limit = fps_limit
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background capture thread."""
        log.info(f"Iniciando captura de manos... {self._running}")
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="HandTracker"
        )
        self._thread.start()
        log.info(f"Captura de manos iniciada... {self._running}")

    def stop(self, timeout: float = 2.0) -> None:
        """Signal background thread to stop and wait for it."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ── Background loop ──────────────────────────────────────────────────────

    def _run(self) -> None:  # noqa: C901
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
            log.error("Camera permission denied: %s", perm_err)
            if self._on_error:
                self._on_error(perm_err)
            return

        import urllib.request
        from pathlib import Path
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        # Download model if missing
        model_path = Path(__file__).parent.parent.parent / "assets" / "hand_landmarker.task"
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
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.7,
        )
        landmarker = mp_vision.HandLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            landmarker.close()
            if self._on_error:
                self._on_error("No se pudo abrir la cámara (índice 0)")
            return

        interval = 1.0 / self._fps_limit
        last_t = 0.0
        start_t = time.monotonic()

        # Hand connections for drawing skeleton
        CONNECTIONS = [
            (0,1),(1,2),(2,3),(3,4),       # thumb
            (0,5),(5,6),(6,7),(7,8),        # index
            (0,9),(9,10),(10,11),(11,12),   # middle
            (0,13),(13,14),(14,15),(15,16), # ring
            (0,17),(17,18),(18,19),(19,20), # pinky
            (5,9),(9,13),(13,17),           # palm
        ]

        try:
            while self._running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                now = time.monotonic()
                if now - last_t < interval:
                    continue
                last_t = now

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp_ms = int((now - start_t) * 1000)

                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                angle: int | None = None
                h, w = frame.shape[:2]

                if result.hand_landmarks:
                    lm = result.hand_landmarks[0]
                    thumb = lm[self.THUMB_TIP]
                    index = lm[self.INDEX_TIP]

                    dist = math.sqrt(
                        (thumb.x - index.x) ** 2 + (thumb.y - index.y) ** 2
                    )
                    dist_c = max(self.DIST_MIN, min(self.DIST_MAX, dist))
                    angle = int(
                        (dist_c - self.DIST_MIN) / (self.DIST_MAX - self.DIST_MIN) * 180
                    )

                    # Draw skeleton
                    pts = [(int(p.x * w), int(p.y * h)) for p in lm]
                    for a, b in CONNECTIONS:
                        cv2.line(frame, pts[a], pts[b], (124, 58, 237), 2)
                    for i, pt in enumerate(pts):
                        color = (0, 212, 255) if i in (self.THUMB_TIP, self.INDEX_TIP) else (200, 200, 200)
                        cv2.circle(frame, pt, 5, color, -1)

                # HUD
                cv2.rectangle(frame, (0, 0), (w, 52), (10, 14, 26), -1)
                if angle is not None:
                    status = "CERRADO" if angle < 30 else ("ABIERTO" if angle > 150 else "PARCIAL")
                    hud_text, hud_color = f"PINZA: {angle:3d}  [{status}]", (0, 212, 255)
                else:
                    hud_text, hud_color = "Sin mano detectada", (100, 116, 139)
                cv2.putText(frame, hud_text, (10, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, hud_color, 2, cv2.LINE_AA)

                if angle is not None:
                    self._on_angle(angle)

                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                self._on_frame(b64)

        finally:
            cap.release()
            landmarker.close()
