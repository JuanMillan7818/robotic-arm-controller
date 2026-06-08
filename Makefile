# ══════════════════════════════════════════════════════════════════
#  Robotic Arm Controller — Makefile
#  Gestor de comandos para desarrollo, instalación y build.
#
#  Uso:
#    make install      → instalar dependencias (uv sync)
#    make run          → ejecutar en Desktop
#    make web          → ejecutar como webapp (browser)
#    make apk          → compilar APK Android
#    make clean        → limpiar artefactos de build
#    make help         → mostrar esta ayuda
# ══════════════════════════════════════════════════════════════════

# ── Configuración ──────────────────────────────────────────────────
PYTHON     := uv run python
UV         := uv
FLET       := uv run flet
APP_NAME   := robotic-arm-controller
ENTRY      := main.py

# Detectar OS del host
ifeq ($(OS),Windows_NT)
    HOST_OS   := windows
    RM        := rmdir /s /q
    MKDIR     := mkdir
    SEP       := \\
    NULL      := nul
else
    UNAME := $(shell uname -s)
    ifeq ($(UNAME),Darwin)
        HOST_OS := macos
    else
        HOST_OS := linux
    endif
    RM        := rm -rf
    MKDIR     := mkdir -p
    SEP       := /
    NULL      := /dev/null
endif

.DEFAULT_GOAL := help
.PHONY: help install install-android run web apk ipa macos linux clean lint check

# ══════════════════════════════════════════════════════════════════
#  AYUDA
# ══════════════════════════════════════════════════════════════════
help:
	@echo.
	@echo  ╔══════════════════════════════════════════════════════╗
	@echo  ║         ROBOTIC ARM CONTROLLER — Makefile           ║
	@echo  ╠══════════════════════════════════════════════════════╣
	@echo  ║  INSTALACION                                         ║
	@echo  ║    make install         Instalar deps (uv sync)      ║
	@echo  ║    make install-android Agregar flet[build] para APK ║
	@echo  ║                                                      ║
	@echo  ║  EJECUCION                                           ║
	@echo  ║    make run             Lanzar app Desktop           ║
	@echo  ║    make web             Lanzar como webapp en browser ║
	@echo  ║                                                      ║
	@echo  ║  BUILD MOVIL / ESCRITORIO                            ║
	@echo  ║    make apk             Compilar APK Android         ║
	@echo  ║    make ipa             Compilar IPA iOS (macOS)     ║
	@echo  ║    make macos           Compilar app macOS           ║
	@echo  ║    make linux           Compilar binario Linux       ║
	@echo  ║    make windows         Compilar EXE Windows         ║
	@echo  ║                                                      ║
	@echo  ║  UTILIDADES                                          ║
	@echo  ║    make clean           Limpiar artefactos build     ║
	@echo  ║    make lint            Verificar codigo (ruff)      ║
	@echo  ║    make check           Verificar imports del proyecto║
	@echo  ╚══════════════════════════════════════════════════════╝
	@echo.

# ══════════════════════════════════════════════════════════════════
#  INSTALACIÓN
# ══════════════════════════════════════════════════════════════════

## Instalar dependencias base con uv
install:
	@echo [INSTALL] Sincronizando dependencias con uv...
	$(UV) sync
	@echo [OK] Dependencias instaladas.

## Agregar flet[build] necesario para compilar APK / IPA
install-android:
	@echo [INSTALL] Agregando flet con soporte de build movil...
	$(UV) add "flet[build]"
	$(UV) sync
	@echo [OK] Listo para build movil.

# ══════════════════════════════════════════════════════════════════
#  EJECUCIÓN LOCAL
# ══════════════════════════════════════════════════════════════════

## Lanzar app en modo Desktop nativo
run:
	@echo [RUN] Iniciando Robotic Arm Controller (Desktop)...
	$(PYTHON) $(ENTRY)

## Lanzar app como webapp en el navegador por defecto
web:
	@echo [RUN] Iniciando en modo Web (http://localhost:8550)...
	$(FLET) run --web --port 8550 $(ENTRY)

# ══════════════════════════════════════════════════════════════════
#  BUILD — MÓVIL
# ══════════════════════════════════════════════════════════════════

## Compilar APK para Android (requiere: make install-android + Android SDK)
apk:
	@echo [BUILD] Compilando APK Android...
	@echo [INFO]  Requiere Android SDK configurado y 'make install-android'
	$(FLET) build apk --project $(APP_NAME)
	@echo [OK] APK generado en build/apk/

## Compilar IPA para iOS (solo macOS + Xcode)
ipa:
	@echo [BUILD] Compilando IPA iOS...
	@echo [INFO]  Solo disponible en macOS con Xcode instalado
	$(FLET) build ipa --project $(APP_NAME)
	@echo [OK] IPA generado en build/ipa/

# ══════════════════════════════════════════════════════════════════
#  BUILD — ESCRITORIO
# ══════════════════════════════════════════════════════════════════

## Compilar aplicacion nativa Windows (.exe)
windows:
	@echo [BUILD] Compilando app Windows...
	$(FLET) build windows --project $(APP_NAME)
	@echo [OK] EXE generado en build/windows/

## Compilar aplicacion nativa macOS (.app)
macos:
	@echo [BUILD] Compilando app macOS...
	$(FLET) build macos --project $(APP_NAME)
	@echo [OK] App generada en build/macos/

## Compilar binario Linux
linux:
	@echo [BUILD] Compilando binario Linux...
	$(FLET) build linux --project $(APP_NAME)
	@echo [OK] Binario generado en build/linux/

# ══════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════

## Verificar que todos los imports del proyecto funcionan
check:
	@echo [CHECK] Verificando imports...
	$(PYTHON) -c "\
from app.comm.base import BtComm; \
from app.comm.serial_comm import SerialComm; \
from app.comm.android_comm import AndroidComm; \
from app.gesture.hand_tracker import HandTracker; \
from app.ui.servo_panel import ServoPanel; \
from app.ui.gesture_panel import GesturePanel; \
from app.ui.main_layout import build_layout; \
print('[OK] Todos los modulos importan correctamente')"

## Verificar codigo con ruff (instalar con: uv add --dev ruff)
lint:
	@echo [LINT] Analizando codigo con ruff...
	$(UV) run ruff check app/ main.py
	@echo [OK] Sin errores de lint.

## Limpiar artefactos de compilacion
clean:
	@echo [CLEAN] Eliminando artefactos de build...
ifeq ($(HOST_OS),windows)
	-if exist build $(RM) build
	-if exist dist  $(RM) dist
	-if exist .flet $(RM) .flet
	-for /d /r . %%d in (__pycache__) do @if exist "%%d" $(RM) "%%d"
else
	$(RM) build/ dist/ .flet/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>$(NULL) || true
	find . -name "*.pyc" -delete 2>$(NULL) || true
endif
	@echo [OK] Limpieza completada.
