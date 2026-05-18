#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path para poder importar core
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.dashboard import MCDashboard
from core.config import *
import subprocess

def debug_dashboard():
    print("--- DEBUG DASHBOARD MONITORING (Senior Tools) ---")
    dashboard = MCDashboard()
    
    print(f"\n[0] Probando Sudo Básico...")
    try:
        # Usar el mismo mecanismo que el dashboard
        askpass_path = root_dir / ".askpass.py"
        env = os.environ.copy()
        env["SUDO_ASKPASS"] = str(askpass_path)
        out = subprocess.check_output(["sudo", "-A", "whoami"], env=env, stderr=subprocess.STDOUT, timeout=5)
        print(f"    Sudo Whoami: {out.decode().strip()}")
    except Exception as e:
        print(f"    Error en Sudo Whoami: {e}")

    print(f"\n[1] Verificando Contenedor: {CONTAINER_NAME}")
    try:
        out = dashboard._exec_docker(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME], timeout=15)
        print(f"    Raw Output: {out}")
        is_running = out.decode().strip() == "true"
    except Exception as e:
        print(f"    Error en _exec_docker: {e}")
        is_running = False
    
    print(f"    ¿Corriendo?: {is_running}")
    
    if is_running:
        print("\n[2] Obteniendo Docker Stats...")
        dashboard.get_docker_stats()
        print(f"    Stats: {dashboard.stats}")
        
        print("\n[3] Obteniendo JVM Stats...")
        jvm_stats = dashboard.get_jvm_stats()
        print(f"    Java PID: {dashboard._java_pid}")
        print(f"    JVM Stats: {jvm_stats}")
        
        print("\n[4] Consultando Servidor (RCON/Túneles)...")
        dashboard.query_server()
        print(f"    Status: {dashboard.server_status}")
        print(f"    TPS: {dashboard.tps}")
        print(f"    MSPT: {dashboard.mspt}")
        print(f"    Entidades: {dashboard.entities}")
        print(f"    Jugadores: {dashboard.players}")
        print(f"    Chunks (cached): {dashboard.chunks}")
        
        print("\n[5] Verificando Túneles...")
        print(f"    Playit: {dashboard.playit_status} ({dashboard.playit_addr})")
        print(f"    Ngrok: {dashboard.ngrok_status} ({dashboard.ngrok_addr})")
    else:
        print("\n[!] El contenedor no está corriendo o no es accesible.")

if __name__ == "__main__":
    debug_dashboard()
