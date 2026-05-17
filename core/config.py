import os
from pathlib import Path

# --- CONFIGURACIÓN SENIOR ---
MINECRAFT_VERSION = "1.21.10"
SERVER_PORT = 25565
RAM_GB = 6
CONTAINER_RAM_GB = 8
CPU_LIMIT = 8.0
IMAGE_NAME = f"minecraft-fabric-{MINECRAFT_VERSION}".replace(".", "-").lower()
CONTAINER_NAME = "minecraft-fabric-server"
DASHBOARD_SESSION = "mc-dashboard"
PLAYIT_SESSION = "playit-mc"
NGROK_SESSION = "ngrok-mc"
RCON_PASSWORD = "senior_architect"
RCON_PORT = 25575

# --- RUTAS ---
PROJECT_DIR = Path(os.getcwd())
DOCKER_DIR = PROJECT_DIR / "docker"
HOST_MODS_DIR = PROJECT_DIR / "mods"
HOST_WORLD_DIR = PROJECT_DIR / "world"
HOST_LOGS_DIR = PROJECT_DIR / "server_logs"
HOST_CONFIG_DIR = PROJECT_DIR / "server_config"
PLAYIT_SECRET = PROJECT_DIR / "playit.toml"
PLAYIT_LOG_FILE = PROJECT_DIR / "playit.log"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def log(msg, color=Colors.OKBLUE):
    print(f"{color}{msg}{Colors.ENDC}")
