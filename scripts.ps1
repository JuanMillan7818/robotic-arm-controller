#!/usr/bin/env pwsh
# Robotic Arm Controller - Scripts de arranque para Windows (PowerShell)
# Equivalente al Makefile para sistemas sin GNU make instalado.
#
# Uso:
#   .\scripts.ps1 install
#   .\scripts.ps1 run
#   .\scripts.ps1 web
#   .\scripts.ps1 apk
#   .\scripts.ps1 windows
#   .\scripts.ps1 check
#   .\scripts.ps1 clean
#   .\scripts.ps1 help

param(
    [Parameter(Position=0)]
    [ValidateSet("help","install","install-android","run","web","apk","ipa","macos","linux","windows","check","lint","clean")]
    [string]$Command = "help"
)

$APP_NAME = "robotic-arm-controller"
$ENTRY    = "main.py"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "  >> $msg" -ForegroundColor Cyan
    Write-Host ""
}

function Assert-UV {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "[ERROR] uv no encontrado. Instalar desde https://docs.astral.sh/uv/" -ForegroundColor Red
        exit 1
    }
}

switch ($Command) {

    "help" {
        Write-Host ""
        Write-Host "  ROBOTIC ARM CONTROLLER - scripts.ps1" -ForegroundColor Cyan
        Write-Host "  =====================================" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  INSTALACION:"
        Write-Host "    install          Instalar deps (uv sync)"
        Write-Host "    install-android  Agregar flet[build] para APK"
        Write-Host ""
        Write-Host "  EJECUCION:"
        Write-Host "    run              Lanzar app Desktop"
        Write-Host "    web              Lanzar como webapp en browser (port 8550)"
        Write-Host ""
        Write-Host "  BUILD MOVIL / ESCRITORIO:"
        Write-Host "    apk              Compilar APK Android"
        Write-Host "    ipa              Compilar IPA iOS (solo macOS + Xcode)"
        Write-Host "    windows          Compilar EXE Windows"
        Write-Host "    macos            Compilar app macOS"
        Write-Host "    linux            Compilar binario Linux"
        Write-Host ""
        Write-Host "  UTILIDADES:"
        Write-Host "    check            Verificar imports del proyecto"
        Write-Host "    lint             Analizar codigo con ruff"
        Write-Host "    clean            Limpiar artefactos build"
        Write-Host ""
    }

    "install" {
        Write-Step "[INSTALL] Sincronizando dependencias con uv..."
        Assert-UV
        uv sync
        Write-Host "[OK] Dependencias instaladas." -ForegroundColor Green
    }

    "install-android" {
        Write-Step "[INSTALL] Agregando flet con soporte build movil..."
        Assert-UV
        uv add "flet[build]"
        uv sync
        Write-Host "[OK] Listo para build movil." -ForegroundColor Green
    }

    "run" {
        Write-Step "[RUN] Iniciando Robotic Arm Controller (Desktop)..."
        Assert-UV
        uv run python $ENTRY
    }

    "web" {
        Write-Step "[RUN] Iniciando en modo Web http://localhost:8550"
        Assert-UV
        uv run flet run --web --port 8550 $ENTRY
    }

    "apk" {
        Write-Step "[BUILD] Compilando APK Android..."
        Write-Host "  Requiere: make install-android + Android SDK configurado" -ForegroundColor Yellow
        Assert-UV
        uv run flet build apk --project $APP_NAME
        Write-Host "[OK] APK generado en build/apk/" -ForegroundColor Green
    }

    "ipa" {
        Write-Step "[BUILD] Compilando IPA iOS..."
        Write-Host "  Solo disponible en macOS con Xcode instalado" -ForegroundColor Yellow
        Assert-UV
        uv run flet build ipa --project $APP_NAME
        Write-Host "[OK] IPA generado en build/ipa/" -ForegroundColor Green
    }

    "windows" {
        Write-Step "[BUILD] Compilando aplicacion Windows (.exe)..."
        Assert-UV
        uv run flet build windows --project $APP_NAME
        Write-Host "[OK] EXE generado en build/windows/" -ForegroundColor Green
    }

    "macos" {
        Write-Step "[BUILD] Compilando aplicacion macOS (.app)..."
        Assert-UV
        uv run flet build macos --project $APP_NAME
        Write-Host "[OK] App generada en build/macos/" -ForegroundColor Green
    }

    "linux" {
        Write-Step "[BUILD] Compilando binario Linux..."
        Assert-UV
        uv run flet build linux --project $APP_NAME
        Write-Host "[OK] Binario generado en build/linux/" -ForegroundColor Green
    }

    "check" {
        Write-Step "[CHECK] Verificando imports del proyecto..."
        Assert-UV
        $tmp = [System.IO.Path]::GetTempFileName() -replace "\.tmp$",".py"
        $proj = (Get-Location).Path.Replace("\","\\")
        $lines = @(
            "import sys; sys.path.insert(0, r`"$proj`")",
            "from app.comm.base import BtComm",
            "from app.comm.serial_comm import SerialComm",
            "from app.comm.android_comm import AndroidComm",
            "from app.gesture.hand_tracker import HandTracker",
            "from app.ui.servo_panel import ServoPanel",
            "from app.ui.gesture_panel import GesturePanel",
            "from app.ui.main_layout import build_layout",
            "print(`"OK - Todos los modulos importan correctamente`")"
        )
        $lines | Set-Content -Path $tmp -Encoding UTF8
        uv run python $tmp
        Remove-Item $tmp -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Imports verificados." -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Fallo en imports. Revisar dependencias." -ForegroundColor Red
            exit 1
        }
    }

    "lint" {
        Write-Step "[LINT] Analizando codigo con ruff..."
        Assert-UV
        uv run ruff check app/ main.py
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Sin errores de lint." -ForegroundColor Green
        }
    }

    "clean" {
        Write-Step "[CLEAN] Eliminando artefactos de build..."
        foreach ($d in @("build","dist",".flet")) {
            if (Test-Path $d) {
                Remove-Item -Recurse -Force $d
                Write-Host "  Eliminado: $d" -ForegroundColor DarkGray
            }
        }
        Get-ChildItem -Recurse -Filter "__pycache__" -Directory |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Recurse -Filter "*.pyc" |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Limpieza completada." -ForegroundColor Green
    }
}
