# 🤖 Robotic Arm Controller

Controlador multiplataforma para brazo robótico de 6 servos, construido con **Flet + MediaPipe + Bluetooth HC-05**.

| Plataforma | Control | Bluetooth |
|------------|---------|-----------|
| Desktop (Windows/Linux/macOS) | Sliders + Gestos con cámara | HC-05 vía puerto COM virtual |
| Android APK | Sliders | HC-05 RFCOMM nativo (pyjnius) |

---

## 🧱 Arquitectura

```
robotic-arm-controller/
├── main.py                        # Entry point → ft.app()
├── app/
│   ├── comm/
│   │   ├── base.py                # Clase abstracta BtComm
│   │   ├── serial_comm.py         # Desktop → pyserial (COM port)
│   │   └── android_comm.py       # Android → pyjnius RFCOMM
│   ├── gesture/
│   │   └── hand_tracker.py       # MediaPipe Hands — landmarks 4↔8
│   └── ui/
│       ├── main_layout.py         # Layout responsive (platform detection)
│       ├── servo_panel.py         # 6 sliders + conexión BT
│       └── gesture_panel.py      # Cámara + toggle modo gestos
├── pyproject.toml
└── .gitignore
```

### Protocolo de comunicación

Todos los comandos siguen el mismo formato de texto plano:

```
SERVO_ID:ANGULO\n
```

Ejemplos:

```
BASE:90\n
HOMBRO_F:45\n
PINZA:0\n      ← cerrado
PINZA:180\n    ← abierto
```

### Servomotores

| ID         | Descripción           | Rango  |
|------------|-----------------------|--------|
| `BASE`     | Base rotatoria        | 0–180° |
| `HOMBRO_F` | Hombro delantero      | 0–180° |
| `HOMBRO_B` | Hombro trasero        | 0–180° |
| `CODO`     | Codo                  | 0–180° |
| `MUÑECA`   | Muñeca                | 0–180° |
| `PINZA`    | Pinza (abre/cierra)   | 0–180° |

---

## ⚙️ Setup — Desktop

### 1. Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) instalado

### 2. Instalar dependencias

```bash
uv sync
```

### 3. Parear HC-05 en Windows

1. Configuración → Bluetooth → Agregar dispositivo → seleccionar `HC-05`
2. PIN: `1234` (por defecto)
3. Ir a **Más opciones de Bluetooth → Puertos COM** — anotar el puerto *saliente* (ej. `COM3`)

### 4. Ejecutar

```bash
uv run python main.py
```

La app detecta automáticamente todos los puertos COM disponibles.
Seleccionar el puerto del HC-05 y presionar **CONECTAR**.

---

## 📱 Setup — Android APK

### Requisitos adicionales

- Android SDK (API 21+)
- `flet` con soporte de build: `uv add flet[build]`

### Compilar APK

```bash
flet build apk
```

El APK lista los dispositivos Bluetooth **emparejados** en el teléfono.
No requiere OpenCV ni MediaPipe.

---

## 🖐️ Control por Gestos (Desktop/Web)

Usa **MediaPipe Hands** para controlar la PINZA en tiempo real:

| Gesto | Resultado |
|-------|-----------|
| Pulgar + Índice juntos | `PINZA:0\n` (cerrado) |
| Pulgar + Índice separados | `PINZA:180\n` (abierto) |

Calibración: editar `HandTracker.DIST_MIN` / `DIST_MAX` en
[`app/gesture/hand_tracker.py`](app/gesture/hand_tracker.py).

---

## 🔧 Firmware Arduino (referencia)

El receptor en el brazo debe parsear el protocolo `ID:ANGULO\n`:

```cpp
#include <Servo.h>
#include <SoftwareSerial.h>
SoftwareSerial bt(10, 11); // RX, TX

Servo servos[6];
// IDs: BASE, HOMBRO_F, HOMBRO_B, CODO, MUÑECA, PINZA

void loop() {
  if (bt.available()) {
    String cmd = bt.readStringUntil('\n'); // ej. "PINZA:90"
    int sep = cmd.indexOf(':');
    if (sep > 0) {
      String id  = cmd.substring(0, sep);
      int    ang = cmd.substring(sep + 1).toInt();
      // mapear id → servo y escribir ángulo
    }
  }
}
```

---

## 📦 Dependencias

| Paquete | Uso |
|---------|-----|
| `flet>=0.24` | UI framework multiplataforma |
| `opencv-python>=4.9` | Captura de cámara (Desktop) |
| `mediapipe>=0.10` | Detección de mano / gestos (Desktop) |
| `pyserial>=3.5` | Comunicación HC-05 vía COM port (Desktop) |
| `pyjnius` | Puente Java para Bluetooth nativo Android (APK) |

---

## 👥 Contexto académico

> **HUS-001** — Sistema Multiplataforma de Control Adaptable para Brazo Robótico
> Asignatura: Robótica — Semestre 7 — INTEP
