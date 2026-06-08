"""
app/ui/gesture_panel.py
Camera feed + MediaPipe gesture control panel (Desktop/Web only).

Pipeline: Frame → JPEG → file → Image.src (incremental names, gapless_playback)
gapless_playback=True: old frame stays visible while next loads → no flicker.
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from typing import Callable

import flet as ft

from app.comm.base import BtComm
from app.gesture.hand_tracker import HandTracker

log = logging.getLogger(__name__)

C_BG = "#0F1629"
C_BORDER = "#1A2440"
C_ACCENT = "#00D4FF"
C_PURPLE = "#7C3AED"
C_GREEN = "#10B981"
C_TEXT = "#E2E8F0"
C_TEXT2 = "#64748B"
C_SURFACE = "#141C2E"


class GesturePanel(ft.Container):
    """Camera + gesture control panel."""

    def __init__(
        self,
        comm: BtComm,
        page: ft.Page,
        on_pinza_angle: Callable[[int], None],
        on_pinza_enabled: Callable[[bool], None],
    ) -> None:
        super().__init__()
        self._comm = comm
        self._page = page
        self._on_pinza_angle = on_pinza_angle
        self._on_pinza_enabled = on_pinza_enabled
        self._tracker: HandTracker | None = None
        self._gesture_active = False
        self._last_pinza = 110  # tracks local PINZA state (init matches Arduino)
        self._frame_idx = 0
        self._tmp_dir = tempfile.mkdtemp(prefix="flet_cam_")

        self._cam_dot = ft.Container(
            width=10, height=10, bgcolor=C_TEXT2, border_radius=5
        )
        self._cam_label = ft.Text(
            "Cámara apagada", color=C_TEXT2, size=12, weight=ft.FontWeight.W_500
        )

        self._ph_idle = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=True,
            controls=[
                ft.Icon(ft.Icons.VIDEOCAM_OFF, color=C_TEXT2, size=48),
                ft.Text("Activa el Modo Gestos", color=C_TEXT2, size=13),
            ],
        )
        self._ph_loading = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            visible=False,
            controls=[
                ft.ProgressRing(width=40, height=40, stroke_width=3, color=C_ACCENT),
                ft.Text("Iniciando cámara...", color=C_ACCENT, size=13),
            ],
        )
        self._cam_placeholder = ft.Container(
            expand=True,
            bgcolor=C_SURFACE,
            border_radius=12,
            alignment=ft.Alignment.CENTER,
            content=ft.Stack(
                expand=True,
                alignment=ft.Alignment.CENTER,
                controls=[self._ph_idle, self._ph_loading],
            ),
        )

        # gapless_playback: keep old frame while next loads → no blank gap
        self._cam_img = ft.Image(
            src=self._alloc_frame_path(),
            fit=ft.BoxFit.CONTAIN,
            border_radius=12,
            expand=True,
            visible=False,
            gapless_playback=True,
        )

        self._angle_text = ft.Text(
            "PINZA: --°",
            color=C_ACCENT,
            size=20,
            weight=ft.FontWeight.BOLD,
        )
        self._angle_bar = ft.ProgressBar(
            value=1.0,
            bgcolor=C_BORDER,
            color=C_ACCENT,
            height=6,
            border_radius=3,
        )

        self._toggle = ft.Switch(
            label="Modo Gestos",
            value=False,
            active_color=C_ACCENT,
            label_text_style=ft.TextStyle(
                color=C_TEXT, weight=ft.FontWeight.W_600, size=13
            ),
            on_change=self._on_toggle,
        )

        self.bgcolor = C_BG
        self.border = ft.Border.all(1, C_BORDER)
        self.border_radius = 16
        self.padding = ft.Padding.all(20)
        self.expand = True
        self.content = self._build_content()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_content(self) -> ft.Column:
        return ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CAMERA_ALT, color=C_PURPLE, size=22),
                        ft.Text(
                            "CONTROL POR GESTOS",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=C_TEXT,
                            expand=True,
                        ),
                        self._cam_dot,
                        ft.Container(width=6),
                        self._cam_label,
                        ft.Container(width=12),
                        self._toggle,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=16, color=C_BORDER),
                ft.Container(
                    expand=True,
                    bgcolor=C_SURFACE,
                    border_radius=12,
                    border=ft.Border.all(1, C_BORDER),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Stack(
                        expand=True,
                        controls=[self._cam_placeholder, self._cam_img],
                    ),
                ),
                ft.Container(height=14),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.OPEN_IN_FULL, color=C_ACCENT, size=18),
                        ft.Container(width=8),
                        self._angle_text,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=6),
                self._angle_bar,
                ft.Container(height=12),
                ft.Container(
                    bgcolor=C_SURFACE,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(
                                "Instrucciones de calibración",
                                size=11,
                                color=C_TEXT2,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                "• Pulgar (ID 4) + Índice (ID 8) juntos → PINZA CERRADA (0°)\n"
                                "• Separa los dedos → PINZA ABIERTA (180°)\n"
                                "• Calibra umbral en HandTracker.DIST_MIN / DIST_MAX",
                                size=11,
                                color=C_TEXT2,
                            ),
                        ],
                    ),
                ),
            ],
        )

    # ── Toggle ────────────────────────────────────────────────────────────────

    def _on_toggle(self, e: ft.ControlEvent) -> None:
        self._gesture_active = e.control.value
        if self._gesture_active:
            self._set_cam_status(active=True)
            self._set_placeholder_loading(True)
            self._start_tracker()
            self._on_pinza_enabled(False)
        else:
            self._stop_tracker()
            self._on_pinza_enabled(True)
            self._set_cam_status(active=False)
            self._set_placeholder_loading(False)
            self._angle_text.value = "PINZA: --°"
            self._angle_bar.value = 1.0
            self._cam_img.visible = False
            self._cam_placeholder.visible = True
            try:
                self._page.update()
            except Exception:
                pass

    def _set_placeholder_loading(self, loading: bool) -> None:
        self._ph_idle.visible = not loading
        self._ph_loading.visible = loading

    def _set_cam_status(self, *, active: bool, error: str | None = None) -> None:
        if error:
            self._cam_dot.bgcolor = "#EF4444"
            self._cam_label.value = f"Error: {error}"
            self._cam_label.color = "#EF4444"
        elif active:
            self._cam_dot.bgcolor = C_GREEN
            self._cam_label.value = "Cámara activa"
            self._cam_label.color = C_GREEN
        else:
            self._cam_dot.bgcolor = C_TEXT2
            self._cam_label.value = "Cámara apagada"
            self._cam_label.color = C_TEXT2

    # ── Frame path allocation ─────────────────────────────────────────────────

    def _alloc_frame_path(self) -> str:
        self._frame_idx += 1
        old = os.path.join(self._tmp_dir, f"frame_{self._frame_idx - 5}.jpg")
        if os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass
        return os.path.join(self._tmp_dir, f"frame_{self._frame_idx}.jpg")

    # ── Thread-safe UI post ───────────────────────────────────────────────────

    def _post(self, fn) -> None:
        async def _task():
            try:
                fn()
                self._page.update()
            except Exception as e:
                log.error("UI task error: %s", e)
        self._page.run_task(_task)

    # ── HandTracker lifecycle ─────────────────────────────────────────────────

    def _start_tracker(self) -> None:
        self._tracker = HandTracker(
            on_frame=self._on_frame,
            on_angle=self._on_angle,
            fps_limit=20,
            on_error=self._on_cam_error,
        )
        self._tracker.start()

    def _stop_tracker(self) -> None:
        if self._tracker:
            self._tracker.stop()
            self._tracker = None

    def cleanup(self) -> None:
        """Stop tracker on app shutdown — releases camera and MediaPipe."""
        self._stop_tracker()

    # ── Callbacks (background thread → _post → event loop) ───────────────────

    def _on_cam_error(self, msg: str) -> None:
        log.error("Gesture cam error: %s", msg)
        def _ui():
            self._gesture_active = False
            self._toggle.value = False
            self._cam_img.visible = False
            self._cam_placeholder.visible = True
            self._set_placeholder_loading(False)
            self._set_cam_status(active=False, error=msg)
            self._on_pinza_enabled(True)
        self._post(_ui)

    def _on_frame(self, b64_jpeg: str) -> None:
        # Write file on background thread — no UI here
        try:
            path = self._alloc_frame_path()
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64_jpeg))
        except Exception:
            return
        def _ui():
            self._cam_img.src = path
            if not self._cam_img.visible:
                self._cam_img.visible = True
                self._cam_placeholder.visible = False
                self._set_placeholder_loading(False)
        self._post(_ui)

    def _on_angle(self, gesture_angle: int) -> None:
        # Map gesture 0–180 → Arduino PINZA range 110–145
        target = int(110 + (gesture_angle / 180.0) * 35)
        target = max(110, min(145, target))

        diff = target - self._last_pinza
        if diff > 7:
            self._comm.send("C")  # close +15°
            self._last_pinza = min(145, self._last_pinza + 15)
        elif diff < -7:
            self._comm.send("O")  # open −15°
            self._last_pinza = max(110, self._last_pinza - 15)
        else:
            return  # within deadband, no command

        captured = self._last_pinza
        def _ui():
            self._on_pinza_angle(captured)
            self._angle_text.value = f"PINZA: {captured}°"
            self._angle_bar.value = (captured - 110) / 35.0
        self._post(_ui)
