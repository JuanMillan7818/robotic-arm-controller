"""
test_serial.py — Validación de comunicación serial con Arduino.

Uso:
    uv run python test_serial.py              # lista puertos disponibles
    uv run python test_serial.py COM6         # secuencia de prueba en COM6
    uv run python test_serial.py COM6 --loop  # envío continuo con delay
"""

import sys
import time
import argparse

COMMANDS = {
    "BASE+":  "A",  # Base +15°
    "BASE-":  "D",  # Base -15°
    "BP+":    "W",  # Base Principal +15°
    "BP-":    "S",  # Base Principal -15°
    "EXT1+":  "K",  # Extensión 1 +15°
    "EXT1-":  "I",  # Extensión 1 -15°
    "EXT2+":  "L",  # Extensión 2 +15°
    "EXT2-":  "J",  # Extensión 2 -15°
    "PINZA+": "C",  # Pinza cerrar
    "PINZA-": "O",  # Pinza abrir
}

TEST_SEQUENCE = [
    ("BASE+",  3, "Base → derecha 45°"),
    ("BASE-",  3, "Base → izquierda 45° (vuelve)"),
    ("BP+",    2, "Base Principal → arriba 30°"),
    ("BP-",    2, "Base Principal → abajo 30° (vuelve)"),
    ("EXT1+",  2, "Extensión 1 → abre 30°"),
    ("EXT1-",  2, "Extensión 1 → cierra 30° (vuelve)"),
    ("PINZA+", 2, "Pinza → cierra"),
    ("PINZA-", 2, "Pinza → abre (vuelve)"),
]


def list_ports() -> None:
    import serial.tools.list_ports
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No se encontraron puertos COM.")
        return
    print(f"\n{'Puerto':<10} {'Descripción':<45} {'HWID'}")
    print("-" * 90)
    for p in sorted(ports, key=lambda x: x.device):
        print(f"{p.device:<10} {p.description:<45} {p.hwid or ''}")


def run_test(port: str, baud: int = 9600, loop: bool = False) -> None:
    import serial

    print(f"\nConectando a {port} @ {baud} baud...")
    try:
        conn = serial.Serial(port=port, baudrate=baud, timeout=2, write_timeout=2)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Conectado: {conn.portstr}  is_open={conn.is_open}\n")

    def send(char: str) -> None:
        conn.write(char.encode("utf-8"))
        conn.flush()
        print(f"  Enviado: {char!r}  ({char})")

    try:
        iterations = 0
        while True:
            iterations += 1
            print(f"\n─── Secuencia #{iterations} ───────────────────────────")
            for name, n, desc in TEST_SEQUENCE:
                char = COMMANDS[name]
                print(f"\n[{name}] {desc}")
                for i in range(n):
                    send(char)
                    time.sleep(0.08)  # 80ms entre chars
                time.sleep(0.5)       # pausa entre movimientos

            if not loop:
                break
            print("\n↻ Repitiendo (Ctrl+C para salir)...")
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nAbortado.")
    finally:
        conn.close()
        print("Puerto cerrado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test serial Arduino")
    parser.add_argument("port", nargs="?", help="Puerto COM (ej. COM6)")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--loop", action="store_true", help="Repetir secuencia")
    args = parser.parse_args()

    if not args.port:
        list_ports()
        print("\nUso: uv run python test_serial.py <PUERTO>")
        return

    run_test(args.port, args.baud, args.loop)


if __name__ == "__main__":
    main()
