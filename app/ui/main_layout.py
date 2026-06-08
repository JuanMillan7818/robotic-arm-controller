"""
app/ui/main_layout.py

Desktop layout:
  ┌──────────────────┬─────────────────────────────────┐
  │                  │  [Referencia] [Control Gestos]   │
  │  Control Brazo   ├─────────────────────────────────┤
  │  (sliders + BT)  │  Tab activa:                    │
  │                  │    · Imagen referencia (default) │
  │                  │    · GesturePanel                │
  └──────────────────┴─────────────────────────────────┘

Android: ServoPanel full screen.
"""

from __future__ import annotations

import atexit
import flet as ft

from app.comm.base import BtComm
from app.ui.servo_panel import ServoPanel
from app.ui.gesture_panel import GesturePanel

C_BG = "#0A0E1A"
C_BORDER = "#1A2440"
C_ACCENT = "#00D4FF"
C_TEXT = "#E2E8F0"
C_TEXT2 = "#64748B"
C_SURFACE = "#141C2E"


def _make_comm(page: ft.Page) -> BtComm:
    if page.platform == ft.PagePlatform.ANDROID:
        from app.comm.android_comm import AndroidComm
        return AndroidComm()
    from app.comm.serial_comm import SerialComm
    return SerialComm()


def _build_reference_tab() -> ft.Container:
    return ft.Container(
        expand=True,
        bgcolor=C_SURFACE,
        padding=ft.Padding.all(16),
        content=ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Image(
                    src="brazo_referencia.png",
                    fit=ft.BoxFit.CONTAIN,
                    expand=True,
                    border_radius=10,
                    gapless_playback=True,
                ),
                ft.Text(
                    "Identifica cada motor según el slider",
                    size=11, color=C_TEXT2, text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )


def build_layout(page: ft.Page) -> None:
    page.title = "Robotic Arm Controller"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = C_BG
    page.padding = 0
    page.fonts = {
        "Inter": "https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2",
    }
    page.theme = ft.Theme(font_family="Inter")
    page.window.min_width = 640
    page.window.min_height = 600

    is_android = page.platform == ft.PagePlatform.ANDROID
    comm: BtComm = _make_comm(page)

    servo_panel = ServoPanel(comm=comm, page=page)

    if not is_android:
        gesture_panel = GesturePanel(
            comm=comm,
            page=page,
            on_pinza_angle=servo_panel.set_pinza_angle,
            on_pinza_enabled=servo_panel.set_pinza_enabled,
        )

    # ── Top bar ───────────────────────────────────────────────────────────────
    top_bar = ft.Container(
        height=56,
        bgcolor="#080C18",
        padding=ft.Padding.symmetric(horizontal=20, vertical=0),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.PRECISION_MANUFACTURING, color=C_ACCENT, size=24),
                ft.Container(width=10),
                ft.Text(
                    "ROBOTIC ARM CONTROLLER",
                    size=15, weight=ft.FontWeight.BOLD, color="#E2E8F0",
                    style=ft.TextStyle(letter_spacing=1.5),
                    expand=True,
                ),
                ft.Text(
                    "ANDROID" if is_android else "DESKTOP",
                    size=10, color=C_TEXT2, weight=ft.FontWeight.W_600,
                    style=ft.TextStyle(letter_spacing=1.2),
                ),
            ],
        ),
    )

    # ── Content ───────────────────────────────────────────────────────────────
    if is_android:
        content = ft.Container(
            expand=True,
            padding=ft.Padding.all(12),
            content=servo_panel,
        )
    else:
        # ── Manual tabs (Flet 0.85 Tabs API incompatible with content) ────────
        ref_content = _build_reference_tab()
        gesture_content = ft.Container(
            expand=True,
            content=gesture_panel,  # type: ignore[possibly-undefined]
        )
        gesture_content.visible = False

        def _tab_style(active: bool) -> ft.ButtonStyle:
            return ft.ButtonStyle(
                color=C_ACCENT if active else C_TEXT2,
                bgcolor={"": C_SURFACE if active else "transparent"},
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            )

        tab_ref_btn = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.SCHEMA, size=16), ft.Text("Referencia", size=13)],
                spacing=6, tight=True,
            ),
            style=_tab_style(True),
        )
        tab_gest_btn = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.CAMERA_ALT, size=16), ft.Text("Control Gestos", size=13)],
                spacing=6, tight=True,
            ),
            style=_tab_style(False),
        )

        def _select_tab(idx: int, _: ft.ControlEvent | None = None) -> None:
            ref_content.visible = idx == 0
            gesture_content.visible = idx == 1
            tab_ref_btn.style = _tab_style(idx == 0)
            tab_gest_btn.style = _tab_style(idx == 1)
            page.update()

        tab_ref_btn.on_click = lambda e: _select_tab(0, e)
        tab_gest_btn.on_click = lambda e: _select_tab(1, e)

        right_panel = ft.Container(
            expand=True,
            bgcolor=C_BG,
            border=ft.Border.all(1, C_BORDER),
            border_radius=16,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    # Tab bar
                    ft.Container(
                        bgcolor="#080C18",
                        border_radius=ft.BorderRadius(16, 16, 0, 0),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                        content=ft.Row(
                            controls=[tab_ref_btn, tab_gest_btn],
                            spacing=4,
                        ),
                    ),
                    ft.Divider(height=1, color=C_BORDER),
                    # Tab content (stack — only one visible at a time)
                    ft.Stack(
                        expand=True,
                        controls=[ref_content, gesture_content],
                    ),
                ],
            ),
        )

        content = ft.Container(
            expand=True,
            padding=ft.Padding.all(16),
            content=ft.Row(
                expand=True,
                spacing=16,
                controls=[
                    ft.Container(expand=2, content=servo_panel),
                    ft.Container(expand=3, content=right_panel),
                ],
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    def _shutdown() -> None:
        if not is_android:
            gesture_panel.cleanup()  # type: ignore[possibly-undefined]
        comm.disconnect()

    atexit.register(_shutdown)

    def _on_close(e: ft.WindowEvent) -> None:
        _shutdown()
        page.window.destroy()

    page.window.prevent_close = True
    page.window.on_close = _on_close

    # ── Assemble ──────────────────────────────────────────────────────────────
    page.add(
        ft.Column(
            expand=True,
            spacing=0,
            controls=[top_bar, content],
        )
    )
