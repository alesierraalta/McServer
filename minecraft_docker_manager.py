#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import time
from core.config import *
from core.manager import setup_directories, build_image, launch_container, setup_dashboard, setup_playit, check_playit_status, get_playit_address, setup_ngrok, check_ngrok_status, get_ngrok_address, create_backup
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
            print(f"Estado Playit: {check_playit_status()[1]}")
            print(f"Estado Ngrok: {check_ngrok_status()[1]}\n")
        return

    if args.dashboard_only:
        try:
            MCDashboard().run(interval=args.n)
        except KeyboardInterrupt:
            print("\nDashboard cerrado.")
        return

    # 0. Chequeo de Sistema e Inicialización
    if not SystemChecker.check_all():
        log("No se pudieron verificar las dependencias. Abortando.", Colors.FAIL)
        sys.exit(1)
    
    setup_directories()

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
        confirm = input(f"\n{Colors.WARNING}¿Confirmás esta configuración? (s/n): {Colors.ENDC}")
        if confirm.lower() != 's':
            print("Abortado.")
            sys.exit(0)

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
    
    # Lanzar sesión tmux en segundo plano con el mismo intervalo si se especificó
    cmd_list = ["python3", os.path.abspath(__file__), "--dashboard-only", "-n", str(args.n)]
    subprocess.call(["tmux", "new-session", "-d", "-s", DASHBOARD_SESSION] + cmd_list)

    log("\n--- TODO LISTO ---", Colors.OKGREEN)
    
    # 6. Verificación de Túnel (Bucle de espera activo)
    if tunnel != "skip":
        log(f"\n--- VERIFICANDO CONEXIÓN {tunnel.upper()} ---", Colors.HEADER)
        connected = False
        for i in range(5): # Esperar hasta 10 segundos (5 * 2s)
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
        
        if not connected and "vinculado" not in status.lower():
            log(f"\n[!] No se pudo establecer la conexión {tunnel.upper()}.", Colors.FAIL)
            log(f"Último estado: {status}", Colors.WARNING)
            
            if tunnel == "playit":
                log(f"Acciones sugeridas para Playit:", Colors.HEADER)
                log(f"- [v]incular: Ver el link de conexión (tmux attach).", Colors.OKBLUE)
                log(f"- [reset]: Borrar configuración y empezar de cero.", Colors.OKBLUE)
                choice = input(f"\n¿Qué deseás hacer? [r]eintentar, [v]incular, [reset], [s]altear, o [q]uit: ").lower()
                
                if choice == 'v':
                    log(f"\nEjecutá esto en otra terminal: {Colors.BOLD}tmux attach -t {session_name}{Colors.ENDC}", Colors.OKGREEN)
                    log("Buscá el link que dice 'Visit link to setup' y abrilo.", Colors.OKBLUE)
                    input("Presioná ENTER cuando hayas terminado para reintentar...")
                    return main()
                elif choice == 'reset':
                    setup_playit("reset")
                    return main()
            
            elif tunnel == "ngrok":
                choice = input(f"\n¿Qué deseás hacer? [r]eintentar, [c]ambiar API key, [s]altear, o [q]uit: ").lower()
                if choice == 'c':
                    token = input(f"Ingresá el nuevo Authtoken: ").strip()
                    if token:
                        subprocess.call(["ngrok", "config", "add-authtoken", token])
                        log("Token actualizado. Reintentando...", Colors.OKGREEN)
                        return main()
            
            else:
                choice = input(f"\n¿Qué deseás hacer? [r]eintentar, [s]altear, o [q]uit: ").lower()

            if choice == 'r':
                return main()
            elif choice == 'q':
                sys.exit(0)
            log("Continuando sin túnel verificado...", Colors.WARNING)

    print() # Nueva línea
    log(f"Server corriendo. Túnel: {tunnel}")
    
    log(f"Para ver el dashboard: tmux attach -t {DASHBOARD_SESSION}")
    log("Para ver logs en tiempo real:", Colors.HEADER)
    
    try:
        subprocess.call(["docker", "logs", "-f", CONTAINER_NAME])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}--- INTERRUPCIÓN DETECTADA ---{Colors.ENDC}")
        choice = input(f"¿Deseas [a]pagar el servidor por completo o [m]antenerlo en segundo plano? (a/m): ").lower()
        
        if choice == 'a':
            log("Apagando servidor Minecraft...", Colors.FAIL)
            # Intentamos un apagado limpio vía RCON si el dashboard está disponible, sino docker stop
            try:
                MCDashboard().rcon_command("stop")
                log("Comando /stop enviado vía RCON. Esperando cierre...", Colors.OKGREEN)
                time.sleep(5) # Dar tiempo a que cierre
            except:
                subprocess.call(["docker", "stop", CONTAINER_NAME])
            
            # Backup después de apagar
            create_backup()

            # Limpieza de sesiones tmux (silenciosa)
            subprocess.call(["tmux", "kill-session", "-t", DASHBOARD_SESSION], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            log("Servidor y Dashboard detenidos.", Colors.OKGREEN)
        else:
            # Backup antes de desconectar la consola (server sigue prendido)
            create_backup()
            log("\nConsola cerrada. Dashboard y Server siguen en segundo plano.", Colors.OKBLUE)
            log(f"Para volver a entrar: tmux attach -t {DASHBOARD_SESSION}", Colors.OKBLUE)

if __name__ == "__main__":
    main()
