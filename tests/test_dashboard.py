import pytest
from core.dashboard import MCDashboard
import socket
import subprocess

def test_full_metrics_parsing(mocker):
    # Mockear stats de Docker y JVM
    mock_docker = b"5.5%|1.2GiB / 4GiB|30.0%|10MB / 20MB|100MB / 200MB"
    mock_pids = b"1234 knot\n"
    mock_heap = b"GC.heap_info: total 4194304K, used 1048576K" 
    mock_hist = b"  1:          1000        24000  net.minecraft.class_2818\n"
    
    # Mockear llamadas a subprocess con un side_effect dinámico
    def check_output_side_effect(cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "docker stats" in cmd_str:
            return mock_docker
        if "jcmd" in cmd_str:
            if "GC.heap_info" in cmd_str:
                return mock_heap
            if "GC.class_histogram" in cmd_str:
                return mock_hist
            return mock_pids # Default for getting PID
        return b""

    mocker.patch("subprocess.check_output", side_effect=check_output_side_effect)
    
    # Mockear RCON
    def mock_rcon_side_effect(cmd):
        if cmd == "help": return "help output"
        if "entity @e" in cmd: return "Test passed, count: 42"
        if "spark tps" in cmd: return "TPS from last 5s, 10s, 1m, 5m, 15m: 20.0, 20.0, 19.5, 19.8, 19.9\nMSPT from last 5s, 10s, 1m, 5m, 15m: 12.5, 13.0, 14.2, 14.5, 14.8"
        return "Unknown command"

    mocker.patch.object(MCDashboard, "rcon_command", side_effect=mock_rcon_side_effect)
    mocker.patch.object(MCDashboard, "_is_container_running", return_value=True)
    mocker.patch.object(MCDashboard, "_refresh_container_limits")
    mocker.patch("core.dashboard.check_playit_status", return_value=(True, "Connected"))
    mocker.patch("core.dashboard.check_ngrok_status", return_value=(True, "Connected"))
    mocker.patch("time.time", return_value=2000.0)

    # Mockear Thread para que ejecute síncronamente en el test
    def mock_thread_start(self):
        self._target(*self._args, **self._kwargs)
    mocker.patch("threading.Thread.start", side_effect=mock_thread_start, autospec=True)

    dashboard = MCDashboard()
    
    # Simular 15 ciclos para que se dispare la actualización de chunks
    for _ in range(15):
        dashboard.get_docker_stats()
        dashboard.query_server()

    # Verificaciones
    assert dashboard.stats['disk'] == "100MB / 200MB"
    assert dashboard.entities == 42
    assert dashboard.tps == "19.5"
    assert dashboard.mspt == "14.2"
    assert dashboard.chunks == 1000

def test_rcon_timeout_handling(mocker):
    dashboard = MCDashboard()
    
    # Mockear el container como corriendo
    mocker.patch.object(dashboard, "_is_container_running", return_value=True)
    mocker.patch.object(dashboard, "_refresh_container_limits")
    mocker.patch("core.dashboard.check_playit_status", return_value=(True, "Connected"))
    mocker.patch("core.dashboard.check_ngrok_status", return_value=(True, "Connected"))
    
    # Mockear RCON para que falle (timeout)
    mocker.patch.object(dashboard, "rcon_command", return_value=None)
    
    # Mockear stats básicas
    dashboard.stats = {"cpu": "10%"}
    
    dashboard.query_server()
    
    assert dashboard.server_status == "Iniciando..."
    assert dashboard.tps == "N/A"
    assert dashboard.entities == 0

def test_jvm_heap_parsing_units(mocker):
    dashboard = MCDashboard()
    dashboard.jvm_max_ram = 4
    dashboard._java_pid = "1234"
    
    # Test con G (Gigabytes)
    mock_heap_g = b"GC.heap_info: total 4194304K, used 1G"
    mocker.patch("subprocess.check_output", return_value=mock_heap_g)
    stats = dashboard.get_jvm_stats()
    assert stats["used"] == 1024.0 # 1G = 1024MiB
    
    # Test con M (Megabytes)
    mock_heap_m = b"GC.heap_info: total 4194304K, used 512M"
    mocker.patch("subprocess.check_output", return_value=mock_heap_m)
    stats = dashboard.get_jvm_stats()
    assert stats["used"] == 512.0
    
    # Test con K (Kilobytes)
    mock_heap_k = b"GC.heap_info: total 4194304K, used 102400K"
    mocker.patch("subprocess.check_output", return_value=mock_heap_k)
    stats = dashboard.get_jvm_stats()
    assert stats["used"] == 100.0 # 102400 / 1024 = 100
