import os
import time
import socket
import struct
import subprocess
import multiprocessing # Para detectar los cores
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich import box
from core.config import *

class MCDashboard:
    def __init__(self):
        self.layout = Layout()
        self.stats = {}
        self.players = set()
        self.server_status = "Iniciando"
        self.start_time = time.time()
        self.uptime = "0s"
        self.log_path = os.path.join(os.getcwd(), "server_logs", "latest.log")
        self._last_log_pos = 0
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
            res = subprocess.check_output(["docker", "stats", CONTAINER_NAME, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}"]).decode().strip()
            if res:
                parts = res.split("|")
                self.stats = {
                    "cpu": parts[0],
                    "mem": parts[1],
                    "mem_perc": float(parts[2].replace("%", "")),
                    "net": parts[3],
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
            res = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd", java_pid, "GC.heap_info"], stderr=subprocess.STDOUT).decode()
            for line in res.split("\n"):
                if "total" in line and "used" in line:
                    line = line.replace(",", "")
                    parts = line.split()
                    used_idx, total_idx = parts.index("used") + 1, parts.index("total") + 1
                    used = float(parts[used_idx].replace("K", "").replace("M", ""))
                    if "K" in parts[used_idx]: used /= 1024
                    return {"used": used, "total": RAM_GB * 1024}
        except: return None

    def rcon_command(self, cmd):
        try:
            auth_packet = struct.pack("<iii", 10 + len("senior_architect"), 0, 3) + b"senior_architect" + b"\x00\x00"
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", 25575))
            s.send(auth_packet)
            res = s.recv(1024)
            cmd_packet = struct.pack("<iii", 10 + len(cmd), 0, 2) + cmd.encode() + b"\x00\x00"
            s.send(cmd_packet)
            res = s.recv(4096)
            s.close()
            output = res[12:-2].decode(errors="ignore")
            return output
        except: return None

    def query_server(self):
        self.update_players_from_log()
        if self.rcon_command("help"): self.server_status = "Online"
        else: self.server_status = "Iniciando/Logs-Only"

    def make_layout(self):
        self.layout.split(Layout(name="header", size=3), Layout(name="main", ratio=1), Layout(name="footer", size=3))
        self.layout["main"].split_row(Layout(name="stats", ratio=1), Layout(name="players", ratio=1))

    def generate_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1); grid.add_column(justify="right", ratio=1)
        status_color = "green" if self.server_status == "Online" else "yellow"
        grid.add_row(Text.from_markup(f"[bold]Minecraft Fabric Manager[/] | Versión: [cyan]{MINECRAFT_VERSION}[/]"),
                     Text.from_markup(f"Estado: [bold {status_color}]{self.server_status}[/] | Uptime: [white]{self.uptime}[/]"))
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
        with Live(self.layout, refresh_per_second=1/interval if interval > 0 else 1, screen=True):
            while True:
                self.get_docker_stats(); self.query_server()
                elapsed = int(time.time() - self.start_time)
                self.uptime = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m {elapsed % 60}s"
                self.layout["header"].update(self.generate_header())
                self.layout["stats"].update(self.generate_stats())
                self.layout["players"].update(self.generate_players())
                self.layout["footer"].update(Panel(Text(" [Q] Salir | [R] Restart Server (próximamente) ", justify="center"), style="white on grey23"))
                time.sleep(interval)
