import pytest
from core import manager
from core.dashboard import MCDashboard
from core import config
import subprocess
import os
from pathlib import Path

def test_cpu_limit_persistence(mocker, tmp_path):
    # Setup mock project structure
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    mock_config_file = core_dir / "config.py"
    mock_config_file.write_text("CPU_LIMIT = 2.0\nRAM_GB = 4\nCONTAINER_RAM_GB = 5\n")
    
    mocker.patch("core.manager.PROJECT_DIR", tmp_path)
    # We also need to mock where manager looks for server.properties if it's used
    mocker.patch("core.manager.get_server_properties", return_value={})
    mocker.patch("core.manager.update_server_properties")
    
    # Mock inputs: vd, mp, diff, gm, motd, cpu, ram_j, ram_c
    mocker.patch("builtins.input", side_effect=["", "", "", "", "", "4.5", "", ""])
    
    # Inject current values to be patched by global in interactive_config
    manager.CPU_LIMIT = 2.0
    
    manager.interactive_config()
    
    # Verify global update
    assert manager.CPU_LIMIT == 4.5
    
    # Verify file persistence
    content = mock_config_file.read_text()
    assert "CPU_LIMIT = 4.5" in content

def test_launch_container_cpu_flag(mocker):
    mock_call = mocker.patch("subprocess.check_call")
    mocker.patch("core.manager.fix_permissions")
    mocker.patch("subprocess.call") # for stop/rm
    
    # Mock current config value
    mocker.patch("core.manager.CPU_LIMIT", 3.5)
    
    manager.launch_container()
    
    # The command is a list
    args = mock_call.call_args[0][0]
    assert "--cpus" in args
    # Find the index of --cpus and check the next element
    idx = args.index("--cpus")
    assert args[idx+1] == "3.5"

def test_dashboard_dynamic_cpu_limit(mocker):
    # Mock subprocess.check_output for Docker inspect calls
    # MCDashboard._refresh_container_limits makes two calls now
    mocker.patch("subprocess.check_output", side_effect=[
        b"4500000000 8589934592", # 4.5 cores, 8GB
        b"MAX_RAM=6.0 PATH=/bin"   # MAX_RAM=6.0
    ])
    
    # Mock constants used in MCDashboard
    mocker.patch("core.dashboard.CONTAINER_NAME", "test-container")
    
    dashboard = MCDashboard()
    # Initialize with different values to ensure they change
    dashboard.cpu_limit = 1.0
    dashboard.mem_limit_gb = 1.0
    dashboard.jvm_max_ram = 1.0
    
    dashboard._refresh_container_limits()
    
    assert dashboard.cpu_limit == 4.5
    assert dashboard.mem_limit_gb == 8.0
    assert dashboard.jvm_max_ram == 6.0
