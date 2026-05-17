import pytest
from core.dashboard import MCDashboard
import socket
import subprocess

def test_full_metrics_parsing(mocker):
    # Mockear stats de Docker y JVM
    mock_docker = b"5.5%|1.2GiB / 4GiB|30.0%|10MB / 20MB|100MB / 200MB"
    mock_pids = b"1234 knot\n"
    mock_heap = b"GC.heap_info: total 4194304K, used 1048576K" # Ajustado para jcmd output
    mock_hist = b"  1:          1000        24000  net.minecraft.class_2818\n"
    mock_flags = b"MaxHeapSize=4294967296"
    
    # Mockear llamadas a subprocess
    mocker.patch("subprocess.check_output", side_effect=[
        mock_docker, # get_docker_stats
        mock_pids,   # get_jvm_stats -> pids
        mock_flags,  # get_jvm_stats -> flags
        mock_heap,   # get_jvm_stats -> heap
        mock_hist    # get_jvm_stats -> chunks
    ])
    
    # Mockear RCON
    def mock_rcon_side_effect(cmd):
        if cmd == "help": return "help output"
        if "entity @e" in cmd: return "Test passed, count: 42"
        if "spark tps" in cmd: return "TPS from last 5s, 10s, 1m, 5m, 15m: 20.0, 20.0, 19.5, 19.8, 19.9\nMSPT from last 5s, 10s, 1m, 5m, 15m: 12.5, 13.0, 14.2, 14.5, 14.8"
        return "Unknown command"

    mocker.patch.object(MCDashboard, "rcon_command", side_effect=mock_rcon_side_effect)
    mocker.patch.object(MCDashboard, "_is_container_running", return_value=True)
    mocker.patch.object(MCDashboard, "_refresh_container_limits") # Evitar llamadas a docker inspect real
    mocker.patch("core.dashboard.check_playit_status", return_value=(True, "Connected"))
    mocker.patch("core.dashboard.check_ngrok_status", return_value=(True, "Connected"))
    mocker.patch("time.time", return_value=2000.0)

    dashboard = MCDashboard()
    dashboard.get_docker_stats() # Esto dispara get_jvm_stats
    dashboard.query_server()

    # Verificaciones
    assert dashboard.stats['disk'] == "100MB / 200MB"
    assert dashboard.entities == 42
    assert dashboard.tps == "19.5"
    assert dashboard.mspt == "14.2"
    assert dashboard.chunks == 1000
