"""
main.py — Entry point for Robotic Arm Controller.

Run (Desktop):
    uv run python main.py

Build APK (Android):
    flet build apk
"""

import logging
import sys
import threading

import flet as ft

from app.ui.main_layout import build_layout

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Silence noisy Flet internals — only show our app logs
for _noisy in ("flet_transport", "flet_controls", "flet", "asyncio"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

log = logging.getLogger(__name__)


def _warm_up_libs() -> None:
    """Import cv2 + mediapipe in background so cache files are written before
    Flet's watchdog starts monitoring. Avoids hot-reload false triggers."""
    def _do():
        try:
            import cv2  # noqa: F401
            import mediapipe  # noqa: F401
            log.info("cv2 + mediapipe warm-up done")
        except Exception as e:
            log.warning("warm-up failed (no camera libs?): %s", e)

    if sys.platform != "android":
        threading.Thread(target=_do, daemon=True, name="WarmUp").start()


def main() -> None:
    _warm_up_libs()
    ft.run(build_layout)


if __name__ == "__main__":
    main()
