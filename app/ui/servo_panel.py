"""
app/ui/servo_panel.py
Control panel: 5 servo sliders + Bluetooth connection UI.

Slider → delta steps → N single-char commands (matches arduino_code.ino).
Each Arduino command moves ±15°. Slider drag calculates how many steps needed.

  BASE    A(+) / D(-)   range 0–180   init 90
  HOMBRO  W(+) / S(-)   range 10–170  init 90
  CODO    K(+) / I(-)   range 0–180   init 90
  MUÑECA  L(+) / J(-)   range 10–160  init 90
  PINZA   C(+) / O(-)   range 110–145 init 110
"""

from __future__ import annotations

import math
import threading
import time

import flet as ft

from app.comm.base import BtComm

STEP = 15  # Arduino moves ±15° per command

SERVOS: list[dict] = [
    {
        "id": "BASE",
        "label": "Base de rotación",
        "sub": "Canal 0 · A/D",
        "icon": ft.Icons.SYNC,
        "plus": "A",
        "minus": "D",
        "init": 90,
        "min": 0,
        "max": 180,
    },
    {
        "id": "BASE_PRINCIPAL",
        "label": "Codo",
        "sub": "Canales 3+6 · W/S",
        "icon": ft.Icons.ARROW_UPWARD,
        "plus": "W",
        "minus": "S",
        "init": 90,
        "min": 10,
        "max": 170,
    },
    {
        "id": "EXT1",
        "label": "Hombro",
        "sub": "Canal 9 · K/I",
        "icon": ft.Icons.TURN_RIGHT,
        "plus": "K",
        "minus": "I",
        "init": 90,
        "min": 0,
        "max": 150,
    },
    {
        "id": "EXT2",
        "label": "Muñeca",
        "sub": "Canal 12 · L/J",
        "icon": ft.Icons.GESTURE,
        "plus": "L",
        "minus": "J",
        "init": 90,
        "min": 10,
        "max": 160,
    },
    {
        "id": "PINZA",
        "label": "Pinza",
        "sub": "Canal 15 · C/O",
        "icon": ft.Icons.OPEN_IN_FULL,
        "plus": "C",
        "minus": "O",
        "init": 110,
        "min": 110,
        "max": 145,
        "vis_step": 5,   # finer slider divisions; actual step is still STEP=15
    },
]

C_BG = "#0F1629"
C_BORDER = "#1A2440"
C_ACCENT = "#00D4FF"
C_PURPLE = "#7C3AED"
C_GREEN = "#10B981"
C_RED = "#EF4444"
C_TEXT = "#E2E8F0"
C_TEXT2 = "#64748B"
C_SURFACE = "#141C2E"

_SERVO_MAP = {s["id"]: s for s in SERVOS}


class ServoPanel(ft.Container):
    """Full servo control panel with connection management."""

    def __init__(self, comm: BtComm, page: ft.Page) -> None:
        super().__init__()
        self._comm = comm
        self._page = page

        # Local angle tracking — mirrors Arduino's objective angles
        self._angles: dict[str, int] = {s["id"]: s["init"] for s in SERVOS}

        # UI refs
        self._sliders: dict[str, ft.Slider] = {}
        self._val_texts: dict[str, ft.Text] = {}

        # Connection UI
        self._devices: list[dict[str, str]] = []
        self._selected_addr: str | None = None

        self._status_dot = ft.Container(
            width=10, height=10, bgcolor=C_RED, border_radius=5
        )
        self._status_label = ft.Text(
            "Desconectado", color=C_RED, size=12, weight=ft.FontWeight.W_500
        )
        self._device_dd = ft.Dropdown(
            hint_text="Seleccionar dispositivo / puerto",
            expand=True,
            text_size=13,
            border_color=C_BORDER,
            focused_border_color=C_ACCENT,
            border_radius=10,
            on_select=self._on_device_selected,
            options=[],
        )
        self._refresh_btn = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_color=C_ACCENT,
            tooltip="Refrescar dispositivos",
            on_click=self._refresh_devices,
        )
        self._btn_label = ft.Text(
            "CONECTAR", weight=ft.FontWeight.BOLD, color="#0A0E1A", size=13
        )
        self._btn_icon = ft.Icon(ft.Icons.BLUETOOTH, color="#0A0E1A", size=18)
        self._connect_btn = ft.Button(
            content=ft.Row(
                [self._btn_icon, self._btn_label],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            bgcolor=C_ACCENT,
            expand=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=self._toggle_connection,
        )

        self.bgcolor = C_BG
        self.border = ft.Border.all(1, C_BORDER)
        self.border_radius = 16
        self.padding = ft.Padding.all(20)
        self.expand = True
        self.content = self._build_content()

    def did_mount(self) -> None:
        self._refresh_devices(None)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_content(self) -> ft.Column:
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.PRECISION_MANUFACTURING, color=C_ACCENT, size=22
                        ),
                        ft.Text(
                            "CONTROL BRAZO",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=C_TEXT,
                            expand=True,
                        ),
                        self._status_dot,
                        ft.Container(width=6),
                        self._status_label,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Divider(height=20, color=C_BORDER),
                ft.Text(
                    "CONEXIÓN BLUETOOTH",
                    size=11,
                    color=C_TEXT2,
                    weight=ft.FontWeight.W_600,
                    style=ft.TextStyle(letter_spacing=1.2),
                ),
                ft.Container(height=8),
                ft.Row(
                    controls=[self._device_dd, self._refresh_btn],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=10),
                self._connect_btn,
                ft.Divider(height=28, color=C_BORDER),
                ft.Row(
                    controls=[
                        ft.Text(
                            "SERVOMOTORES",
                            size=11,
                            color=C_TEXT2,
                            weight=ft.FontWeight.W_600,
                            style=ft.TextStyle(letter_spacing=1.2),
                            expand=True,
                        ),
                        ft.TextButton(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.RESTART_ALT, size=14, color=C_TEXT2
                                    ),
                                    ft.Text("Restablecer", size=11,
                                            color=C_TEXT2),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            on_click=self._reset_all,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=12),
                *[self._build_slider_row(s) for s in SERVOS],
            ],
        )

    def _build_slider_row(self, servo: dict) -> ft.Container:
        sid = servo["id"]
        angle = self._angles[sid]
        rng = servo["max"] - servo["min"]
        divisions = rng // servo.get("vis_step", STEP)

        val_text = ft.Text(
            f"{angle}°",
            color=C_ACCENT,
            size=14,
            weight=ft.FontWeight.BOLD,
            width=44,
            text_align=ft.TextAlign.RIGHT,
        )
        slider = ft.Slider(
            min=servo["min"],
            max=servo["max"],
            value=float(angle),
            divisions=divisions,
            active_color=C_ACCENT,
            inactive_color=C_BORDER,
            thumb_color=C_ACCENT,
            expand=True,
            on_change=lambda e, vt=val_text: self._on_slider_drag(vt, e),
            on_change_end=lambda e, s=servo: self._on_slider_release(s, e),
        )

        self._sliders[sid] = slider
        self._val_texts[sid] = val_text

        return ft.Container(
            margin=ft.Margin.only(bottom=8),
            bgcolor=C_SURFACE,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(servo["icon"], color=C_PURPLE, size=16),
                            ft.Container(width=8),
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text(
                                        servo["label"],
                                        size=13,
                                        weight=ft.FontWeight.W_600,
                                        color=C_TEXT,
                                    ),
                                    ft.Text(servo["sub"],
                                            size=10, color=C_TEXT2),
                                ],
                                expand=True,
                            ),
                            val_text,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    slider,
                ],
            ),
        )

    # ── Slider handlers ───────────────────────────────────────────────────────

    def _on_slider_drag(self, val_text: ft.Text, e: ft.ControlEvent) -> None:
        """Live label update while dragging — no command sent."""
        val_text.value = f"{int(e.control.value)}°"
        val_text.update()

    def _on_slider_release(self, servo: dict, e: ft.ControlEvent) -> None:
        """On release: compute delta steps → send N single-char commands."""
        target = int(e.control.value)
        current = self._angles[servo["id"]]
        diff = target - current
        # ceil so edge positions (e.g. PINZA 110→145) always reach target;
        # Arduino constrain() clamps any overshoot on the hardware side.
        delta = (
            math.ceil(abs(diff) / STEP) * (1 if diff >
                                           0 else -1) if diff != 0 else 0
        )
        if delta == 0:
            return

        char = servo["plus"] if delta > 0 else servo["minus"]
        n = abs(delta)

        # Update local tracking (clamped to real limits)
        actual = max(servo["min"], min(servo["max"], current + delta * STEP))
        self._angles[servo["id"]] = actual

        # Snap slider + label back to actual angle — prevents desync when vis_step < STEP
        sid = servo["id"]
        if sid in self._sliders:
            self._sliders[sid].value = float(actual)
        if sid in self._val_texts:
            self._val_texts[sid].value = f"{actual}°"
        try:
            self._page.update()
        except Exception:
            pass

        def _send() -> None:
            for _ in range(n):
                self._comm.send(char)
                # 60ms between chars — Arduino loop runs every 15ms
                time.sleep(0.06)

        threading.Thread(target=_send, daemon=True).start()

    # ── Public: sync PINZA from gesture panel ────────────────────────────────

    def set_servo_angle(self, sid: str, angle: int) -> None:
        """Update any servo slider display (called from gesture panel, no command sent)."""
        servo = _SERVO_MAP.get(sid)
        if not servo:
            return
        clamped = max(servo["min"], min(servo["max"], angle))
        self._angles[sid] = clamped
        if sid in self._sliders:
            self._sliders[sid].value = float(clamped)
        if sid in self._val_texts:
            self._val_texts[sid].value = f"{clamped}°"
        try:
            self._page.update()
        except Exception:
            pass

    def set_gesture_mode(self, active: bool) -> None:
        """Disable all sliders when gesture mode is active."""
        for slider in self._sliders.values():
            slider.disabled = active
        try:
            self._page.update()
        except Exception:
            pass

    # Keep legacy aliases so existing call sites don't break
    def set_pinza_angle(self, angle: int) -> None:
        self.set_servo_angle("PINZA", angle)

    def set_pinza_enabled(self, enabled: bool) -> None:
        self.set_gesture_mode(not enabled)

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset_all(self, _: ft.ControlEvent) -> None:
        """Send commands to return all servos to Arduino init positions."""
        cmds: list[str] = []
        for servo in SERVOS:
            sid = servo["id"]
            current = self._angles[sid]
            diff = servo["init"] - current
            delta = (
                math.ceil(abs(diff) / STEP) * (1 if diff > 0 else -1)
                if diff != 0
                else 0
            )
            if delta == 0:
                continue
            char = servo["plus"] if delta > 0 else servo["minus"]
            cmds.extend([char] * abs(delta))
            self._angles[sid] = servo["init"]
            if sid in self._sliders:
                self._sliders[sid].value = float(servo["init"])
            if sid in self._val_texts:
                self._val_texts[sid].value = f"{servo['init']}°"
        self._page.update()

        def _send() -> None:
            for c in cmds:
                self._comm.send(c)
                time.sleep(0.06)

        threading.Thread(target=_send, daemon=True).start()

    # ── Connection logic ──────────────────────────────────────────────────────

    def _refresh_devices(self, _: ft.ControlEvent | None) -> None:
        self._device_dd.options = [
            ft.DropdownOption(key="__scanning__",
                              text="Buscando dispositivos...")
        ]
        self._device_dd.value = "__scanning__"
        self._page.update()

        def _scan() -> None:
            self._devices = self._comm.list_devices()
            opts = [
                ft.DropdownOption(
                    key=d["address"], text=f"{d['name']}  —  {d['address']}"
                )
                for d in self._devices
            ]
            if not opts:
                opts = [
                    ft.DropdownOption(
                        key="__none__", text="Sin dispositivos encontrados"
                    )
                ]

            async def _ui() -> None:
                self._device_dd.options = opts
                self._device_dd.value = None
                self._page.update()

            self._page.run_task(_ui)

        threading.Thread(target=_scan, daemon=True).start()

    def _on_device_selected(self, e: ft.ControlEvent) -> None:
        val = e.control.value
        if val and not val.startswith("__"):
            self._selected_addr = val

    def _toggle_connection(self, _: ft.ControlEvent) -> None:
        if self._comm.is_connected:
            self._comm.disconnect()
            self._set_status(connected=False)
            self._btn_icon.name = ft.Icons.BLUETOOTH
            self._btn_icon.color = "#0A0E1A"
            self._btn_label.value = "CONECTAR"
            self._btn_label.color = "#0A0E1A"
            self._connect_btn.bgcolor = C_ACCENT
            self._page.update()
        else:
            if not self._selected_addr:
                return
            self._btn_label.value = "Conectando..."
            self._btn_icon.name = ft.Icons.HOURGLASS_TOP
            self._connect_btn.disabled = True
            self._page.update()

            def _do_connect() -> None:
                # type: ignore[arg-type]
                ok = self._comm.connect(self._selected_addr)
                txt_color = "#E2E8F0" if ok else "#0A0E1A"

                async def _ui() -> None:
                    self._set_status(connected=ok)
                    self._btn_icon.name = (
                        ft.Icons.BLUETOOTH_DISABLED if ok else ft.Icons.BLUETOOTH
                    )
                    self._btn_icon.color = txt_color
                    self._btn_label.value = "DESCONECTAR" if ok else "CONECTAR"
                    self._btn_label.color = txt_color
                    self._connect_btn.bgcolor = C_RED if ok else C_ACCENT
                    self._connect_btn.disabled = False
                    self._page.update()

                self._page.run_task(_ui)

            threading.Thread(target=_do_connect, daemon=True).start()

    def _set_status(self, *, connected: bool) -> None:
        if connected:
            self._status_dot.bgcolor = C_GREEN
            self._status_label.value = "Conectado"
            self._status_label.color = C_GREEN
        else:
            self._status_dot.bgcolor = C_RED
            self._status_label.value = "Desconectado"
            self._status_label.color = C_RED
        self._page.update()
