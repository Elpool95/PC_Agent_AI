import io
import json
import os
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import psutil
import pytest
from modules import tools


class _FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_trova_nvidia_smi():
    with patch("shutil.which", return_value=r"C:\Windows\System32\nvidia-smi.exe"):
        assert tools._trova_nvidia_smi().endswith("nvidia-smi.exe")
    with patch("shutil.which", return_value=None), patch("os.path.exists", return_value=False):
        assert tools._trova_nvidia_smi() == "nvidia-smi"


def test_analizza_sistema():
    p1 = SimpleNamespace(info={"pid": 10, "name": "appA.exe", "cpu_percent": 25.0, "memory_info": SimpleNamespace(rss=500 * 1024 * 1024)})
    p2 = SimpleNamespace(info={"pid": 20, "name": "appB.exe", "cpu_percent": 5.0, "memory_info": SimpleNamespace(rss=900 * 1024 * 1024)})
    p3 = SimpleNamespace(info={"pid": 0, "name": "System Idle Process", "cpu_percent": 90.0, "memory_info": None})
    fake_ram = SimpleNamespace(percent=42.0, used=10 * 1024**3, total=24 * 1024**3)
    with patch("psutil.cpu_percent", return_value=15.0), \
         patch("psutil.virtual_memory", return_value=fake_ram), \
         patch("psutil.process_iter", return_value=[p1, p2, p3]):
        res = tools.analizza_sistema()
    assert res["cpu_percent"] == 15.0
    assert res["top_processi_cpu"][0]["name"] == "appA.exe"
    assert res["top_processi_ram"][0]["name"] == "appB.exe"
    assert res["top_processi_ram"][0]["ram_mb"] == 900.0


def test_monitora_gpu_success_and_error():
    sample = "NVIDIA GeForce RTX 3070, 12, 41, 1024, 8192, 30.5, 45, 1725, P2\n"
    with patch("subprocess.check_output", return_value=sample):
        res = tools.monitora_gpu()
    assert res["gpu"] == "NVIDIA GeForce RTX 3070"
    assert res["utilizzo_num"] == 12
    assert res["temperatura_num"] == 41
    assert res["ventola_percent"] == "45%"
    assert res["clock_mhz"] == "1725 MHz"

    with patch("subprocess.check_output", side_effect=FileNotFoundError("no smi")):
        err = tools.monitora_gpu()
    assert "errore" in err


def test_leggi_sensori_cpu_and_offline():
    lhm_data = {
        "Children": [
            {
                "Text": "CPU",
                "Children": [
                    {"Text": "CPU Package", "Value": "42,5 °C"},
                    {"Text": "CPU Package", "Value": "22,1 W"},
                ],
            },
            {
                "Text": "Fans",
                "Children": [
                    {"Text": "Fan #1", "Value": "1500 RPM"},
                    {"Text": "Fan #2", "Value": "0 RPM"},
                    {"Text": "GPU Fan 1", "Value": "1200 RPM"},
                ],
            },
        ]
    }
    with patch("urllib.request.urlopen", return_value=_FakeResponse(lhm_data)):
        res = tools.leggi_sensori_cpu()
        assert res["temperatura_c"] == "42,5 °C"
        assert res["potenza_w"] == "22,1 W"
        assert res["ventole_rpm"] == ["F1: 1500 RPM"]
        assert tools.leggi_temp_cpu() == "42,5 °C"

    with patch("urllib.request.urlopen", side_effect=OSError("offline")):
        res_off = tools.leggi_sensori_cpu()
        assert "avvia LHM" in res_off["temperatura_c"]
        assert res_off["ventole_rpm"] == []


def test_dischi_helpers():
    parts = [
        SimpleNamespace(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed"),
        SimpleNamespace(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw,fixed"),
        SimpleNamespace(device="G:\\", mountpoint="G:\\", fstype="", opts="cdrom"),
    ]
    with patch("psutil.disk_partitions", return_value=parts):
        assert tools.elenca_lettere_dischi() == ["C", "D"]

    with patch("subprocess.check_output", return_value="C:PhysicalDrive0\nD:PhysicalDrive1\n"):
        assert tools.mappa_dischi_fisici() == {"C": "PhysicalDrive0", "D": "PhysicalDrive1"}
        assert tools.mappa_dischi_fisici(("C",)) == {"C": "PhysicalDrive0"}

    fake_usage = SimpleNamespace(used=100 * 1024**3, free=50 * 1024**3, total=150 * 1024**3, percent=66.7)
    with patch("psutil.disk_partitions", return_value=parts), patch("psutil.disk_usage", return_value=fake_usage):
        arch = tools.monitora_archiviazione()
    assert len(arch) == 2
    assert arch[0]["unita"] == "C:\\"


def test_info_banchi_ram_dual_and_single():
    dual_json = json.dumps([
        {"BankLabel": "BANK 0", "DeviceLocator": "ChannelA-DIMM0", "PartNumber": "CMK8G", "Capacity": 8 * 1024**3, "ConfiguredClockSpeed": 2133, "ConfiguredVoltage": 1200, "SMBIOSMemoryType": 26},
        {"BankLabel": "BANK 2", "DeviceLocator": "ChannelB-DIMM0", "PartNumber": "CMK8G", "Capacity": 8 * 1024**3, "ConfiguredClockSpeed": 2133, "ConfiguredVoltage": 1200, "SMBIOSMemoryType": 26},
    ])
    with patch("subprocess.check_output", return_value=dual_json):
        res = tools.info_banchi_ram()
    assert res["totale_gb"] == 16
    assert res["modalita_canale"] == "Dual Channel"
    assert res["tipo"] == "DDR4"
    assert res["frequenza_mhz"] == 2133

    single_json = json.dumps(
        {"BankLabel": "BANK 0", "DeviceLocator": "ChannelA-DIMM0", "PartNumber": "", "Capacity": 8 * 1024**3, "Speed": 3200, "ConfiguredVoltage": 0, "SMBIOSMemoryType": 26}
    )
    with patch("subprocess.check_output", return_value=single_json):
        res_s = tools.info_banchi_ram()
    assert res_s["modalita_canale"] == "Single Channel"
    assert res_s["banchi"][0]["voltaggio"] == "N/D"


def test_rete_and_ping_including_dast():
    stats = {
        "Loopback Pseudo-Interface 1": SimpleNamespace(isup=True, speed=1000),
        "Ethernet": SimpleNamespace(isup=True, speed=1000),
    }
    addrs = {
        "Ethernet": [SimpleNamespace(family=socket.AF_INET, address="192.168.1.50")],
    }
    with patch("psutil.net_if_stats", return_value=stats), patch("psutil.net_if_addrs", return_value=addrs):
        net = tools.info_rete_attiva()
    assert net == {"nome": "Ethernet", "ip": "192.168.1.50", "link_mbps": 1000}

    with patch("psutil.net_if_stats", return_value={}):
        assert tools.info_rete_attiva()["nome"] == "Offline"

    assert tools.formatta_velocita_rete(250_000) == "2.00 Mbps"
    assert tools.formatta_velocita_rete(12_500) == "100.0 Kbps"

    with patch("subprocess.check_output", return_value="Risposta da 1.1.1.1: byte=32 durata=14ms TTL=57"):
        assert tools.misura_ping("1.1.1.1")["stato"] == "14 ms"
    with patch("subprocess.check_output", return_value="Reply from 1.1.1.1: time<1ms"):
        assert tools.misura_ping("1.1.1.1")["stato"] == "<1 ms"
    with patch("subprocess.check_output", return_value="Richiesta scaduta."):
        assert tools.misura_ping("1.1.1.1")["stato"] == "Timeout"

    # DAST / Pentest: command injection & flag injection
    for bad in ("1.1.1.1 & calc.exe", "-t", "/?", "", "host;whoami"):
        assert tools.misura_ping(bad)["stato"] == "Host non valido"


def test_piano_energetico_e_modalita():
    with patch("subprocess.check_output", return_value="GUID: 381b4222-f694-41f0-9685-ff5bb260df2e (Bilanciato)"):
        assert tools.piano_energetico_attivo()["modalita"] == "bilanciato"
    with patch("subprocess.check_output", return_value="GUID: 11111111-1111-1111-1111-111111111111 (Prestazioni eccellenti)"):
        assert tools.piano_energetico_attivo()["modalita"] == "gaming"

    fake_proc = MagicMock()
    fake_proc.info = {"name": "chrome.exe"}
    prot_proc = MagicMock()
    prot_proc.info = {"name": "discord.exe"}

    with patch("modules.tools._trova_o_crea_prestazioni_eccellenti", return_value="11111111-1111-1111-1111-111111111111"), \
         patch("subprocess.run") as mock_run, \
         patch("psutil.process_iter", return_value=[fake_proc, prot_proc]):
        msg = tools.attiva_modalita_prestazioni()
    assert "Prestazioni eccellenti" in msg
    assert "chrome.exe" in msg
    fake_proc.terminate.assert_called_once()
    prot_proc.terminate.assert_not_called()
    assert mock_run.called

    with patch("subprocess.run") as mock_run2:
        assert "Bilanciato" in tools.ripristina_modalita_bilanciata()
        mock_run2.assert_called_once()


def test_analizza_spazio_disco_and_pulisci_temp(tmp_path):
    # DAST: path traversal and invalid drive
    assert "errore" in tools.analizza_spazio_disco("../../Windows")
    assert "errore" in tools.analizza_spazio_disco("Z:")

    # Valid drive analysis using tmp_path as TEMP
    f1 = tmp_path / "temp1.tmp"
    f1.write_text("a" * 1024, encoding="utf-8")
    d1 = tmp_path / "subdir"
    d1.mkdir()
    (d1 / "nested.tmp").write_text("b" * 2048, encoding="utf-8")

    drive = os.path.splitdrive(str(tmp_path))[0]
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        res_disk = tools.analizza_spazio_disco(drive)
        assert res_disk["unita"] == drive.upper()
        assert isinstance(res_disk["cartelle_analizzate"], list)
        msg = tools.pulisci_file_temporanei()
    assert "rimossi 2" in msg
    assert not f1.exists() and not d1.exists()


def test_app_avvio_e_piano_eccellenti():
    mock_key = MagicMock()
    mock_key.__enter__.return_value = mock_key
    with patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.EnumValue", side_effect=[("MyApp", "C:\\app.exe", 1), OSError(), OSError()]):
        apps = tools.elenca_app_avvio()
    assert "MyApp" in apps["utente_corrente"]

    with patch("winreg.OpenKey", return_value=mock_key), patch("winreg.DeleteValue"):
        assert "rimossa correttamente" in tools.disabilita_app_avvio("MyApp")
    with patch("winreg.OpenKey", return_value=mock_key), patch("winreg.DeleteValue", side_effect=FileNotFoundError()):
        assert "non trovata" in tools.disabilita_app_avvio("MissingApp")

    guid = "12345678-1234-1234-1234-123456789abc"
    with patch("subprocess.check_output", return_value=f"GUID: {guid} (Prestazioni eccellenti)"):
        assert tools._trova_o_crea_prestazioni_eccellenti() == guid
    with patch("subprocess.check_output", side_effect=["GUID: 0000 (Bilanciato)", f"GUID: {guid}"]):
        assert tools._trova_o_crea_prestazioni_eccellenti() == guid


def test_termina_processo_guards_and_execution():
    # Protected & system processes + metacharacters
    assert "bloccata" in tools.termina_processo("discord.exe").lower()
    assert "bloccata" in tools.termina_processo("explorer.exe").lower()
    assert "me stesso" in tools.termina_processo(str(os.getpid())).lower()
    assert "valido" in tools.termina_processo("notepad.exe & calc").lower()
    assert "valido" in tools.termina_processo("").lower()

    # Valid PID termination (mocked)
    mock_p = MagicMock()
    mock_p.name.return_value = "notepad.exe"
    with patch("psutil.Process", return_value=mock_p):
        assert "terminato correttamente" in tools.termina_processo("99999")
    mock_p.terminate.assert_called_once()

    # Valid name termination (mocked)
    p_match = MagicMock()
    p_match.info = {"pid": 88888, "name": "notepad.exe"}
    with patch("psutil.process_iter", return_value=[p_match]):
        assert "Terminati 1" in tools.termina_processo("notepad")
    p_match.terminate.assert_called_once()

    with patch("psutil.process_iter", return_value=[]):
        assert "Nessun processo attivo" in tools.termina_processo("ghost_app.exe")


def test_info_versioni_e_cpu_nome():
    assert isinstance(tools.info_cpu_nome(), str)
    with patch("subprocess.check_output", return_value="621.40\n"):
        v = tools.info_versioni_sistema()
    assert v["driver_gpu"] == "621.40"
    assert "Windows" in v["windows"]
