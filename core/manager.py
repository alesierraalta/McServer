import os
import subprocess
import time
from core.config import *

def get_server_properties():
    properties = {}
    path = HOST_CONFIG_DIR / "server.properties"
    if not path.exists():
        return properties
    try:
        with open(path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        properties[parts[0].strip()] = parts[1].strip()
    except: pass
    return properties

def show_current_config_summary():
    props = get_server_properties()
    log("\n--- CONFIGURACIÓN ACTUAL ---", Colors.HEADER)
    print(f"  {Colors.OKBLUE}Memoria:{Colors.ENDC} Juego {RAM_GB}GB | Contenedor {CONTAINER_RAM_GB}GB")
    print(f"  {Colors.OKBLUE}Renderizado:{Colors.ENDC} {props.get('view-distance', '10')} chunks")
    print(f"  {Colors.OKBLUE}Jugadores:{Colors.ENDC} {props.get('max-players', '20')}")
    print(f"  {Colors.OKBLUE}Dificultad:{Colors.ENDC} {props.get('difficulty', 'normal')}")
    print(f"  {Colors.OKBLUE}Modo de juego:{Colors.ENDC} {props.get('gamemode', 'survival')}")
    print(f"  {Colors.OKBLUE}MOTD:{Colors.ENDC} {props.get('motd', 'A Minecraft Server')}")

def show_final_summary(tunnel_type):
    props = get_server_properties()
    log("\n--- RESUMEN DE LANZAMIENTO ---", Colors.HEADER)
    print(f"  {Colors.OKGREEN}Hardware:{Colors.ENDC} RAM {RAM_GB}GB (Juego) | {CONTAINER_RAM_GB}GB (Docker)")
    print(f"  {Colors.OKGREEN}Mundo:{Colors.ENDC} {props.get('view-distance', '10')} Chunks | {props.get('max-players', '20')} Players")
    print(f"  {Colors.OKGREEN}Red:{Colors.ENDC} Túnel {tunnel_type.upper()}")
    print(f"  {Colors.OKGREEN}Otros:{Colors.ENDC} {props.get('difficulty', 'normal')} | {props.get('gamemode', 'survival')}")

def update_server_properties(updates: dict):
    config_path = HOST_CONFIG_DIR / "server.properties"
    if not config_path.exists():
        # Crear inicial si no existe
        content = f"server-port={SERVER_PORT}\nonline-mode=false\nmotd=Minecraft Docker Senior\nenable-query=true\nquery.port={SERVER_PORT}\nenable-rcon=true\nrcon.password=senior_architect\n"
        config_path.write_text(content)
    
    with open(config_path, "r") as f: lines = f.readlines()
    
    new_lines = []; seen = set()
    for line in lines:
        if "=" in line:
            key = line.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                seen.add(key); continue
        new_lines.append(line)
    
    for key, val in updates.items():
        if key not in seen: new_lines.append(f"{key}={val}\n")
    
    with open(config_path, "w") as f: f.writelines(new_lines)
    log(f"Propiedades del servidor actualizadas: {list(updates.keys())}", Colors.OKGREEN)

def docker_menu():
    while True:
        log("\n--- GESTIÓN DE DOCKER (Senior Panel) ---", Colors.HEADER)
        print(f"[1] {Colors.OKBLUE}Ver Logs (Live){Colors.ENDC}")
        print(f"[2] {Colors.OKBLUE}Entrar a la Consola (Bash){Colors.ENDC}")
        print(f"[3] {Colors.OKBLUE}Estado del Contenedor (Stats){Colors.ENDC}")
        print(f"[4] {Colors.WARNING}Reiniciar Contenedor{Colors.ENDC}")
        print(f"[5] {Colors.FAIL}LIMPIEZA TOTAL (Borrar Contenedor e Imagen){Colors.ENDC}")
        print(f"[0] {Colors.BOLD}Volver al menú principal{Colors.ENDC}")
        
        choice = input(f"\nSelección: ").strip()
        
        if choice == "1":
            log("Entrando a logs... (Presioná Ctrl+C para salir de los logs, el server seguirá corriendo)", Colors.WARNING)
            try: subprocess.call(["docker", "logs", "-f", CONTAINER_NAME])
            except KeyboardInterrupt: pass
        
        elif choice == "2":
            log(f"Conectando a {CONTAINER_NAME}...", Colors.OKGREEN)
            subprocess.call(["docker", "exec", "-it", CONTAINER_NAME, "/bin/bash"])
        
        elif choice == "3":
            subprocess.call(["docker", "ps", "-f", f"name={CONTAINER_NAME}"])
            print("\nConsumo de recursos:")
            subprocess.call(["docker", "stats", CONTAINER_NAME, "--no-stream"])
            input("\nPresioná ENTER para volver...")
            
        elif choice == "4":
            log("Reiniciando contenedor...", Colors.WARNING)
            subprocess.call(["docker", "restart", CONTAINER_NAME])
            log("Contenedor reiniciado.", Colors.OKGREEN)
            
        elif choice == "5":
            confirm = input(f"{Colors.FAIL}¿Estás SEGURO de borrar TODO? (s/n): {Colors.ENDC}").lower()
            if confirm == 's':
                log("Borrando contenedor...", Colors.FAIL)
                subprocess.call(["docker", "rm", "-f", CONTAINER_NAME], stderr=subprocess.DEVNULL)
                log("Borrando imagen...", Colors.FAIL)
                subprocess.call(["docker", "rmi", IMAGE_NAME], stderr=subprocess.DEVNULL)
                log("Limpieza completada. Deberás iniciar el server de nuevo para reconstruir.", Colors.OKGREEN)
                time.sleep(2)
        
        elif choice == "0":
            break
        else:
            log("Opción no válida.", Colors.FAIL)

def interactive_config():
    global RAM_GB, CONTAINER_RAM_GB
    log("\n--- CONFIGURACIÓN BÁSICA DEL SERVIDOR ---", Colors.HEADER)
    print(f"{Colors.BOLD}Recomendaciones:{Colors.ENDC}")
    print(f"  - {Colors.OKBLUE}Potato:{Colors.ENDC} Dist: 6, RAM JUEGO: 2, RAM CONT: 3")
    print(f"  - {Colors.OKGREEN}Normal:{Colors.ENDC} Dist: 10, RAM JUEGO: 4, RAM CONT: 5")
    print(f"  - {Colors.WARNING}Senior:{Colors.ENDC} Dist: 16+, RAM JUEGO: 8, RAM CONT: 10")
    print("\nDejá en blanco para mantener el valor actual o el default.")
    
    updates = {}
    
    # 1. Distancia de renderizado
    vd = input(f"Distancia de renderizado (chunks) [Default: 10]: ").strip()
    if vd: updates["view-distance"] = vd
    
    # 2. Máximo de jugadores
    mp = input(f"Máximo de jugadores [Default: 20]: ").strip()
    if mp: updates["max-players"] = mp
    
    # 3. Dificultad
    print(f"\nDificultad: [0] peaceful, [1] easy, [2] normal, [3] hard")
    diff = input(f"Selección (0-3) [Default: 2]: ").strip()
    diff_map = {"0": "peaceful", "1": "easy", "2": "normal", "3": "hard"}
    if diff in diff_map: updates["difficulty"] = diff_map[diff]
    
    # 4. Modo de juego
    print(f"\nModo de juego: [0] survival, [1] creative, [2] adventure, [3] spectator")
    gm = input(f"Selección (0-3) [Default: 0]: ").strip()
    gm_map = {"0": "survival", "1": "creative", "2": "adventure", "3": "spectator"}
    if gm in gm_map: updates["gamemode"] = gm_map[gm]
    
    # 5. MOTD
    motd = input(f"\nMensaje del día (MOTD): ").strip()
    if motd: updates["motd"] = motd

    # 6. RAM Dual
    print(f"\n{Colors.BOLD}Configuración de Memoria:{Colors.ENDC}")
    ram_j = input(f"RAM para el JUEGO (Xmx) [Default: {RAM_GB}GB]: ").strip()
    ram_c = input(f"RAM para el CONTENEDOR (Limit) [Default: {CONTAINER_RAM_GB}GB]: ").strip()
    
    if ram_j or ram_c:
        new_j = int(ram_j) if ram_j else RAM_GB
        new_c = int(ram_c) if ram_c else CONTAINER_RAM_GB
        
        if new_j > new_c:
            log(f"Error: La RAM del juego ({new_j}GB) no puede ser mayor a la del contenedor ({new_c}GB).", Colors.FAIL)
            log(f"Ajustando RAM del contenedor a {new_j + 1}GB por seguridad.", Colors.WARNING)
            new_c = new_j + 1
            
        RAM_GB = new_j
        CONTAINER_RAM_GB = new_c
        log(f"Memoria configurada: Juego {RAM_GB}GB | Contenedor {CONTAINER_RAM_GB}GB", Colors.OKGREEN)

    if updates:
        update_server_properties(updates)
    else:
        log("No se realizaron cambios adicionales en la configuración.", Colors.OKBLUE)

def ensure_server_config():
    updates = {
        "enable-rcon": "true", "rcon.password": "senior_architect", "rcon.port": "25575",
        "enable-query": "true", "query.port": "25565", "broadcast-rcon-to-ops": "true"
    }
    update_server_properties(updates)
    log("Configuración técnica de RCON/Query verificada.", Colors.OKGREEN)

import zipfile
import json
import shutil
from datetime import datetime

def inspect_mod(jar_path):
    try:
        with zipfile.ZipFile(jar_path, 'r') as zip_ref:
            # Check for Fabric
            if 'fabric.mod.json' in zip_ref.namelist():
                with zip_ref.open('fabric.mod.json') as f:
                    data = json.load(f)
                    env = data.get('environment', '*')
                    return 'Fabric', env, data.get('name', data.get('id', 'Unknown'))
            
            # Check for Forge (modern)
            if 'META-INF/mods.toml' in zip_ref.namelist():
                return 'Forge', 'both', 'Unknown Forge Mod'
                    
    except:
        return 'Error', 'unknown', 'Error'
    
    return 'Unknown', 'both', 'Unknown'

def organize_mods():
    log("\n--- ORGANIZADOR DE MODS (Senior Architect Edition) ---", Colors.HEADER)
    source_dir = PROJECT_DIR / "mods"
    mods_c = PROJECT_DIR / "modsC"
    # mods_s es temporal para organizar, el destino final para el server es 'mods'
    # pero para no borrar el origen mientras procesamos, usamos una subcarpeta
    temp_s = PROJECT_DIR / ".temp_mods_s"
    
    for d in [mods_c, temp_s]: d.mkdir(exist_ok=True)
    
    jar_files = list(source_dir.glob("*.jar"))
    if not jar_files:
        log("No se encontraron mods (.jar) en la carpeta /mods", Colors.WARNING)
        return

    log(f"Analizando {len(jar_files)} mods...", Colors.OKBLUE)
    
    # Limpiar destinos
    for f in mods_c.glob("*.jar"): f.unlink()
    for f in temp_s.glob("*.jar"): f.unlink()
    
    stats = {"client_only": 0, "server_only": 0, "both": 0, "error": 0}
    results = []

    for jar in jar_files:
        loader, env, name = inspect_mod(jar)
        
        # Lógica de lados (Sides)
        # '*' o missing = AMBOS
        # 'client' = SOLO CLIENTE
        # 'server' = SOLO SERVIDOR
        
        is_client = env in ['client', '*']
        is_server = env in ['server', '*']
        
        if is_client:
            shutil.copy2(jar, mods_c / jar.name)
        if is_server:
            shutil.copy2(jar, temp_s / jar.name)
            
        env_str = "Ambos" if env == '*' else ("Cliente" if env == 'client' else "Servidor")
        if env == 'Error': env_str = "Error"; stats["error"] += 1
        elif env == '*': stats["both"] += 1
        elif env == 'client': stats["client_only"] += 1
        elif env == 'server': stats["server_only"] += 1
        
        results.append(f"{Colors.BOLD}{jar.name}{Colors.ENDC} -> {Colors.OKBLUE}{env_str}{Colors.ENDC}")

    # Sincronizar temp_s con mods (el directorio del server)
    # IMPORTANTE: El usuario quiere que 'mods' sea el del server.
    # Pero 'mods' es nuestra fuente ahora mismo. 
    # Para no romper el flujo, vamos a avisar antes de sobreescribir la fuente.
    
    log("\nResultados del análisis:", Colors.HEADER)
    for res in results: print(f"  - {res}")
    
    log("\nResumen:", Colors.OKGREEN)
    print(f"  - 🖥️  Solo Cliente (en modsC): {stats['client_only']}")
    print(f"  - ☁️  Solo Servidor: {stats['server_only']}")
    print(f"  - 🔄  Ambos Lados: {stats['both']}")
    
    print(f"\n{Colors.WARNING}[!] IMPORTANTE:{Colors.ENDC}")
    print(f"Los mods de CLIENTE (cliente + ambos) están en: {Colors.BOLD}/modsC{Colors.ENDC}")
    print(f"Los mods de SERVIDOR (servidor + ambos) están listos para ser movidos a /mods")
    
    confirm = input(f"\n¿Deseas actualizar la carpeta /mods con la selección de servidor? (s/n): ").lower()
    if confirm == 's':
        # Mover de temp a mods
        for f in source_dir.glob("*.jar"): f.unlink()
        for f in temp_s.glob("*.jar"):
            shutil.move(str(f), str(source_dir / f.name))
        shutil.rmtree(temp_s)
        log("Carpeta /mods actualizada para el servidor.", Colors.OKGREEN)
    else:
        shutil.rmtree(temp_s)
        log("No se modificó la carpeta /mods. Los archivos filtrados de servidor se perdieron (repetí el proceso si querés aplicarlos).", Colors.WARNING)

def list_mods():
    log("\n--- LISTADO DE MODS INSTALADOS ---", Colors.HEADER)
    source_dir = PROJECT_DIR / "mods"
    jar_files = list(source_dir.glob("*.jar"))
    
    if not jar_files:
        log("No hay mods en /mods", Colors.WARNING)
        return
        
    print(f"{'Archivo':<40} | {'Nombre Real':<30} | {'Lado'}")
    print("-" * 85)
    for jar in jar_files:
        loader, env, name = inspect_mod(jar)
        env_str = "Ambos" if env == '*' else ("Cliente" if env == 'client' else "Servidor")
        print(f"{jar.name[:38]:<40} | {name[:28]:<30} | {env_str}")

def mod_menu():
    while True:
        log("\n--- GESTIÓN DE MODS ---", Colors.HEADER)
        print("[1] 🔍 Clasificar y Organizar Mods (modsC y mods Server)")
        print("[2] 📄 Listar Mods con Detalle")
        print("[0] Volver")
        
        choice = input(f"\nSelección: ").strip()
        
        if choice == "1":
            organize_mods()
        elif choice == "2":
            list_mods()
        elif choice == "0":
            break
        else:
            log("Opción no válida.", Colors.FAIL)

import zipfile
from datetime import datetime

def create_backup():
    # Definimos qué queremos respaldar para que sea portable
    backup_targets = [
        HOST_WORLD_DIR,
        HOST_MODS_DIR,
        HOST_CONFIG_DIR,
        PLAYIT_SECRET
    ]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"full_server_backup_{timestamp}.zip"
    
    log(f"Creando backup completo en {backup_file}...", Colors.HEADER)
    try:
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for target in backup_targets:
                if not target.exists(): continue
                
                if target.is_dir():
                    for root, dirs, files in os.walk(target):
                        for file in files:
                            file_path = Path(root) / file
                            # Guardamos ruta relativa al proyecto
                            zipf.write(file_path, file_path.relative_to(PROJECT_DIR))
                else:
                    # Es un archivo individual (ej: playit.toml)
                    zipf.write(target, target.relative_to(PROJECT_DIR))
                    
        log("Backup completo guardado con éxito.", Colors.OKGREEN)
    except Exception as e:
        log(f"Error creando backup: {e}", Colors.FAIL)

def restore_latest_backup():
    backup_dir = PROJECT_DIR / "backups"
    if not backup_dir.exists(): return False
    
    backups = list(backup_dir.glob("full_server_backup_*.zip"))
    if not backups:
        log("No se encontraron backups para restaurar.", Colors.WARNING)
        return False
    
    latest_backup = max(backups, key=os.path.getctime)
    log(f"Restaurando el backup más reciente: {latest_backup.name}", Colors.HEADER)
    
    try:
        with zipfile.ZipFile(latest_backup, 'r') as zipf:
            zipf.extractall(PROJECT_DIR)
        log("Restauración completa exitosa.", Colors.OKGREEN)
        return True
    except Exception as e:
        log(f"Error al restaurar: {e}", Colors.FAIL)
        return False

def setup_directories():
    log("--- 1. PREPARANDO ENTORNO ---", Colors.HEADER)
    for d in [DOCKER_DIR, HOST_MODS_DIR, HOST_WORLD_DIR, HOST_LOGS_DIR, HOST_CONFIG_DIR, PROJECT_DIR / "backups"]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Si la carpeta world está vacía (solo la carpeta creada sin archivos dentro), intentamos restaurar
    world_files = list(HOST_WORLD_DIR.iterdir())
    if not world_files:
        log("Carpeta 'world' vacía. Buscando backups para restaurar...", Colors.WARNING)
        restore_latest_backup()

    ensure_server_config()
    configs = {
        "eula.txt": "eula=true\n",
        "server.properties": f"server-port={SERVER_PORT}\nonline-mode=false\nmotd=Minecraft Docker Senior\nenable-query=true\nquery.port={SERVER_PORT}\nenable-rcon=true\nrcon.password=senior_architect\n",
        "ops.json": "[]\n", "whitelist.json": "[]\n"
    }
    for name, content in configs.items():
        f = HOST_CONFIG_DIR / name
        if not f.exists():
            f.write_text(content)
            log(f"Config inicial creada: {name}", Colors.OKGREEN)

def build_image():
    log("--- 2. VERIFICANDO IMAGEN DOCKER ---", Colors.HEADER)
    if subprocess.call(["docker", "inspect", IMAGE_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
        log("Imagen ya existe. Saltando build.", Colors.OKGREEN)
        return
    dockerfile_content = f"""
FROM eclipse-temurin:21-jdk
RUN apt-get update && apt-get install -y curl iproute2 procps jq ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /server
RUN set -eux; \\
    INSTALLER_VERSION="$(curl -fsSL https://meta.fabricmc.net/v2/versions/installer | jq -r '.[0].version')"; \\
    LOADER_VERSION="$(curl -fsSL https://meta.fabricmc.net/v2/versions/loader/{MINECRAFT_VERSION} | jq -r '.[0].loader.version')"; \\
    curl -fL -o fabric-installer.jar "https://maven.fabricmc.net/net/fabricmc/fabric-installer/${{INSTALLER_VERSION}}/fabric-installer-${{INSTALLER_VERSION}}.jar"; \\
    java -jar fabric-installer.jar server -mcversion "{MINECRAFT_VERSION}" -loader "${{LOADER_VERSION}}" -downloadMinecraft -dir /server; \\
    mkdir -p /server/mods /server/world /server/logs && \\
    chown -R 1000:1000 /server
USER 1000:1000
RUN printf '#!/usr/bin/env sh\\necho "eula=true" > /server/eula.txt\\nexec java -Xms1G -Xmx${{MAX_RAM:-4}}G -jar fabric-server-launch.jar nogui\\n' > /server/start.sh && chmod +x /server/start.sh
EXPOSE {SERVER_PORT} 25575
CMD ["/server/start.sh"]
"""
    DOCKER_DIR.mkdir(exist_ok=True)
    (DOCKER_DIR / "Dockerfile").write_text(dockerfile_content)
    log("Construyendo imagen... (esto puede tardar)", Colors.WARNING)
    # Forzamos rebuild si cambiamos el Dockerfile
    subprocess.check_call(["docker", "build", "--no-cache", "-t", IMAGE_NAME, str(DOCKER_DIR)])
    log("Imagen construida con éxito.", Colors.OKGREEN)

def setup_playit(mode):
    if mode == "skip": return
    
    session_name = PLAYIT_SESSION
    # Matar sesión previa si existe o si pedimos restart (new/reset)
    if mode in ["new", "reset"]:
        subprocess.call(["tmux", "kill-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    # Verificar si ya está corriendo (para modo 'keep')
    res = subprocess.call(["tmux", "has-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if res == 0 and mode == "keep":
        log("Playit ya está corriendo en tmux.", Colors.OKGREEN)
        return

    if mode == "reset":
        if PLAYIT_SECRET.exists(): PLAYIT_SECRET.unlink()
        if PLAYIT_LOG_FILE.exists(): PLAYIT_LOG_FILE.unlink()
        log("Configuración de Playit reseteada.", Colors.WARNING)

    # Preparar comando
    # Usamos --log_path para el log y --secret_path para el secreto
    cmd = f"playit --secret_path {PLAYIT_SECRET} --log_path {PLAYIT_LOG_FILE} start"
    
    # Lanzar sesión tmux usando lista para evitar problemas de shell
    subprocess.call(["tmux", "new-session", "-d", "-s", session_name, cmd])
    log(f"Sesión tmux '{session_name}' lanzada.", Colors.OKGREEN)

def check_playit_status():
    if not PLAYIT_LOG_FILE.exists():
        return False, "Esperando log..."
    
    try:
        with open(PLAYIT_LOG_FILE, "r") as f:
            lines = f.readlines()[-20:] # Leer últimas 20 líneas
            content = "".join(lines).lower()
            if "tunnel established" in content or "connected" in content:
                return True, "Conectado"
            if "claim" in content or "visit" in content or "approve" in content:
                return False, "No vinculado (ver tmux)"
            if "error" in content:
                return False, "Error de conexión"
            return False, "Iniciando..."
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_playit_address():
    addr_file = HOST_CONFIG_DIR / "playit_address.txt"
    if not PLAYIT_LOG_FILE.exists():
        if addr_file.exists(): return addr_file.read_text().strip()
        return None
    
    try:
        with open(PLAYIT_LOG_FILE, "r") as f:
            content = f.read()
            import re
            # 1. Patrón oficial de asignación
            match = re.search(r'address: "([^"]+)"', content)
            if match:
                addr = match.group(1)
                addr_file.write_text(addr)
                return addr
            
            # 2. Dominios comunes de Playit v0.17+
            # Buscamos .playit.gg, .gl.at.ply.gg, .gl.joinmc.link
            patterns = [r'([\w-]+\.playit\.gg)', r'([\w-]+\.gl\.at\.ply\.gg)', r'([\w-]+\.gl\.joinmc\.link)']
            for p in patterns:
                match = re.search(p, content)
                if match:
                    addr = match.group(1)
                    # Intentamos capturar el puerto si está pegado
                    port_match = re.search(rf'{re.escape(addr)}:(\d+)', content)
                    if port_match: addr = f"{addr}:{port_match.group(1)}"
                    addr_file.write_text(addr)
                    return addr
    except: pass
    
    if addr_file.exists(): return addr_file.read_text().strip()
    return None

def is_ngrok_configured():
    """Verifica si ngrok tiene un authtoken configurado"""
    try:
        # ngrok config check devuelve 0 si el archivo es válido y tiene token
        res = subprocess.call(["ngrok", "config", "check"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res == 0
    except:
        return False

def setup_ngrok(mode):
    if mode == "skip": return
    
    # 1. Verificar Token antes de arrancar
    if not is_ngrok_configured():
        log("\n[!] NGROK REQUIERE CONFIGURACIÓN", Colors.FAIL)
        print(f"1. Create una cuenta en {Colors.OKBLUE}https://dashboard.ngrok.com{Colors.ENDC}")
        print(f"2. Copiá tu 'Authtoken' de la web.")
        print(f"3. Pegalo abajo (o dejá en blanco para saltear):\n")
        
        token = input(f"Ingresá tu authtoken: ").strip()
        if token:
            subprocess.call(["ngrok", "config", "add-authtoken", token])
            log("Token configurado con éxito.", Colors.OKGREEN)
        else:
            log("No se configuró el token. Ngrok probablemente fallará.", Colors.WARNING)

    session_name = NGROK_SESSION
    if mode in ["new", "reset"]:
        subprocess.call(["tmux", "kill-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    res = subprocess.call(["tmux", "has-session", "-t", session_name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    if res == 0 and mode == "keep":
        log("Ngrok ya está corriendo en tmux.", Colors.OKGREEN)
        return

    # Comando para Ngrok (TCP en el puerto del server)
    # Agregamos --log=stdout para que tmux no se cierre si hay error inmediato
    cmd = f"ngrok tcp {SERVER_PORT}"
    
    subprocess.call(["tmux", "new-session", "-d", "-s", session_name, cmd])
    log(f"Sesión tmux '{session_name}' lanzada para Ngrok.", Colors.OKGREEN)

def check_ngrok_status():
    import requests
    try:
        # Ngrok tiene una API local en el puerto 4040
        resp = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if resp.status_code == 200:
            tunnels = resp.json().get("tunnels", [])
            if tunnels:
                return True, "Conectado"
        return False, "Buscando túnel..."
    except:
        return False, "Ngrok no responde (¿está abierto?)"

def get_ngrok_address():
    import requests
    try:
        resp = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        if resp.status_code == 200:
            tunnels = resp.json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "tcp":
                    # Ngrok devuelve tcp://0.tcp.ngrok.io:12345
                    return t.get("public_url").replace("tcp://", "")
    except: pass
    return None

def fix_permissions():
    """Usa un contenedor temporal para devolver la propiedad de los archivos al usuario host"""
    log("Asegurando permisos de archivos...", Colors.HEADER)
    try:
        # 1. Chown recursivo para el usuario 1000
        subprocess.call([
            "docker", "run", "--rm",
            "-v", f"{PROJECT_DIR}:/data",
            "busybox", "chown", "-R", "1000:1000", "/data"
        ])
        # 2. Corregir permisos: Directorios 755, Archivos 644
        # Usamos find para ser precisos
        subprocess.call([
            "docker", "run", "--rm",
            "-v", f"{PROJECT_DIR}:/data",
            "busybox", "sh", "-c", "find /data -type d -exec chmod 755 {} +"
        ])
        subprocess.call([
            "docker", "run", "--rm",
            "-v", f"{PROJECT_DIR}:/data",
            "busybox", "sh", "-c", "find /data -type f -exec chmod 644 {} +"
        ])
    except Exception as e:
        log(f"Error asegurando permisos: {e}", Colors.FAIL)

def launch_container():
    log("--- 3. LANZANDO CONTENEDOR ---", Colors.HEADER)
    subprocess.call(["docker", "stop", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.call(["docker", "rm", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Corregimos permisos antes de lanzar
    fix_permissions()

    cmd = [
        "docker", "run", "-d", "--name", CONTAINER_NAME,
        # Ya no necesitamos -u aquí si lo pusimos en el Dockerfile, pero no molesta
        "-u", "1000:1000", 
        "-p", f"{SERVER_PORT}:{SERVER_PORT}", "-p", "25575:25575",
        "-e", f"MAX_RAM={RAM_GB}",
        "--restart", "unless-stopped", "--memory", f"{CONTAINER_RAM_GB}g",
        "-v", f"{HOST_MODS_DIR}:/server/mods",
        "-v", f"{HOST_WORLD_DIR}:/server/world",
        "-v", f"{HOST_LOGS_DIR}:/server/logs",
        "-v", f"{HOST_CONFIG_DIR}/server.properties:/server/server.properties",
        IMAGE_NAME
    ]
    subprocess.check_call(cmd)
    log(f"Contenedor {CONTAINER_NAME} iniciado.", Colors.OKGREEN)

def setup_dashboard():
    log("--- 4. PREPARANDO DASHBOARD ---", Colors.HEADER)
    subprocess.call(["tmux", "kill-session", "-t", DASHBOARD_SESSION], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log(f"Dashboard listo. Usá: tmux attach -t {DASHBOARD_SESSION}", Colors.OKGREEN)
