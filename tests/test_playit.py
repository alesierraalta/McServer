import pytest
from core.manager import check_playit_status, get_playit_address
from core.config import PLAYIT_LOG_FILE
import os

@pytest.fixture
def mock_log(tmp_path, monkeypatch):
    log_file = tmp_path / "playit.log"
    # Redirigir la constante en el módulo core.manager para el test
    import core.manager
    monkeypatch.setattr(core.manager, "PLAYIT_LOG_FILE", log_file)
    return log_file

def test_status_connected(mock_log):
    mock_log.write_text("2026-05-15 INFO: tunnel running\n2026-05-15 INFO: tunnel established")
    connected, status = check_playit_status()
    assert connected is True
    assert status == "Conectado"

def test_status_not_linked(mock_log):
    mock_log.write_text("Visit https://playit.gg/claim/xyz to approve program")
    connected, status = check_playit_status()
    assert connected is False
    assert "No vinculado" in status

def test_ip_extraction(mock_log):
    mock_log.write_text('tunnels: [Tunnel { address: "mi-server.playit.gg" }]')
    addr = get_playit_address()
    assert addr == "mi-server.playit.gg"

def test_ip_extraction_fallback(mock_log):
    mock_log.write_text('Some logs with fancy-server-123.playit.gg inside')
    addr = get_playit_address()
    assert addr == "fancy-server-123.playit.gg"
