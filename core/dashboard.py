import os
import time
import socket
import struct
import subprocess
import multiprocessing # Para detectar los cores
import sys
import select
import termios
import tty
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich import box
from core.config import *
from core.manager import check_playit_status, check_ngrok_status

class MCDashboard:
    def __init__(self):
        self.layout = Layout()
        self.stats = {}
        self.players = set()
        self.server_status = "Iniciando"
        self.playit_status = "Buscando..."
        self.ngrok_status = "Buscando..."
        self.playit_connected = False
        self.ngrok_connected = False
        self.entities = 0
        self.tps = "N/A"
        self.mspt = "N/A"
        self.chunks = 0
        self.start_time = time.time()
        self.uptime = "0s"
        self.log_path = os.path.join(os.getcwd(), "server_logs", "latest.log")
        self._last_log_pos = 0
        self._last_rcon_check = 0
        self._rcon_check_interval = 30.0  # Chequeamos cada 30 segundos para evitar ruido
        self.update_players_from_log()

    def update_players_from_log(self):
        if not os.path.exists(self.log_path): return
        try:
            with open(self.log_path, "r") as f:
                f.seek(self._last_log_pos)
                lines = f.readlines()
                self._last_log_pos = f.tell()
                for line in lines:
                    if "joined the game" in line:
                        parts = line.split("]: ")
                        if len(parts) > 1:
                            name = parts[1].split(" joined")[0].strip()
                            self.players.add(name)
                    elif "left the game" in line:
                        parts = line.split("]: ")
                        if len(parts) > 1:
                            name = parts[1].split(" left")[0].strip()
                            if name in self.players: self.players.remove(name)
        except: pass

    def get_docker_stats(self):
        try:
            res = subprocess.check_output(["docker", "stats", CONTAINER_NAME, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}"]).decode().strip()
            if res:
                parts = res.split("|")
                self.stats = {
                    "cpu": parts[0],
                    "mem": parts[1],
                    "mem_perc": float(parts[2].replace("%", "")),
                    "net": parts[3],
                    "disk": parts[4],
                    "mem_raw": parts[1]
                }
            self.stats['jvm'] = self.get_jvm_stats()
        except: pass

    def get_jvm_stats(self):
        try:
            pids = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd"], stderr=subprocess.STDOUT).decode().split("\n")
            java_pid = "1"
            for line in pids:
                if any(x in line for x in ["net.fabricmc.loader", "minecraft", "knot"]):
                    java_pid = line.split(" ")[0]
                    break
            
            # 1. Memoria Heap
            res = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd", java_pid, "GC.heap_info"], stderr=subprocess.STDOUT).decode()
            stats = {"used": 0, "total": RAM_GB * 1024}
            for line in res.split("\n"):
                if "total" in line and "used" in line:
                    line = line.replace(",", "")
                    parts = line.split()
                    used_idx = parts.index("used") + 1
                    used = float(parts[used_idx].replace("K", "").replace("M", ""))
                    if "K" in parts[used_idx]: used /= 1024
                    stats["used"] = used
            
            # 2. Chunks (net.minecraft.class_2818 en Fabric 1.21.1)
            hist = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd", java_pid, "GC.class_histogram"], stderr=subprocess.STDOUT).decode()
            for line in hist.split("\n"):
                if "net.minecraft.class_2818" in line:
                    self.chunks = int(line.split(":")[1].split()[0])
                    break
            
            return stats
        except: return None

    def is_rcon_alive(self) -> bool:
        """Passive TCP probe: connect only, no auth handshake.
        Note: Modern Minecraft/Fabric servers log this connection, so
        we throttle calls to this method to reduce log noise."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", 25575))
            s.close()
            return True
        except OSError:
            return False

    def rcon_command(self, cmd: str) -> str | None:
        """Full RCON session for actual commands (/stop, /backup, etc.).
        Do NOT call this on every dashboard tick."""
        try:
            auth_packet = struct.pack("<iii", 10 + len(RCON_PASSWORD), 0, 3) + RCON_PASSWORD.encode() + b"\x00\x00"
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect(("127.0.0.1", 25575))
            s.send(auth_packet)
            s.recv(1024)  # auth response
            cmd_packet = struct.pack("<iii", 10 + len(cmd), 1, 2) + cmd.encode() + b"\x00\x00"
            s.send(cmd_packet)
            res = s.recv(4096)
            s.close()
            return res[12:-2].decode(errors="ignore")
        except OSError:
            return None

    def query_server(self):
        self.update_players_from_log()
        self.playit_connected, self.playit_status = check_playit_status()
        self.ngrok_connected, self.ngrok_status = check_ngrok_status()
        now = time.time()
        if now - self._last_rcon_check >= self._rcon_check_interval:
            self._last_rcon_check = now
            if self.is_rcon_alive():
                self.server_status = "Online"
                # 1. Entidades
                res_e = self.rcon_command("execute if entity @e")
                if res_e and "count: " in res_e:
                    try: self.entities = int(res_e.split("count: ")[1])
                    except: pass
                
                # 2. Spark TPS/MSPT (Opcional)
                res_s = self.rcon_command("spark tps")
                if res_s and "TPS from last" in res_s:
                    try:
                        # Extraer 1m TPS
                        tps_line = [l for l in res_s.split("\n") if "TPS from last" in l][0]
                        self.tps = tps_line.split(": ")[1].split(", ")[2] # El 3ero es 1m
                        # Extraer 1m MSPT
                        mspt_line = [l for l in res_s.split("\n") if "MSPT from last" in l][0]
                        self.mspt = mspt_line.split(": ")[1].split(", ")[2]
                    except:
                        self.tps = self.mspt = "Error"
                else:
                    self.tps = self.mspt = "N/A"
            else:
                self.server_status = "Iniciando/Logs-Only"
                self.tps = self.mspt = "N/A"
                self.entities = 0
                self.chunks = 0

    def make_layout(self):
        self.layout.split(Layout(name="header", size=4), Layout(name="main", ratio=1), Layout(name="footer", size=3))
        self.layout["main"].split_row(Layout(name="stats", ratio=1), Layout(name="players", ratio=1))

    def generate_header(self) -> Panel:
        from core.manager import get_playit_address, get_ngrok_address
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1); grid.add_column(justify="right", ratio=1)
        status_color = "green" if self.server_status == "Online" else "yellow"
        playit_color = "green" if self.playit_connected else "yellow"
        ngrok_color = "green" if self.ngrok_connected else "yellow"
        
        # Recopilar todas las IPs activas
        ips = []
        p_addr = get_playit_address()
        if p_addr: ips.append(f"[cyan]Playit:[/] [bold]{p_addr}[/]")
        n_addr = get_ngrok_address()
        if n_addr: ips.append(f"[blue]Ngrok:[/] [bold]{n_addr}[/]")
        
        addr_text = " | ".join(ips) if ips else "Buscando IP..."
        tunnels_text = f"Playit: [bold {playit_color}]{self.playit_status}[/] | Ngrok: [bold {ngrok_color}]{self.ngrok_status}[/]"
        
        grid.add_row(Text.from_markup(f"[bold]MC Manager[/] | {tunnels_text}"),
                     Text.from_markup(f"Server: [bold {status_color}]{self.server_status}[/] | Uptime: [white]{self.uptime}[/]"))
        grid.add_row(Text.from_markup(f"Direcciones: {addr_text}"), "")
        return Panel(grid, style="white on blue")

    def generate_stats(self) -> Panel:
        table = Table(show_header=False, box=box.SIMPLE, expand=True)
        cpu_str = self.stats.get('cpu', '0%')
        cpu_count = multiprocessing.cpu_count() # Detectamos cores totales
        try: cpu_val = float(cpu_str.replace('%', ''))
        except: cpu_val = 0.0
        table.add_row("CPU Usage", f"[bold cyan]{cpu_str}[/] [grey50]({cpu_count} Threads)[/]")
        table.add_row("", self.generate_progress_bar(cpu_val, "cyan"))
        mem_raw = self.stats.get('mem_raw', "0 / 0")
        table.add_row("RAM Contenedor", f"[bold]{mem_raw}[/]")
        table.add_row("", self.generate_progress_bar(self.stats.get('mem_perc', 0), "cyan"))
        jvm = self.stats.get('jvm')
        if jvm:
            jvm_perc = (jvm['used'] / jvm['total']) * 100
            table.add_row("RAM Minecraft (Heap)", f"[bold]{jvm['used']:.1f}MiB / {jvm['total']:.1f}MiB[/]")
            table.add_row("", self.generate_progress_bar(jvm_perc, "green"))
        else: table.add_row("RAM Minecraft", "[yellow]Cargando JVM stats...[/]")
        table.add_row("Net I/O", f"[bold]{self.stats.get('net', '0 / 0')}[/]")
        table.add_row("Disk I/O", f"[bold]{self.stats.get('disk', '0 / 0')}[/]")
        
        # Colores para TPS
        try:
            tps_val = float(self.tps.split()[0])
            tps_color = "green" if tps_val > 18 else "yellow" if tps_val > 15 else "red"
        except: tps_color = "white"
        
        table.add_row("TPS (1m)", f"[bold {tps_color}]{self.tps}[/]")
        table.add_row("MSPT (1m)", f"[bold]{self.mspt}[/]")
        table.add_row("Entidades", f"[bold]{self.entities}[/]")
        table.add_row("Chunks Cargados", f"[bold]{self.chunks}[/]")
        return Panel(table, title="[bold]Performance[/]", border_style="cyan")

    def generate_progress_bar(self, percentage, color):
        p = Progress(BarColumn(bar_width=None, style="grey35", complete_style=color, finished_style=color),
                     TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
        p.add_task("task", total=100, completed=percentage)
        return p

    def generate_players(self) -> Panel:
        table = Table(show_header=True, box=box.SIMPLE, expand=True)
        table.add_column("Jugador", style="green")
        if not self.players: table.add_row("[italic white]Nadie conectado...[/]")
        else:
            for p in sorted(list(self.players)): table.add_row(p)
        return Panel(table, title=f"[bold]Jugadores ({len(self.players)})[/]", border_style="green")

    def run(self, interval=2.0):
        self.make_layout()
        
        # Intentar guardar configuración original de la terminal
        old_settings = None
        try:
            if sys.stdin.isatty():
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
        except: pass
        
        try:
            with Live(self.layout, refresh_per_second=1/interval if interval > 0 else 1, screen=True):
                while True:
                    self.get_docker_stats(); self.query_server()
                    elapsed = int(time.time() - self.start_time)
                    self.uptime = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m {elapsed % 60}s"
                    self.layout["header"].update(self.generate_header())
                    self.layout["stats"].update(self.generate_stats())
                    self.layout["players"].update(self.generate_players())
                    self.layout["footer"].update(Panel(Text(" [Q] Salir | [R] Restart Server (próximamente) ", justify="center"), style="white on grey23"))
                    
                    # Espera no bloqueante para entrada de teclado
                    start_wait = time.time()
                    while time.time() - start_wait < interval:
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            ch = sys.stdin.read(1).lower()
                            if ch == 'q':
                                return # Salida limpia
                        time.sleep(0.05)
        finally:
            # Restaurar terminal pase lo que pase
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
