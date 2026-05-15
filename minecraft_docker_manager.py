#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import time
from core.config import *
from core.manager import setup_directories, build_image, launch_container, setup_dashboard, setup_playit, check_playit_status, get_playit_address, setup_ngrok, check_ngrok_status, get_ngrok_address, create_backup, interactive_config, show_current_config_summary, docker_menu, show_final_summary, mod_menu
from core.dashboard import MCDashboard
from core.system_check import SystemChecker

def parse_args():
    parser = argparse.ArgumentParser(description="Minecraft Fabric Docker Manager Senior")
    parser.add_argument("--playit", choices=["keep", "new", "reset", "skip"], default="keep")
    parser.add_argument("--tunnel", choices=["playit", "ngrok", "skip"], default=None, help="Elegí el proveedor de túnel (opcional, si no se pone se pregunta)")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dashboard-only", action="store_true", help="Solo abre el dashboard")
    parser.add_argument("--ip", action="store_true", help="Muestra la IP pública del servidor")
    parser.add_argument("-n", type=float, default=2.0, help="Intervalo de refresco del dashboard en segundos (default: 2.0)")
    return parser.parse_args()

def main():
    args = parse_args()

    if args.ip:
        addr = get_playit_address() or get_ngrok_address()
        if addr:
            print(f"\n{Colors.OKGREEN}🚀 Dirección para el Minecraft: {Colors.BOLD}{addr}{Colors.ENDC}\n")
        else:
            print(f"\n{Colors.WARNING}[!] No se pudo encontrar una dirección activa.{Colors.ENDC}")
        return

    if args.dashboard_only:
        try: MCDashboard().run(interval=args.n)
        except KeyboardInterrupt: print("\nDashboard cerrado.")
        return

    # --- MENU PRINCIPAL ---
    while True:
        log("\n--- MC MANAGER: PANEL PRINCIPAL ---", Colors.HEADER)
        print(f"[1] {Colors.OKGREEN}🚀 INICIAR SERVIDOR{Colors.ENDC}")
        print(f"[2] {Colors.OKBLUE}🐳 Gestión de Docker (Logs, Consola, Limpieza){Colors.ENDC}")
        print(f"[3] {Colors.OKBLUE}📊 Abrir Dashboard solamente{Colors.ENDC}")
        print(f"[4] {Colors.OKBLUE}💾 Crear Backup Manual{Colors.ENDC}")
        print(f"[5] {Colors.OKBLUE}📦 Gestión de Mods{Colors.ENDC}")
        print(f"[0] {Colors.BOLD}Salir{Colors.ENDC}")
        
        choice = input(f"\nSelección: ").strip()
        
        if choice == "1":
            start_server_flow(args)
        elif choice == "2":
            docker_menu()
        elif choice == "3":
            try: MCDashboard().run(interval=args.n)
            except KeyboardInterrupt: pass
        elif choice == "4":
            create_backup()
        elif choice == "5":
            mod_menu()
        elif choice == "0":
            log("¡Hasta luego, Senior!", Colors.OKBLUE)
            sys.exit(0)
        else:
            log("Opción no válida.", Colors.FAIL)

def start_server_flow(args):
    # 0. Chequeo de Sistema e Inicialización
    if not SystemChecker.check_all():
        log("No se pudieron verificar las dependencias. Abortando.", Colors.FAIL)
        return
    
    setup_directories()
    
    if not args.yes:
        show_current_config_summary()
        conf_choice = input(f"\n¿Deseas modificar la configuración básica (RAM, Chunks, etc.)? (s/n) [Default: n]: ").strip().lower()
        if conf_choice == 's':
            interactive_config()

    # --- SELECCIÓN DE TÚNEL INTERACTIVA ---
    tunnel = args.tunnel
    if not tunnel:
        log("\n--- CONFIGURACIÓN DE RED ---", Colors.HEADER)
        print("Elegí cómo querés que tus amigos se conecten:")
        print(f"[1] {Colors.BOLD}Playit.gg{Colors.ENDC} (Recomendado: IP fija y fácil de usar)")
        print(f"[2] {Colors.BOLD}Ngrok{Colors.ENDC} (Muy estable: usa TCP directo, pero la IP cambia al reiniciar)")
        print(f"[3] {Colors.BOLD}Saltar{Colors.ENDC} (Si ya tenés puertos abiertos o vas a jugar solo)")
        
        choice = input(f"\nSelección (1-3) [Default: 1]: ").strip()
        if choice == "2": tunnel = "ngrok"
        elif choice == "3": tunnel = "skip"
        else: tunnel = "playit"

    # --- PASO A PASO EXPLICATIVO ---
    log(f"\n--- PASO A PASO: {tunnel.upper()} ---", Colors.HEADER)
    if tunnel == "playit":
        print("1. El script iniciará Playit en una sesión oculta (tmux).")
        print("2. Verificará si ya estás vinculado a tu cuenta.")
        print("3. Si no, te dará un link para que hagas 'Approve' en la web.")
        print("4. Una vez listo, te dará tu IP fija .playit.gg")
    elif tunnel == "ngrok":
        print("1. El script lanzará un túnel TCP mediante Ngrok.")
        print("2. Verificará que tengas el authtoken configurado.")
        print("3. Te dará una IP dinámica (ej: 0.tcp.ngrok.io:12345).")
    else:
        print("1. El servidor arrancará sin túnel externo.")
        print("2. Deberás usar tu IP local o abrir el puerto 25565 en tu router.")

    if not args.yes:
        show_final_summary(tunnel)
        confirm = input(f"\n{Colors.WARNING}¿Confirmás esta configuración para el lanzamiento? (s/n) [Default: s]: {Colors.ENDC}").strip().lower()
        if confirm == 'n':
            log("Lanzamiento cancelado por el usuario.", Colors.FAIL)
            return

    # 2. Imagen
    build_image()

    # 3. Lanzar
    launch_container()

    # 4. Túnel
    if tunnel == "playit":
        setup_playit(args.playit)
        check_func = check_playit_status
        addr_func = get_playit_address
        session_name = PLAYIT_SESSION
    elif tunnel == "ngrok":
        setup_ngrok(args.playit)
        check_func = check_ngrok_status
        addr_func = get_ngrok_address
        session_name = NGROK_SESSION
    else:
        check_func = lambda: (False, "Túnel salteado")
        addr_func = lambda: None
        session_name = None

    # 5. Dashboard Background
    setup_dashboard()
    
    # Lanzar sesión tmux en segundo plano
    cmd_list = ["python3", os.path.abspath(__file__), "--dashboard-only", "-n", str(args.n)]
    subprocess.call(["tmux", "new-session", "-d", "-s", DASHBOARD_SESSION] + cmd_list)

    log("\n--- TODO LISTO ---", Colors.OKGREEN)
    
    # 6. Verificación de Túnel
    if tunnel != "skip":
        log(f"\n--- VERIFICANDO CONEXIÓN {tunnel.upper()} ---", Colors.HEADER)
        connected = False
        for i in range(5):
            connected, status = check_func()
            if connected:
                log(f"Status: {status}", Colors.OKGREEN)
                addr = addr_func()
                if addr:
                    print(f"{Colors.OKGREEN}🚀 Dirección IP: {Colors.BOLD}{addr}{Colors.ENDC}")
                break
            
            if "vinculado" in status.lower():
                log(f"Status: {status}", Colors.WARNING)
                log("\n[!] ACCIÓN REQUERIDA:", Colors.FAIL)
                log(f"1. Abrí otra terminal y ejecutá: {Colors.BOLD}tmux attach -t {session_name}{Colors.ENDC}", Colors.OKBLUE)
                log("2. Seguí el link de vinculación que aparece.", Colors.OKBLUE)
                log("3. Una vez vinculado, esta pantalla se actualizará sola.\n", Colors.OKBLUE)
            else:
                print(f"\rEsperando a {tunnel}... ({i+1}/5) - Estado: {status}   ", end="", flush=True)
            time.sleep(2)

    log(f"\nServer corriendo. Túnel: {tunnel}")
    log(f"Para ver el dashboard: tmux attach -t {DASHBOARD_SESSION}")
    log("Para ver logs en tiempo real:", Colors.HEADER)
    
    try:
        subprocess.call(["docker", "logs", "-f", CONTAINER_NAME])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}--- INTERRUPCIÓN DETECTADA ---{Colors.ENDC}")
        choice = input(f"¿Deseas [a]pagar el servidor por completo o [m]antenerlo en segundo plano? (a/m): ").lower()
        
        if choice == 'a':
            log("Apagando servidor Minecraft...", Colors.FAIL)
            try:
                MCDashboard().rcon_command("stop")
                log("Comando /stop enviado vía RCON. Esperando cierre...", Colors.OKGREEN)
                time.sleep(5)
            except:
                subprocess.call(["docker", "stop", CONTAINER_NAME])
            create_backup()
            subprocess.call(["tmux", "kill-session", "-t", DASHBOARD_SESSION], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            log("Servidor y Dashboard detenidos.", Colors.OKGREEN)
        else:
            create_backup()
            log("\nConsola cerrada. Dashboard y Server siguen en segundo plano.", Colors.OKBLUE)
            log(f"Para volver a entrar: tmux attach -t {DASHBOARD_SESSION}", Colors.OKBLUE)

if __name__ == "__main__":
    main()
