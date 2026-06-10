"""
app/ui/gesture_panel.py
Camera feed + 5-axis gesture control panel (Desktop only).

Gesture → target angle per motor → delta steps → single-char commands.
Deadband ±7° prevents jitter commands.
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
from typing import Callable

import flet as ft

from app.comm.base import BtComm
from app.gesture.hand_tracker import HandTracker

log = logging.getLogger(__name__)

C_BG      = "#0F1629"
C_BORDER  = "#1A2440"
C_ACCENT  = "#00D4FF"
C_PURPLE  = "#7C3AED"
C_GREEN   = "#10B981"
C_TEXT    = "#E2E8F0"
C_TEXT2   = "#64748B"
C_SURFACE = "#141C2E"

STEP = 15  # Arduino step size per command

# Motor config mirroring arduino_code.ino
_MOTORS: dict[str, dict] = {
    # deadband: angle diff needed to trigger one step (≥ STEP avoids jitter oscillation)
    # min_interval: min seconds between commands per motor
    "BASE":           {"plus": "A", "minus": "D", "init": 90,  "min": 0,   "max": 180, "deadband": 20, "min_interval": 0.2},
    "BASE_PRINCIPAL": {"plus": "W", "minus": "S", "init": 90,  "min": 10,  "max": 170, "deadband": 20, "min_interval": 0.2},
    "EXT1":           {"plus": "K", "minus": "I", "init": 90,  "min": 0,   "max": 180, "deadband": 15, "min_interval": 0.15},
    "EXT2":           {"plus": "L", "minus": "J", "init": 90,  "min": 10,  "max": 160, "deadband": 15, "min_interval": 0.15},
    "PINZA":          {"plus": "C", "minus": "O", "init": 110, "min": 110, "max": 145, "deadband": 10, "min_interval": 0.5},
}

_MOTOR_LABELS = {
    "BASE":           "Base",
    "BASE_PRINCIPAL": "Base Principal",
    "EXT1":           "Ext. 1",
    "EXT2":           "Ext. 2",
    "PINZA":          "Pinza",
}


class GesturePanel(ft.Container):
    """Camera + 5-axis gesture control panel."""

    def __init__(
        self,
        comm: BtComm,
        page: ft.Page,
        on_servo_angle: Callable[[str, int], None],
        on_gesture_active: Callable[[bool], None],
    ) -> None:
        super().__init__()
        self._comm             = comm
        self._page             = page
        self._on_servo_angle   = on_servo_angle
        self._on_gesture_active = on_gesture_active
        self._tracker: HandTracker | None = None
        self._gesture_active   = False
        self._closing          = False   # set before join to unblock HandTracker thread
        self._frame_idx        = 0
        self._tmp_dir          = tempfile.mkdtemp(prefix="flet_cam_")

        # Local motor angle tracking (mirrors Arduino objectives)
        self._angles: dict[str, int] = {mid: m["init"] for mid, m in _MOTORS.items()}
        # Per-motor last-command timestamp for rate limiting
        self._last_cmd_t: dict[str, float] = {mid: 0.0 for mid in _MOTORS}

        # Camera status indicator
        self._cam_dot = ft.Container(width=10, height=10, bgcolor=C_TEXT2, border_radius=5)
        self._cam_label = ft.Text("Cámara apagada", color=C_TEXT2, size=12, weight=ft.FontWeight.W_500)

        # Placeholder
        self._ph_idle = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10, visible=True,
            controls=[
                ft.Icon(ft.Icons.VIDEOCAM_OFF, color=C_TEXT2, size=48),
                ft.Text("Activa el Modo Gestos", color=C_TEXT2, size=13),
            ],
        )
        self._ph_loading = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14, visible=False,
            controls=[
                ft.ProgressRing(width=40, height=40, stroke_width=3, color=C_ACCENT),
                ft.Text("Iniciando cámara...", color=C_ACCENT, size=13),
            ],
        )
        self._cam_placeholder = ft.Container(
            expand=True, bgcolor=C_SURFACE, border_radius=12,
            alignment=ft.Alignment.CENTER,
            content=ft.Stack(
                expand=True,
                alignment=ft.Alignment.CENTER,
                controls=[self._ph_idle, self._ph_loading],
            ),
        )

        # Live feed
        self._cam_img = ft.Image(
            src="placeholder",
            fit=ft.BoxFit.CONTAIN,
            border_radius=12,
            expand=True,
            visible=False,
            gapless_playback=True,
        )

        # Motor angle readouts (5 chips)
        self._motor_texts: dict[str, ft.Text] = {
            mid: ft.Text(
                f"{_MOTOR_LABELS[mid]}: {self._angles[mid]}°",
                color=C_TEXT2, size=11, weight=ft.FontWeight.W_500,
            )
            for mid in _MOTORS
        }

        # Toggle
        self._toggle = ft.Switch(
            label="Modo Gestos",
            value=False,
            active_color=C_ACCENT,
            label_text_style=ft.TextStyle(color=C_TEXT, weight=ft.FontWeight.W_600, size=13),
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
        motor_row = ft.Row(
            controls=list(self._motor_texts.values()),
            wrap=True,
            spacing=12,
            run_spacing=4,
        )
        return ft.Column(
            expand=True, spacing=0,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CAMERA_ALT, color=C_PURPLE, size=22),
                        ft.Text("CONTROL POR GESTOS", size=14, weight=ft.FontWeight.BOLD,
                                color=C_TEXT, expand=True),
                        self._cam_dot,
                        ft.Container(width=6),
                        self._cam_label,
                        ft.Container(width=12),
                        self._toggle,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=10, color=C_BORDER),
                motor_row,
                ft.Divider(height=10, color=C_BORDER),
                ft.Container(
                    expand=True, bgcolor=C_SURFACE, border_radius=12,
                    border=ft.Border.all(1, C_BORDER),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Stack(
                        expand=True,
                        controls=[self._cam_placeholder, self._cam_img],
                    ),
                ),
                ft.Divider(height=10, color=C_BORDER),
                ft.Container(
                    bgcolor=C_SURFACE, border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                    content=ft.Column(spacing=2, controls=[
                        ft.Text("Gestos", size=11, color=C_TEXT2, weight=ft.FontWeight.W_600),
                        ft.Text(
                            "✋ Izquierda: X posición → Base  ·  Abierta/Puño → Base Principal\n"
                            "🤚 Derecha: Abierta/Puño → Ext.1  ·  Inclinación → Ext.2\n"
                            "   ☝️ Solo índice → Pinza abre  ·  Índice+Medio → Pinza cierra",
                            size=11, color=C_TEXT2,
                        ),
                    ]),
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
            self._on_gesture_active(True)
        else:
            self._stop_tracker()
            self._on_gesture_active(False)
            self._set_cam_status(active=False)
            self._set_placeholder_loading(False)
            self._cam_img.visible = False
            self._cam_placeholder.visible = True
            try:
                self._page.update()
            except Exception:
                pass

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

    def _set_placeholder_loading(self, loading: bool) -> None:
        self._ph_idle.visible    = not loading
        self._ph_loading.visible = loading

    # ── Frame path ────────────────────────────────────────────────────────────

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
        if self._closing:
            return  # UI thread may be in join() — drop task to prevent deadlock
        async def _task():
            try:
                fn()
                self._page.update()
            except Exception as exc:
                log.error("UI task error: %s", exc)
        self._page.run_task(_task)

    # ── HandTracker lifecycle ─────────────────────────────────────────────────

    def _start_tracker(self) -> None:
        self._tracker = HandTracker(
            on_frame=self._on_frame,
            on_gesture=self._on_gesture,
            fps_limit=20,
            on_error=self._on_cam_error,
        )
        self._tracker.start()

    def _stop_tracker(self) -> None:
        if self._tracker:
            self._tracker.stop()
            self._tracker = None

    def cleanup(self) -> None:
        self._closing = True   # drop all _post calls before joining thread
        self._stop_tracker()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_cam_error(self, msg: str) -> None:
        log.error("Gesture cam error: %s", msg)
        def _ui():
            self._gesture_active = False
            self._toggle.value = False
            self._cam_img.visible = False
            self._cam_placeholder.visible = True
            self._set_placeholder_loading(False)
            self._set_cam_status(active=False, error=msg)
            self._on_gesture_active(False)
        self._post(_ui)

    def _on_frame(self, b64_jpeg: str) -> None:
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

    def _on_gesture(self, gestures: dict[str, int]) -> None:
        """Receive target angles for all motors, send delta commands."""
        updates: dict[str, int] = {}
        now = time.monotonic()

        for mid, target in gestures.items():
            cfg     = _MOTORS[mid]
            current = self._angles[mid]
            diff    = target - current

            # Rate limit: skip if motor commanded too recently
            if now - self._last_cmd_t[mid] < cfg["min_interval"]:
                continue

            db = cfg["deadband"]
            if diff > db:
                self._comm.send(cfg["plus"])
                self._angles[mid] = min(cfg["max"], current + STEP)
                updates[mid]      = self._angles[mid]
                self._last_cmd_t[mid] = now
            elif diff < -db:
                self._comm.send(cfg["minus"])
                self._angles[mid] = max(cfg["min"], current - STEP)
                updates[mid]      = self._angles[mid]
                self._last_cmd_t[mid] = now

        if not updates:
            return

        captured = dict(updates)

        def _ui():
            for mid, angle in captured.items():
                # Update gesture panel readout chips
                self._motor_texts[mid].value = f"{_MOTOR_LABELS[mid]}: {angle}°"
                # Sync servo panel sliders
                self._on_servo_angle(mid, angle)
        self._post(_ui)
