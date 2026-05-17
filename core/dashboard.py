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
import threading
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich import box
from core.config import *
from core.manager import check_playit_status, check_ngrok_status

# Modos del Dashboard
MAIN_DASHBOARD = "main_dashboard"
PLAYER_SELECTION = "player_selection"
PLAYER_ACTION_MENU = "player_action_menu"
CONFIRMATION = "confirmation"

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
        self.playit_addr = "Buscando..."
        self.ngrok_addr = "Buscando..."
        
        # Resource Limits (Real-time from Docker)
        self.cpu_limit = CPU_LIMIT
        self.mem_limit_gb = CONTAINER_RAM_GB
        self.jvm_max_ram = RAM_GB
        
        # Persistent RCON State
        self._rcon_sock = None
        self._rcon_authenticated = False
        
        self.update_players_from_log()
        
        # State management for interactive features
        self._mode = MAIN_DASHBOARD
        self._selected_player_index = -1
        self._current_message = None
        self._message_timer = None
        
        # Background data fetching
        self._stop_event = threading.Event()
        self._data_thread = None
        self._java_pid = None
        self._chunks_cycle = 0

    def _refresh_container_limits(self):
        """Obtiene los límites reales del contenedor desde Docker inspect"""
        try:
            # Primero CPU y Memoria (son fijos)
            out = subprocess.check_output(
                ["docker", "inspect", CONTAINER_NAME, "--format", "{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            
            if out:
                parts = out.split()
                if parts[0] != "0":
                    self.cpu_limit = float(parts[0]) / 1e9
                if parts[1] != "0":
                    self.mem_limit_gb = float(parts[1]) / (1024**3)
            
            # Luego buscamos la variable MAX_RAM sin que rompa el template
            env_out = subprocess.check_output(
                ["docker", "inspect", CONTAINER_NAME, "--format", "{{range .Config.Env}}{{.}} {{end}}"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            
            for env_var in env_out.split():
                if env_var.startswith("MAX_RAM="):
                    try: self.jvm_max_ram = float(env_var.split("=")[1])
                    except: pass
        except:
            pass

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
            res = subprocess.check_output(
                ["docker", "stats", CONTAINER_NAME, "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}|{{.NetIO}}|{{.BlockIO}}"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
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
        except:
            self.stats = {
                "cpu": "OFFLINE",
                "mem": "0 / 0",
                "mem_perc": 0,
                "net": "0 / 0",
                "disk": "0 / 0",
                "mem_raw": "0 / 0",
                "jvm": None
            }

    def get_jvm_stats(self):
        try:
            # Obtener PID si no lo tenemos o si cambió
            if not self._java_pid:
                pids_out = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd"], stderr=subprocess.DEVNULL).decode().split("\n")
                for line in pids_out:
                    if any(x in line for x in ["net.fabricmc.loader", "minecraft", "knot"]):
                        self._java_pid = line.split(" ")[0].strip()
                        break
            
            if not self._java_pid: return None
            
            # 1. Obtener Uso Actual de GC.heap_info (Relativamente rápido)
            res = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd", self._java_pid, "GC.heap_info"], stderr=subprocess.DEVNULL).decode()
            stats = {"used": 0, "total": self.jvm_max_ram * 1024.0}
            for line in res.split("\n"):
                if "total" in line and "used" in line:
                    line = line.replace(",", "")
                    parts = line.split()
                    try:
                        used_idx = parts.index("used") + 1
                        used_str = parts[used_idx]
                        used = float(used_str.replace("K", "").replace("M", "").replace("G", ""))
                        if "K" in used_str: used /= 1024
                        elif "G" in used_str: used *= 1024
                        stats["used"] = used
                    except: pass
            
            # 2. Chunks (MUY lento, solo cada 15 ciclos)
            self._chunks_cycle += 1
            if self._chunks_cycle >= 15:
                self._chunks_cycle = 0
                try:
                    hist = subprocess.check_output(["docker", "exec", CONTAINER_NAME, "jcmd", self._java_pid, "GC.class_histogram"], stderr=subprocess.DEVNULL).decode()
                    for line in hist.split("\n"):
                        if "net.minecraft.class_2818" in line:
                            self.chunks = int(line.split(":")[1].split()[0])
                            break
                except: pass
            
            return stats
        except: 
            self._java_pid = None # Reset PID on error
            return None

    def _is_container_running(self):
        """Verifica si el contenedor está corriendo sin spamear logs"""
        try:
            out = subprocess.check_output(
                ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return out == "true"
        except:
            return False

    def _rcon_connect(self):
        """Establece conexión RCON persistente (Senior & Clean)"""
        if self._rcon_sock and self._rcon_authenticated:
            return True
            
        try:
            if self._rcon_sock:
                try: self._rcon_sock.close()
                except: pass
            
            self._rcon_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._rcon_sock.settimeout(0.5) # Timeouts cortos para el UI
            self._rcon_sock.connect(("127.0.0.1", 25575))
            
            # Auth (Request Type 3)
            auth_packet = struct.pack("<iii", 10 + len(RCON_PASSWORD), 0, 3) + RCON_PASSWORD.encode() + b"\x00\x00"
            self._rcon_sock.send(auth_packet)
            res = self._rcon_sock.recv(1024)
            
            # Verificar ID de respuesta (Type 2 si OK, msg_id match)
            if len(res) < 12: raise Exception("Response too short")
            _, msg_id, _ = struct.unpack("<iii", res[:12])
            if msg_id == -1:
                self._rcon_authenticated = False
                return False
                
            self._rcon_authenticated = True
            return True
        except:
            self._rcon_sock = None
            self._rcon_authenticated = False
            return False

    def rcon_command(self, cmd: str) -> str | None:
        """Envía un comando usando la conexión persistente"""
        if not self._rcon_connect():
            return None
            
        try:
            # Request (Type 2: Command)
            cmd_packet = struct.pack("<iii", 10 + len(cmd), 1, 2) + cmd.encode() + b"\x00\x00"
            self._rcon_sock.send(cmd_packet)
            
            # Response
            res = self._rcon_sock.recv(16384) # Buffer más grande por si hay mucha data
            if not res:
                raise ConnectionResetError()
                
            return res[12:-2].decode(errors="ignore")
        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            self._rcon_authenticated = False
            if self._rcon_sock:
                try: self._rcon_sock.close()
                except: pass
                self._rcon_sock = None
            return None
        except:
            return None

    def set_message(self, message: str, style: str = "white"):
        self._current_message = Text(message, style=style)
        self._message_timer = time.time() + 5 # Message lasts for 5 seconds

    def _handle_input(self, char: str):
        # Existing global commands
        if char == 'q':
            return True # Signal to quit
        elif char == 'r':
            self._rcon_authenticated = False
            if self._rcon_sock:
                try: self._rcon_sock.close()
                except: pass
                self._rcon_sock = None
            self.get_docker_stats()
            self.query_server()
            self.set_message("Refrescando datos...", "blue")
            return False # Not a quit signal

        # Player interaction mode activation
        if char == 'p' and self._mode == MAIN_DASHBOARD and len(self.players) > 0:
            self._mode = PLAYER_SELECTION
            self._selected_player_index = 0 # Select the first player
            self.set_message("Modo selección de jugador. Usa ↑↓ para navegar, Enter para seleccionar, Esc para salir.", "yellow")
            return False

        # Mode-specific input handling
        if self._mode == PLAYER_SELECTION:
            sorted_players = sorted(list(self.players))
            if char == '\x1b[A': # Up arrow
                self._selected_player_index = max(0, self._selected_player_index - 1)
            elif char == '\x1b[B': # Down arrow
                self._selected_player_index = min(len(sorted_players) - 1, self._selected_player_index + 1)
            elif char == '\n': # Enter key
                if self._selected_player_index != -1 and sorted_players:
                    self._mode = PLAYER_ACTION_MENU
                    self.set_message(f"Jugador seleccionado: {sorted_players[self._selected_player_index]}. Elige una acción.", "green")
            elif char == '\x1b': # Escape key
                self._mode = MAIN_DASHBOARD
                self._selected_player_index = -1
                self.set_message("Volviendo al dashboard principal.", "blue")
            return False

        if self._mode == PLAYER_ACTION_MENU:
            sorted_players = sorted(list(self.players))
            selected_player = sorted_players[self._selected_player_index] if self._selected_player_index != -1 else None
            if selected_player:
                if char == 'k': # Kick
                    self._execute_player_action(selected_player, "kick")
                    self._mode = MAIN_DASHBOARD
                elif char == 'b': # Ban
                    self._execute_player_action(selected_player, "ban")
                    self._mode = MAIN_DASHBOARD
                elif char == 'o': # Op
                    self._execute_player_action(selected_player, "op")
                    self._mode = MAIN_DASHBOARD
                elif char == 'd': # Deop
                    self._execute_player_action(selected_player, "deop")
                    self._mode = MAIN_DASHBOARD
                elif char == '\x1b': # Escape
                    self._mode = PLAYER_SELECTION
                    self.set_message(f"Volviendo a selección de jugador.", "blue")
            else: # Fallback if no player is selected (shouldn't happen)
                self._mode = MAIN_DASHBOARD
            return False

        if char == '\x1b': # Global Escape to main dashboard if not handled by other modes
            if self._mode != MAIN_DASHBOARD:
                self._mode = MAIN_DASHBOARD
                self._selected_player_index = -1
                self.set_message("Volviendo al dashboard principal.", "blue")
            return False

        return False # No quit signal, and input not handled by any specific mode

    def _execute_player_action(self, player_name: str, action_type: str):
        command = ""
        success_message = ""
        error_message = ""

        if action_type == "kick":
            command = f"kick {player_name}"
            success_message = f"Jugador {player_name} expulsado."
            error_message = f"Error al expulsar a {player_name}."
        elif action_type == "ban":
            command = f"ban {player_name}"
            success_message = f"Jugador {player_name} baneado."
            error_message = f"Error al banear a {player_name}."
        elif action_type == "op":
            command = f"op {player_name}"
            success_message = f"Jugador {player_name} ahora es operador."
            error_message = f"Error al dar OP a {player_name}."
        elif action_type == "deop":
            command = f"deop {player_name}"
            success_message = f"Jugador {player_name} ya no es operador."
            error_message = f"Error al quitar OP a {player_name}."
        else:
            self.set_message(f"Acción '{action_type}' no reconocida.", "red")
            return

        response = self.rcon_command(command)
        if response is not None:
            self.set_message(success_message + f" Respuesta: {response[:50]}...", "green")
        else:
            self.set_message(error_message + " No se recibió respuesta o RCON falló.", "red")

    def query_server(self):
        from core.manager import get_playit_address, get_ngrok_address
        self.update_players_from_log()
        self._refresh_container_limits()
        
        # Detectar túnel activo
        tunnel_file = HOST_CONFIG_DIR / "active_tunnel.txt"
        active_tunnel = None
        if tunnel_file.exists():
            active_tunnel = tunnel_file.read_text().strip()
        else:
            # Fallback: Detectar por sesiones de tmux activas
            res_playit = subprocess.call(["tmux", "has-session", "-t", PLAYIT_SESSION], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            res_ngrok = subprocess.call(["tmux", "has-session", "-t", NGROK_SESSION], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            if res_ngrok == 0: active_tunnel = "ngrok"
            elif res_playit == 0: active_tunnel = "playit"

        # Actualizar estados y direcciones según el túnel activo
        self.playit_connected, self.playit_status = check_playit_status()
        self.ngrok_connected, self.ngrok_status = check_ngrok_status()
        
        if active_tunnel == "ngrok":
            self.ngrok_addr = get_ngrok_address() or "N/A"
            self.playit_addr = "N/A"
        elif active_tunnel == "playit":
            self.playit_addr = get_playit_address() or "N/A"
            self.ngrok_addr = "N/A"
        else:
            self.playit_addr = "N/A"
            self.ngrok_addr = "N/A"
        
        if not self._is_container_running():
            self.server_status = "Offline"
            self.tps = self.mspt = "N/A"
            self.entities = 0
            self.chunks = 0
            # Si el container está abajo, cerramos RCON por las dudas
            if self._rcon_sock:
                try: self._rcon_sock.close()
                except: pass
                self._rcon_sock = None
                self._rcon_authenticated = False
            return

        # Si el container corre, probamos RCON
        res_help = self.rcon_command("help")
        if res_help is not None:
            self.server_status = "Online"
            
            # 1. Entidades
            res_e = self.rcon_command("execute if entity @e")
            if res_e and "ount: " in res_e.lower():
                try: self.entities = int(res_e.lower().split("ount: ")[1])
                except: pass
            
            # 2. TPS/MSPT
            res_s = self.rcon_command("spark tps")
            if res_s and "TPS from last" in res_s:
                try:
                    lines = res_s.split("\n")
                    tps_line = [l for l in lines if "TPS from last" in l][0]
                    self.tps = tps_line.split(": ")[1].split(", ")[2].replace("*", "")
                    mspt_line = [l for l in lines if "MSPT from last" in l][0]
                    self.mspt = mspt_line.split(": ")[1].split(", ")[2]
                except: self.tps = self.mspt = "Error"
            else:
                res_t = self.rcon_command("tick query")
                if res_t and "Average time per tick" in res_t:
                    try:
                        if "Target tick rate" in res_t:
                            self.tps = res_t.split("Target tick rate: ")[1].split(" ")[0]
                        self.mspt = res_t.split("Average time per tick: ")[1].split("ms")[0] + "ms"
                    except: self.tps = self.mspt = "N/A"
                else: self.tps = self.mspt = "N/A"
        else:
            self.server_status = "Iniciando..."
            self.tps = self.mspt = "N/A"
            self.entities = 0
            self.chunks = 0
            self.stats['jvm'] = None # Limpiar stats de JVM si no hay RCON

    def make_layout(self):
        self.layout.split(Layout(name="header", size=4), Layout(name="main", ratio=1), Layout(name="footer", size=3))
        self.layout["main"].split_row(Layout(name="stats", ratio=1), Layout(name="players", ratio=1))

    def generate_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1); grid.add_column(justify="right", ratio=1)
        status_color = "green" if self.server_status == "Online" else "yellow"
        playit_color = "green" if self.playit_connected else "yellow"
        ngrok_color = "green" if self.ngrok_connected else "yellow"
        
        # Usar IPs cacheadas del background thread
        ips = []
        if self.playit_addr != "N/A": ips.append(f"[cyan]Playit:[/] [bold]{self.playit_addr}[/]")
        if self.ngrok_addr != "N/A": ips.append(f"[blue]Ngrok:[/] [bold]{self.ngrok_addr}[/]")
        
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
        
        # Mostrar el uso relativo al límite configurado
        table.add_row("CPU Usage", f"[bold cyan]{cpu_str}[/] [grey50](Limit: {self.cpu_limit} Cores / Host: {cpu_count})[/]")
        
        # Barra de progreso basada en el límite
        cpu_perc_of_limit = (cpu_val / self.cpu_limit) if self.cpu_limit > 0 else 0
        table.add_row("", self.generate_progress_bar(cpu_perc_of_limit, "cyan"))
        
        mem_raw = self.stats.get('mem_raw', "0 / 0")
        table.add_row("RAM Contenedor", f"[bold]{mem_raw}[/]")
        table.add_row("", self.generate_progress_bar(self.stats.get('mem_perc', 0), "cyan"))
        jvm = self.stats.get('jvm')
        if jvm and self.server_status == "Online":
            jvm_perc = (jvm['used'] / jvm['total']) * 100
            table.add_row("RAM Minecraft (Heap)", f"[bold]{jvm['used']:.1f}MiB / {jvm['total']:.1f}MiB[/]")
            table.add_row("", self.generate_progress_bar(jvm_perc, "green"))
        else:
            status_msg = "Cargando..." if self.server_status == "Iniciando..." else "N/A (Offline)"
            table.add_row("RAM Minecraft (Heap)", f"[grey50]{status_msg}[/]")
            table.add_row("", self.generate_progress_bar(0, "white"))
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

        sorted_players = sorted(list(self.players))

        if not sorted_players:
            table.add_row("[italic white]Nadie conectado...[/]")
        else:
            for i, p in enumerate(sorted_players):
                if (self._mode == PLAYER_SELECTION or self._mode == PLAYER_ACTION_MENU) and i == self._selected_player_index:
                    table.add_row(f"[bold reverse green]{p}[/]")
                else:
                    table.add_row(p)
        
        title = f"[bold]Jugadores ({len(sorted_players)})[/]"
        if self._mode == PLAYER_SELECTION:
            title += "\n[yellow]↑↓ Navegar | Enter Seleccionar | Esc Salir[/]"
        elif self._mode == PLAYER_ACTION_MENU:
            title += "\n[yellow]K Kick | B Ban | O Op | D Deop | Esc Volver[/]"

        return Panel(table, title=title, border_style="green")

    def _data_worker(self, interval: float):
        """Hilo de fondo para actualizar datos pesados sin bloquear la UI"""
        while not self._stop_event.is_set():
            try:
                self.get_docker_stats()
                self.query_server()
            except: pass
            self._stop_event.wait(interval)

    def run(self, interval=2.0):
        self.make_layout()
        
        # Intentar guardar configuración original de la terminal
        old_settings = None
        try:
            if sys.stdin.isatty():
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
        except: pass
        
        # Iniciar hilo de datos
        self._stop_event.clear()
        self._data_thread = threading.Thread(target=self._data_worker, args=(interval,), daemon=True)
        self._data_thread.start()

        try:
            # Refresh rate de la UI más alto para suavidad (10 fps)
            with Live(self.layout, refresh_per_second=10, screen=True):
                while True:
                    now = time.time()
                    
                    # UI update is now independent of data fetching
                    elapsed = int(now - self.start_time)
                    self.uptime = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m {elapsed % 60}s"
                    self.layout["header"].update(self.generate_header())
                    self.layout["stats"].update(self.generate_stats())
                    self.layout["players"].update(self.generate_players())
                    
                    # Footer con mensaje o comandos
                    if self._current_message and self._message_timer and now > self._message_timer:
                        self._current_message = None
                        self._message_timer = None
                    
                    if self._current_message:
                        footer_text = self._current_message
                    else:
                        footer_text = Text(" [Q] Salir | [P] Jugadores | [R] Refrescar forzado ", justify="center")
                    self.layout["footer"].update(Panel(footer_text, style="white on grey23"))

                    # Manejo de entrada de teclado (Ultra-responsivo)
                    if select.select([sys.stdin], [], [], 0.05)[0]: # Timeout corto para inputs
                        char_buffer = sys.stdin.read(1)
                        if char_buffer == '\x1b': # Posible secuencia de escape
                            # Verificamos si hay más caracteres inmediatamente (sin bloquear)
                            if select.select([sys.stdin], [], [], 0.01)[0]:
                                try:
                                    char_buffer += sys.stdin.read(2)
                                except: pass
                        
                        if self._handle_input(char_buffer.lower()):
                            break # Terminar bucle
                            
                    # Pequeño respiro para el CPU
                    time.sleep(0.01)

        finally:
            # Detener hilo de datos
            self._stop_event.set()
            if self._data_thread:
                self._data_thread.join(timeout=1.0)

            # Restaurar terminal pase lo que pase
            if old_settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            
            # Cerrar RCON limpio
            if self._rcon_sock:
                try: self._rcon_sock.close()
                except: pass
                self._rcon_sock = None
                self._rcon_authenticated = False
