import os
import subprocess
import time
from core.config import *

def ensure_server_config():
    config_path = HOST_CONFIG_DIR / "server.properties"
    if not config_path.exists(): return
    with open(config_path, "r") as f: lines = f.readlines()
    updates = {
        "enable-rcon": "true", "rcon.password": "senior_architect", "rcon.port": "25575",
        "enable-query": "true", "query.port": "25565", "broadcast-rcon-to-ops": "true"
    }
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
    log("Configuración de RCON/Query verificada.", Colors.OKGREEN)

import zipfile
from datetime import datetime

def create_backup():
    if not HOST_WORLD_DIR.exists():
        log("No hay carpeta 'world' para respaldar.", Colors.WARNING)
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PROJECT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"world_backup_{timestamp}.zip"
    
    log(f"Creando backup en {backup_file}...", Colors.HEADER)
    try:
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(HOST_WORLD_DIR):
                for file in files:
                    file_path = Path(root) / file
                    zipf.write(file_path, file_path.relative_to(PROJECT_DIR))
        log("Backup completado con éxito.", Colors.OKGREEN)
    except Exception as e:
        log(f"Error creando backup: {e}", Colors.FAIL)

def restore_latest_backup():
    backup_dir = PROJECT_DIR / "backups"
    if not backup_dir.exists(): return False
    
    backups = list(backup_dir.glob("world_backup_*.zip"))
    if not backups:
        log("No se encontraron backups para restaurar.", Colors.WARNING)
        return False
    
    latest_backup = max(backups, key=os.path.getctime)
    log(f"Restaurando el backup más reciente: {latest_backup.name}", Colors.HEADER)
    
    try:
        with zipfile.ZipFile(latest_backup, 'r') as zipf:
            zipf.extractall(PROJECT_DIR)
        log("Restauración completada.", Colors.OKGREEN)
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
    mkdir -p /server/mods /server/world /server/logs
RUN printf '#!/usr/bin/env sh\\necho "eula=true" > /server/eula.txt\\nexec java -Xms1G -Xmx{RAM_GB}G -jar fabric-server-launch.jar nogui\\n' > /server/start.sh && chmod +x /server/start.sh
EXPOSE {SERVER_PORT} 25575
CMD ["/server/start.sh"]
"""
    DOCKER_DIR.mkdir(exist_ok=True)
    (DOCKER_DIR / "Dockerfile").write_text(dockerfile_content)
    log("Construyendo imagen... (esto puede tardar)", Colors.WARNING)
    subprocess.check_call(["docker", "build", "-t", IMAGE_NAME, str(DOCKER_DIR)])
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

def launch_container():
    log("--- 3. LANZANDO CONTENEDOR ---", Colors.HEADER)
    subprocess.call(["docker", "stop", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.call(["docker", "rm", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cmd = [
        "docker", "run", "-d", "--name", CONTAINER_NAME,
        "-p", f"{SERVER_PORT}:{SERVER_PORT}", "-p", "25575:25575",
        "--restart", "unless-stopped", "--memory", "8g",
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
