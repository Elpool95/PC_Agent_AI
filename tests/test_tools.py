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


def test_piano_energetico_e_modalita(tmp_path):
    state_file = str(tmp_path / "gaming_state.json")
    with patch("subprocess.check_output", return_value="GUID: 381b4222-f694-41f0-9685-ff5bb260df2e (Bilanciato)"):
        assert tools.piano_energetico_attivo()["modalita"] == "bilanciato"
    with patch("subprocess.check_output", return_value="GUID: 11111111-1111-1111-1111-111111111111 (Prestazioni eccellenti)"):
        assert tools.piano_energetico_attivo()["modalita"] == "gaming"

    fake_proc = MagicMock()
    fake_proc.info = {"name": "chrome.exe", "memory_info": SimpleNamespace(rss=512 * 1024 * 1024)}
    prot_proc = MagicMock()
    prot_proc.info = {"name": "discord.exe", "memory_info": SimpleNamespace(rss=200 * 1024 * 1024)}

    fake_vm = SimpleNamespace(used=8 * 1024**3)
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools.piano_energetico_attivo", return_value={"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "nome": "Bilanciato", "modalita": "bilanciato"}), \
         patch("modules.tools._trova_o_crea_prestazioni_eccellenti", return_value="11111111-1111-1111-1111-111111111111"), \
         patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as mock_run, \
         patch("modules.tools.applica_ottimizzazioni_registro_gaming", return_value=["Windows Game Mode ON", "Notifiche Toast OFF"]), \
         patch("modules.tools.applica_fps_cap_gaming", return_value={"applicato": True, "target_fps": 72, "refresh_hz": 75, "messaggio": "Limite FPS NVIDIA (Max Frame Rate): 72 FPS (monitor principale 2560x1080 @ 75 Hz, margine -3 Hz)."}), \
         patch("modules.tools.imposta_priorita_processo_corrente", return_value=True) as mock_prio, \
         patch("psutil.virtual_memory", return_value=fake_vm), \
         patch("psutil.wait_procs", return_value=([], [])), \
         patch("psutil.process_iter", return_value=[fake_proc, prot_proc]):
        msg = tools.attiva_modalita_prestazioni()
    assert "Prestazioni eccellenti" in msg
    assert "USB Suspend OFF" in msg
    assert "Windows Game Mode ON" in msg
    assert "72 FPS" in msg
    assert "chrome.exe" in msg
    assert "512.0 MB" in msg
    assert "BELOW_NORMAL" in msg
    fake_proc.terminate.assert_called_once()
    prot_proc.terminate.assert_not_called()
    mock_prio.assert_called_once_with(True)
    assert mock_run.called

    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("subprocess.run") as mock_run2, \
         patch("modules.tools.ripristina_ottimizzazioni_registro_gaming", return_value=4), \
         patch("modules.tools.ripristina_fps_cap_gaming", return_value=" Limite FPS NVIDIA rimosso (Disattivato)."), \
         patch("modules.tools.imposta_priorita_processo_corrente", return_value=True) as mock_prio2:
        res_bil = tools.ripristina_modalita_bilanciata()
        assert "Bilanciato" in res_bil
        assert "4 impostazioni" in res_bil
        assert "Limite FPS NVIDIA rimosso" in res_bil
        mock_run2.assert_called_once()
        mock_prio2.assert_called_once_with(False)


def test_gaming_tuning_powercfg_and_dast():
    valid_guid = "11111111-1111-1111-1111-111111111111"
    with patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as mock_run:
        res = tools._ottimizza_piano_gaming(valid_guid)
    assert res == ["USB Suspend OFF", "PCIe Power Mgmt OFF", "Disk Standby OFF", "CPU Core Unpark 100%"]
    assert mock_run.call_count == 4

    # DAST: GUID malformato o con metacaratteri shell bloccato
    with patch("subprocess.run") as mock_bad:
        assert tools._ottimizza_piano_gaming("bad-guid & calc.exe") == []
        assert tools._ottimizza_piano_gaming("") == []
        mock_bad.assert_not_called()


def test_gaming_registro_hkcu_e_rollback(tmp_path):
    state_file = str(tmp_path / "gaming_state.json")
    tools._GAMING_REG_SNAPSHOT.clear()
    mock_key = MagicMock()
    mock_key.__enter__.return_value = mock_key

    # 3 chiavi esistevano, 4 non esistevano (FileNotFoundError)
    query_side = [(1, 4), FileNotFoundError(), FileNotFoundError(), FileNotFoundError(), (1, 4), (1, 4), FileNotFoundError()]
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools.abilita_vrr_windows", return_value=True), \
         patch("modules.tools._imposta_animazioni_ui", return_value=True) as mock_anim, \
         patch("winreg.CreateKeyEx", return_value=mock_key), \
         patch("winreg.QueryValueEx", side_effect=query_side), \
         patch("winreg.SetValueEx") as mock_set:
        applicati = tools.applica_ottimizzazioni_registro_gaming()
    assert len(applicati) == 9
    assert "Trasparenze DWM OFF" in applicati
    assert "Effetti Visivi Ridotti" in applicati
    assert "Animazioni UI OFF" in applicati
    assert "VRR & Windowed Opt ON" in applicati
    mock_anim.assert_called_once_with(False)
    assert mock_set.call_count == 7
    assert len(tools._GAMING_REG_SNAPSHOT) == 7
    assert os.path.isfile(state_file)

    # Simula chiusura e riapertura dell'app azzerando lo snapshot in RAM
    tools._GAMING_REG_SNAPSHOT.clear()

    # Rollback da disco: 3 chiavi ripristinate con SetValueEx, 4 rimosse con DeleteValue
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._imposta_animazioni_ui", return_value=True) as mock_anim_restore, \
         patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.SetValueEx") as mock_restore_set, \
         patch("winreg.DeleteValue") as mock_restore_del:
        ripristinati = tools.ripristina_ottimizzazioni_registro_gaming()
    assert ripristinati == 7
    assert mock_restore_set.call_count == 3
    assert mock_restore_del.call_count == 4
    mock_anim_restore.assert_called_once_with(True)
    assert len(tools._GAMING_REG_SNAPSHOT) == 0
    assert not os.path.exists(state_file)


def test_priorita_processo_e_formatta_ram():
    mock_proc = MagicMock()
    with patch("psutil.Process", return_value=mock_proc):
        assert tools.imposta_priorita_processo_corrente(True) is True
        mock_proc.nice.assert_called_with(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        assert tools.imposta_priorita_processo_corrente(False) is True
        mock_proc.nice.assert_called_with(psutil.NORMAL_PRIORITY_CLASS)

    with patch("psutil.Process", side_effect=psutil.AccessDenied()):
        assert tools.imposta_priorita_processo_corrente(True) is False

    assert tools._formatta_ram_liberata(512 * 1024 * 1024) == "512.0 MB"
    assert tools._formatta_ram_liberata(2 * 1024**3) == "2.00 GB"


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


def test_maschera_percorso_utente():
    home = os.path.expanduser("~")
    esempio = os.path.join(home, "AppData", "Local", "Temp")
    mascherato = tools.maschera_percorso_utente(esempio)
    assert mascherato.startswith("%USERPROFILE%")
    assert home.lower() not in mascherato.lower()
    assert tools.maschera_percorso_utente("") == ""


def test_stato_sicurezza_lhm_e_blocco_lan():
    conn_lan = SimpleNamespace(laddr=SimpleNamespace(ip="::", port=8085), status=psutil.CONN_LISTEN)
    conn_local = SimpleNamespace(laddr=SimpleNamespace(ip="127.0.0.1", port=8085), status=psutil.CONN_LISTEN)

    # Esposto su LAN senza regola firewall
    with patch("psutil.net_connections", return_value=[conn_lan]), \
         patch("subprocess.run", return_value=SimpleNamespace(returncode=1)):
        st = tools.stato_sicurezza_lhm()
    assert st == {"attivo": True, "esposto_lan": True, "protetto_firewall": False, "sicuro": False}

    # Esposto su LAN ma protetto da regola firewall
    with patch("psutil.net_connections", return_value=[conn_lan]), \
         patch("subprocess.run", return_value=SimpleNamespace(returncode=0)):
        st_ok = tools.stato_sicurezza_lhm()
    assert st_ok["sicuro"] is True and st_ok["protetto_firewall"] is True

    # Solo localhost -> sicuro anche senza regola firewall
    with patch("psutil.net_connections", return_value=[conn_local]), \
         patch("subprocess.run", return_value=SimpleNamespace(returncode=1)):
        st_loc = tools.stato_sicurezza_lhm()
    assert st_loc["sicuro"] is True and st_loc["esposto_lan"] is False

    # Blocco LAN: già protetto
    with patch("modules.tools.stato_sicurezza_lhm", return_value={"protetto_firewall": True}):
        assert "già protetta" in tools.blocca_lhm_da_lan()

    # Blocco LAN: UAC accettato (> 32) e annullato (<= 32)
    with patch("modules.tools.stato_sicurezza_lhm", return_value={"protetto_firewall": False}), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=42):
        assert "aggiunta" in tools.blocca_lhm_da_lan()
    with patch("modules.tools.stato_sicurezza_lhm", return_value={"protetto_firewall": False}), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=5):
        assert "annullata" in tools.blocca_lhm_da_lan().lower()


def test_pausa_e_riavvio_servizi_gaming_and_dast(tmp_path):
    state_file = str(tmp_path / "gaming_state.json")
    tools._SERVIZI_IN_PAUSA.clear()

    svc_running = SimpleNamespace(status=lambda: "running")
    svc_stopped = SimpleNamespace(status=lambda: "stopped")
    with patch("psutil.win_service_get", side_effect=[svc_running, svc_stopped, svc_running]):
        assert tools.servizi_gaming_attivi() == ["WSearch", "DiagTrack"]

    # DAST: servizi fuori allowlist o con metacaratteri shell vengono filtrati
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("ctypes.windll.shell32.ShellExecuteW") as mock_uac:
        res_bad = tools.pausa_servizi_gaming(["vgc", "WSearch; calc.exe"])
        assert "Nessun servizio" in res_bad
        mock_uac.assert_not_called()

    # Pausa UAC confermata (> 32), simulazione riavvio app (clear RAM), poi riavvio servizi da snapshot disco
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=42):
        res_ok = tools.pausa_servizi_gaming(["WSearch", "SysMain"])
        assert "messi in pausa" in res_ok
        tools._SERVIZI_IN_PAUSA.clear()  # simula chiusura e riapertura app
        assert tools.ha_servizi_gaming_in_pausa() is True

        res_restart = tools.riavvia_servizi_gaming()
        assert "riavviati" in res_restart
        assert tools.ha_servizi_gaming_in_pausa() is False
        assert not os.path.exists(state_file)

    # Nessun servizio in pausa -> stringa vuota senza UAC
    with patch("modules.tools.GAMING_STATE_FILE", state_file):
        assert tools.riavvia_servizi_gaming() == ""

    # UAC annullata (<= 32)
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=5):
        assert "annullata" in tools.pausa_servizi_gaming(["WSearch"]).lower()
        assert tools.ha_servizi_gaming_in_pausa() is False


def test_snapshot_persistente_piano_personalizzato(tmp_path):
    state_file = str(tmp_path / "gaming_state.json")
    custom_guid = "99999999-8888-7777-6666-555555555555"
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools.piano_energetico_attivo", return_value={"guid": custom_guid, "nome": "AMD Ryzen Balanced", "modalita": "bilanciato"}), \
         patch("modules.tools._trova_o_crea_prestazioni_eccellenti", return_value="11111111-1111-1111-1111-111111111111"), \
         patch("subprocess.run", return_value=SimpleNamespace(returncode=0)), \
         patch("modules.tools.applica_ottimizzazioni_registro_gaming", return_value=[]), \
         patch("modules.tools.applica_fps_cap_gaming", return_value={"applicato": False, "target_fps": 0, "refresh_hz": 0, "messaggio": ""}), \
         patch("modules.tools.imposta_priorita_processo_corrente", return_value=True), \
         patch("psutil.virtual_memory", return_value=SimpleNamespace(used=4 * 1024**3)), \
         patch("psutil.process_iter", return_value=[]):
        tools.attiva_modalita_prestazioni()

    assert os.path.isfile(state_file)

    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("subprocess.run") as mock_restore_run, \
         patch("modules.tools.ripristina_ottimizzazioni_registro_gaming", return_value=0), \
         patch("modules.tools.ripristina_fps_cap_gaming", return_value=""), \
         patch("modules.tools.imposta_priorita_processo_corrente", return_value=True):
        res = tools.ripristina_modalita_bilanciata()
    assert "AMD Ryzen Balanced" in res
    mock_restore_run.assert_called_once()
    assert custom_guid in mock_restore_run.call_args[0][0]
    assert not os.path.exists(state_file)


def test_diagnostica_pre_partita_ok_e_avvisi():
    mon_dldsr_ok = {"larghezza": 2560, "altezza": 1080, "refresh_hz": 75, "risoluzioni_dldsr": ["3413x1440"], "dldsr_attivo": True}
    # Caso tutto OK
    ram_ok = {"banchi": [{"gb": 8}, {"gb": 8}], "modalita_canale": "Dual Channel", "tipo": "DDR4", "frequenza_mhz": 3200}
    with patch("modules.tools._leggi_hags_attivo", return_value=True), \
         patch("modules.tools._leggi_vrr_attivo", return_value=True), \
         patch("modules.tools._leggi_physx_auto", return_value=False), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Ethernet", "ip": "192.168.1.2", "link_mbps": 1000}), \
         patch("modules.tools.misura_ping", return_value={"ms": 14, "stato": "14 ms"}), \
         patch("psutil.disk_usage", return_value=SimpleNamespace(percent=50.0, free=200 * 1024**3)), \
         patch("modules.tools.monitora_gpu", return_value={"temperatura_num": 40, "temperatura_c": "40°C", "gpu": "NVIDIA GeForce RTX 3070", "vram_totale_mb": "8192"}), \
         patch("modules.tools.leggi_sensori_cpu", return_value={"temperatura_c": "42,0 °C"}), \
         patch("modules.tools.info_monitor_principale", return_value=mon_dldsr_ok):
        res_ok = tools.diagnostica_pre_partita(ram_ok)
    assert res_ok["ok"] is True
    assert res_ok["consiglia_dldsr"] is None
    assert "tutto OK" in res_ok["testo"]

    # Caso con colli di bottiglia reali (HAGS off, VRR off, PhysX Auto, Wi-Fi, ping alto, C: pieno, GPU/CPU calde, RAM Single Channel base)
    ram_slow = {"banchi": [{"gb": 8}], "modalita_canale": "Single Channel", "tipo": "DDR4", "frequenza_mhz": 2133}
    with patch("modules.tools._leggi_hags_attivo", return_value=False), \
         patch("modules.tools._leggi_vrr_attivo", return_value=False), \
         patch("modules.tools._leggi_physx_auto", return_value=True), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Wi-Fi", "ip": "192.168.1.5", "link_mbps": 300}), \
         patch("modules.tools.misura_ping", return_value={"ms": 85, "stato": "85 ms"}), \
         patch("psutil.disk_usage", return_value=SimpleNamespace(percent=95.0, free=10 * 1024**3)), \
         patch("modules.tools.monitora_gpu", return_value={"temperatura_num": 78, "temperatura_c": "78°C", "gpu": "NVIDIA GeForce RTX 3070", "vram_totale_mb": "8192"}), \
         patch("modules.tools.leggi_sensori_cpu", return_value={"temperatura_c": "80,5 °C"}), \
         patch("modules.tools.info_monitor_principale", return_value=mon_dldsr_ok):
        res_warn = tools.diagnostica_pre_partita(ram_slow)
    assert res_warn["ok"] is False
    assert len(res_warn["avvisi"]) == 10
    assert "HAGS" in res_warn["testo"]
    assert "VRR" in res_warn["testo"]
    assert "PhysX" in res_warn["testo"]
    assert "Wi-Fi" in res_warn["testo"]
    assert "Single Channel" in res_warn["testo"]
    assert "XMP/EXPO" in res_warn["testo"]


def test_priorita_background_gaming_e_anticheat_intatto():
    p_discord = MagicMock()
    p_discord.info = {"name": "discord.exe"}
    p_steam = MagicMock()
    p_steam.info = {"name": "steamwebhelper.exe"}
    p_vgc = MagicMock()
    p_vgc.info = {"name": "vgc.exe"}
    p_riot = MagicMock()
    p_riot.info = {"name": "riotclientux.exe"}

    with patch("psutil.process_iter", return_value=[p_discord, p_steam, p_vgc, p_riot]):
        mod = tools.imposta_priorita_background_gaming(True)
    assert mod == ["discord.exe", "steamwebhelper.exe"]
    p_discord.nice.assert_called_once_with(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    p_steam.nice.assert_called_once_with(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    p_vgc.nice.assert_not_called()
    p_riot.nice.assert_not_called()

    with patch("psutil.process_iter", return_value=[p_discord, p_steam, p_vgc, p_riot]):
        restored = tools.imposta_priorita_background_gaming(False)
    assert restored == ["discord.exe", "steamwebhelper.exe"]
    p_discord.nice.assert_called_with(psutil.NORMAL_PRIORITY_CLASS)
    p_vgc.nice.assert_not_called()
    p_riot.nice.assert_not_called()


def test_vrr_windows_parse_leggi_e_abilita():
    assert tools._parse_directx_global_settings("SwapEffectUpgradeEnable=1;CustomFlag=0;") == {
        "SwapEffectUpgradeEnable": "1",
        "CustomFlag": "0",
    }

    mock_key = MagicMock()
    mock_key.__enter__.return_value = mock_key

    with patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.QueryValueEx", return_value=("SwapEffectUpgradeEnable=1;VRROptimizeEnable=1;", 1)):
        assert tools._leggi_vrr_attivo() is True

    with patch("winreg.OpenKey", return_value=mock_key), \
         patch("winreg.QueryValueEx", return_value=("SwapEffectUpgradeEnable=1;", 1)):
        assert tools._leggi_vrr_attivo() is False

    with patch("winreg.CreateKeyEx", return_value=mock_key), \
         patch("winreg.QueryValueEx", return_value=("CustomFlag=1;SwapEffectUpgradeEnable=1;", 1)), \
         patch("winreg.SetValueEx") as mock_set:
        assert tools.abilita_vrr_windows() is True
    scritto = mock_set.call_args[0][4]
    assert "CustomFlag=1;" in scritto
    assert "SwapEffectUpgradeEnable=1;" in scritto
    assert "VRROptimizeEnable=1;" in scritto


def test_abilita_hags():
    with patch("modules.tools._leggi_hags_attivo", return_value=True):
        assert "già attivo" in tools.abilita_hags()

    with patch("modules.tools._leggi_hags_attivo", return_value=False), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=42) as mock_uac:
        res_ok = tools.abilita_hags()
    assert "abilitato" in res_ok.lower()
    assert "riavvia" in res_ok.lower()
    mock_uac.assert_called_once()

    with patch("modules.tools._leggi_hags_attivo", return_value=False), \
         patch("ctypes.windll.shell32.ShellExecuteW", return_value=5):
        assert "annullata" in tools.abilita_hags().lower()


def test_fps_cap_gaming_e_ripristino_persistente(tmp_path):
    state_file = str(tmp_path / "gaming_state.json")
    mon_75 = {"larghezza": 2560, "altezza": 1080, "refresh_hz": 75, "risoluzioni_dldsr": [], "dldsr_attivo": False}

    # Caso 1: nessun cap precedente -> imposta 72 FPS e su Balance rimuove ('delete')
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._nvapi_drs_frl_fps", side_effect=[(True, None), (True, 72)]) as mock_nv:
        res = tools.applica_fps_cap_gaming(mon_75)
    assert res["applicato"] is True
    assert res["target_fps"] == 72
    assert "72 FPS" in res["messaggio"]
    assert "2560x1080 @ 75 Hz" in res["messaggio"]
    assert mock_nv.call_args_list[1].args == ("set", 72)
    assert os.path.isfile(state_file)

    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._nvapi_drs_frl_fps", return_value=(True, None)) as mock_nv_del:
        msg_rest = tools.ripristina_fps_cap_gaming()
    assert "rimosso" in msg_rest.lower()
    mock_nv_del.assert_called_once_with("delete")
    assert not os.path.exists(state_file)

    # Caso 2: esisteva un cap precedente (es. 120 FPS) su monitor 144 Hz -> imposta 141 FPS e poi ripristina 120 FPS
    mon_144 = {"larghezza": 2560, "altezza": 1440, "refresh_hz": 144, "risoluzioni_dldsr": [], "dldsr_attivo": False}
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._nvapi_drs_frl_fps", side_effect=[(True, 120), (True, 141)]):
        res2 = tools.applica_fps_cap_gaming(mon_144)
    assert res2["applicato"] is True and res2["target_fps"] == 141

    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._nvapi_drs_frl_fps", return_value=(True, 120)) as mock_nv_rest:
        msg_rest2 = tools.ripristina_fps_cap_gaming()
    assert "120 FPS" in msg_rest2
    mock_nv_rest.assert_called_once_with("set", 120)

    # Caso 3: monitor non valido o GPU non NVIDIA -> degrada senza errori
    with patch("modules.tools.GAMING_STATE_FILE", state_file):
        assert tools.applica_fps_cap_gaming({"refresh_hz": 0})["applicato"] is False
    with patch("modules.tools.GAMING_STATE_FILE", state_file), \
         patch("modules.tools._nvapi_drs_frl_fps", return_value=(False, None)):
        assert tools.applica_fps_cap_gaming(mon_75)["applicato"] is False


def test_diagnostica_dldsr_cpu_bound_e_monitor():
    mon_no_dldsr = {"larghezza": 2560, "altezza": 1080, "refresh_hz": 75, "risoluzioni_dldsr": [], "dldsr_attivo": False}
    ram_ok = {"banchi": [{"gb": 8}, {"gb": 8}], "modalita_canale": "Dual Channel", "tipo": "DDR4", "frequenza_mhz": 3200}
    with patch("modules.tools._leggi_hags_attivo", return_value=True), \
         patch("modules.tools._leggi_vrr_attivo", return_value=True), \
         patch("modules.tools._leggi_physx_auto", return_value=False), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Ethernet", "ip": "192.168.1.2", "link_mbps": 1000}), \
         patch("modules.tools.misura_ping", return_value={"ms": 14, "stato": "14 ms"}), \
         patch("psutil.disk_usage", return_value=SimpleNamespace(percent=50.0, free=200 * 1024**3)), \
         patch("psutil.cpu_count", return_value=4), \
         patch("modules.tools.monitora_gpu", return_value={"temperatura_num": 40, "temperatura_c": "40°C", "gpu": "NVIDIA GeForce RTX 3070", "vram_totale_mb": "8192"}), \
         patch("modules.tools.leggi_sensori_cpu", return_value={"temperatura_c": "42,0 °C"}), \
         patch("modules.tools.info_monitor_principale", return_value=mon_no_dldsr):
        res = tools.diagnostica_pre_partita(ram_ok)
    assert res["ok"] is False
    assert res["consiglia_dldsr"] == {"nativa": "2560x1080", "res_178": "3413x1440", "res_225": "3840x1620"}
    assert "DLDSR" in res["testo"]
    assert "3413x1440" in res["testo"]

    # Smoke test lettura reale monitor principale
    mon = tools.info_monitor_principale()
    assert {"larghezza", "altezza", "refresh_hz", "dldsr_attivo"}.issubset(mon.keys())
