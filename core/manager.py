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

def setup_directories():
    log("--- 1. PREPARANDO ENTORNO ---", Colors.HEADER)
    for d in [DOCKER_DIR, HOST_MODS_DIR, HOST_WORLD_DIR, HOST_LOGS_DIR, HOST_CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
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
RUN cat > /server/start.sh <<'EOF'
#!/usr/bin/env sh
java -Xms1G -Xmx{RAM_GB}G -jar fabric-server-launch.jar nogui
EOF
RUN chmod +x /server/start.sh
EXPOSE {SERVER_PORT} 25575
CMD ["/server/start.sh"]
"""
    DOCKER_DIR.mkdir(exist_ok=True)
    (DOCKER_DIR / "Dockerfile").write_text(dockerfile_content)
    log("Construyendo imagen... (esto puede tardar)", Colors.WARNING)
    subprocess.check_call(["docker", "build", "-t", IMAGE_NAME, str(DOCKER_DIR)])
    log("Imagen construida con éxito.", Colors.OKGREEN)

def get_playit_command(mode):
    if mode == "skip": return None
    if mode == "reset":
        if os.path.exists(PLAYIT_LOG): os.remove(PLAYIT_LOG)
        return f"playit --secret-path {PLAYIT_LOG} setup"
    if mode == "new": return f"playit --secret-path {PLAYIT_LOG}"
    return f"playit --secret-path {PLAYIT_LOG}"

def launch_container():
    log("--- 3. LANZANDO CONTENEDOR ---", Colors.HEADER)
    subprocess.call(["docker", "stop", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.call(["docker", "rm", CONTAINER_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cmd = [
        "docker", "run", "-d", "--name", CONTAINER_NAME,
        "-p", f"{SERVER_PORT}:{SERVER_PORT}", "-p", "25575:25575",
        "--restart", "unless-stopped", "--memory", "8g",
        "--mount", f"type=bind,source={HOST_MODS_DIR},target=/server/mods",
        "--mount", f"type=bind,source={HOST_WORLD_DIR},target=/server/world",
        "--mount", f"type=bind,source={HOST_LOGS_DIR},target=/server/logs",
        "--mount", f"type=bind,source={HOST_CONFIG_DIR},target=/server/server.properties,src=server.properties",
        IMAGE_NAME
    ]
    # Pequeño fix para el mount de server.properties individual
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
