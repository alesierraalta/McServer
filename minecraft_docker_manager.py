#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
from core.config import *
from core.manager import setup_directories, build_image, launch_container, setup_dashboard
from core.dashboard import MCDashboard
from core.system_check import SystemChecker

def parse_args():
    parser = argparse.ArgumentParser(description="Minecraft Fabric Docker Manager Senior")
    parser.add_argument("--playit", choices=["keep", "new", "reset", "skip"], default="keep")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dashboard-only", action="store_true", help="Solo abre el dashboard")
    parser.add_argument("-n", type=float, default=2.0, help="Intervalo de refresco del dashboard en segundos (default: 2.0)")
    return parser.parse_args()

def main():
    args = parse_args()

    if args.dashboard_only:
        try:
            MCDashboard().run(interval=args.n)
        except KeyboardInterrupt:
            print("\nDashboard cerrado.")
        return

    if not args.yes:
        confirm = input(f"{Colors.WARNING}¿Estás listo para iniciar el servidor? (s/n): {Colors.ENDC}")
        if confirm.lower() != 's':
            print("Abortado.")
            sys.exit(0)

    # 0. Chequeo de Sistema (Instalación de dependencias si faltan)
    if not SystemChecker.check_all():
        log("No se pudieron verificar las dependencias. Abortando.", Colors.FAIL)
        sys.exit(1)

    # 1. Preparar entorno
    setup_directories()

    # 2. Imagen
    build_image()

    # 3. Lanzar
    launch_container()

    # 4. Dashboard Background
    setup_dashboard()
    
    # Lanzar sesión tmux en segundo plano con el mismo intervalo si se especificó
    cmd = f"python3 {os.path.abspath(__file__)} --dashboard-only -n {args.n}"
    subprocess.call(["tmux", "new-session", "-d", "-s", DASHBOARD_SESSION, cmd])

    log("\n--- TODO LISTO ---", Colors.OKGREEN)
    log(f"Server corriendo. Playit modo: {args.playit}")
    log(f"Para ver el dashboard: tmux attach -t {DASHBOARD_SESSION}")
    log("Para ver logs en tiempo real:", Colors.HEADER)
    
    try:
        subprocess.call(["docker", "logs", "-f", CONTAINER_NAME])
    except KeyboardInterrupt:
        print("\nConsola cerrada. Dashboard y Server siguen en segundo plano.")

if __name__ == "__main__":
    main()
