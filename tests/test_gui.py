import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest
from modules.agent_win11 import PCAgentGUI


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def gui_app(tk_root):
    win = tk.Toplevel(tk_root)
    win.withdraw()
    with patch("threading.Thread") as mock_thread:
        app = PCAgentGUI(win)
    win.update_idletasks()
    yield app, win, mock_thread
    win.destroy()


def test_gui_usability_labels_and_bottom_anchor(gui_app):
    app, root, _ = gui_app
    # Verifica etichette pulsanti richieste
    buttons = []
    def collect_buttons(widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Button):
                buttons.append(child.cget("text"))
            collect_buttons(child)
    collect_buttons(root)

    expected = {"Top Process", "Storage", "Gaming Mode", "Balance", "Start App", "RAM Detail", "Lock LHM", "Clear", "Send"}
    assert expected.issubset(set(buttons))
    assert app.lbl_footer.master.pack_info()["side"] == "bottom"
    assert app.entry.master.pack_info()["side"] == "bottom"


def test_gui_disk_colors_per_individual_drive(gui_app):
    app, root, _ = gui_app
    items = [
        ("C", "C: 95.0% [!] (11GB liberi) R 0.0/W 0.0 MB/s", "#ff5252"),
        ("D", "D: 85.0% (30GB liberi) R 0.0/W 0.0 MB/s", "#ffb74d"),
        ("E", "E: 10.0% (800GB liberi) R 0.0/W 0.0 MB/s", "#ce93d8"),
    ]
    app._aggiorna_dischi_ui(items)
    root.update_idletasks()

    assert app.disk_labels["C"].cget("fg") == "#ff5252"
    assert app.disk_labels["D"].cget("fg") == "#ffb74d"
    assert app.disk_labels["E"].cget("fg") == "#ce93d8"

    # Aggiornamento in-place sugli stessi dischi
    items_updated = [
        ("C", "C: 94.0% [!] (12GB liberi)", "#ff5252"),
        ("D", "D: 70.0% (50GB liberi)", "#ce93d8"),
        ("E", "E: 11.0% (790GB liberi)", "#ce93d8"),
    ]
    app._aggiorna_dischi_ui(items_updated)
    assert app.disk_labels["D"].cget("fg") == "#ce93d8"


def test_gui_mode_toggle_and_clear_console(gui_app):
    app, root, _ = gui_app
    with patch("modules.tools.imposta_priorita_processo_corrente", return_value=True) as mock_prio:
        app._imposta_stato_modalita("gaming")
        assert "●" in app.btn_gaming.cget("text")
        assert app.btn_bilanciato.cget("text") == "Balance"
        assert app._telemetry_interval == 2.5
        mock_prio.assert_called_with(True)

        app._imposta_stato_modalita("bilanciato")
        assert "●" in app.btn_bilanciato.cget("text")
        assert app.btn_gaming.cget("text") == "Gaming Mode"
        assert app._telemetry_interval == 1
        mock_prio.assert_called_with(False)

    app.aggiungi_testo("Tu", "messaggio di prova")
    assert "messaggio di prova" in app.chat_area.get("1.0", tk.END)
    app.pulisci_console()
    assert app.chat_area.get("1.0", tk.END).strip() == ""


def test_gui_carica_info_hw_and_chiama_gemini(gui_app):
    app, root, _ = gui_app
    mock_agent = MagicMock()
    mock_agent.errore_init = "offline"
    mock_agent.invia.side_effect = lambda txt, on_retry=None: (on_retry("Retry msg") if on_retry else None) or "OK AI"

    with patch("modules.tools.info_versioni_sistema", return_value={"windows": "Win11", "driver_gpu": "621.40"}), \
         patch("modules.tools.piano_energetico_attivo", return_value={"modalita": "bilanciato"}), \
         patch("modules.tools.info_banchi_ram", return_value={
             "banchi": [{"slot_breve": "ChA-0", "gb": 8, "frequenza_mhz": 2133, "voltaggio": "1.20V", "part_number": "CMK"}],
             "frequenza_mhz": 2133, "tipo": "DDR4", "modalita_canale": "Dual Channel", "totale_gb": 8
         }), \
         patch("modules.agent_win11.GeminiAgent", return_value=mock_agent), \
         patch("modules.tools.stato_sicurezza_lhm", return_value={"attivo": True, "sicuro": False}):
        app._carica_info_hw()
        root.update()

    assert "Win11" in app.lbl_footer.cget("text")
    assert "ChA-0" in app.lbl_ram_banchi.cget("text")
    assert "porta 8085" in app.chat_area.get("1.0", tk.END)

    app._chiama_gemini("domanda")
    root.update()
    assert "OK AI" in app.chat_area.get("1.0", tk.END)


def test_gui_loop_telemetria_single_tick(gui_app):
    from types import SimpleNamespace
    app, root, _ = gui_app
    app.ram_info_hw = {"frequenza_mhz": 2133, "tipo": "DDR4", "modalita_canale": "Dual Channel"}

    wait_calls = {"n": 0}
    def fake_wait(timeout=None):
        wait_calls["n"] += 1
        if wait_calls["n"] > 1:
            raise KeyboardInterrupt()
        return False

    io_disk = {"PhysicalDrive0": SimpleNamespace(read_bytes=1024 * 1024, write_bytes=2 * 1024 * 1024)}
    io_net = {"Ethernet": SimpleNamespace(bytes_recv=100_000, bytes_sent=50_000)}
    fake_ram = SimpleNamespace(used=8 * 1024**3, total=24 * 1024**3, percent=33.3)
    fake_disk = SimpleNamespace(free=50 * 1024**3, percent=92.0)

    fake_info_dischi = {
        "C": {"drive": "PhysicalDrive0", "modello": "Samsung SSD 850 EVO 250GB", "tipo": "SSD", "bus": "SATA", "health_win": "Healthy"}
    }
    fake_lhm_ok = {
        "temperatura_c": "40 °C", "potenza_w": "20 W", "ventole_rpm": ["F1: 1500 RPM"],
        "dischi_lhm": {"samsung ssd 850 evo 250gb": {"temp_num": 41, "temperatura_c": "41°C", "life_percent": 89}},
    }

    with patch.object(app._telemetry_wake, "wait", side_effect=fake_wait), \
         patch("modules.tools.elenca_lettere_dischi", return_value=["C"]), \
         patch("modules.tools.mappa_info_dischi_fisici", return_value=fake_info_dischi), \
         patch("modules.tools.mappa_dischi_fisici", return_value={"C": "PhysicalDrive0"}), \
         patch("psutil.disk_io_counters", return_value=io_disk), \
         patch("psutil.net_io_counters", return_value=io_net), \
         patch("psutil.disk_usage", return_value=fake_disk), \
         patch("psutil.cpu_percent", return_value=22.0), \
         patch("psutil.virtual_memory", return_value=fake_ram), \
         patch("modules.tools.leggi_sensori_lhm", return_value=fake_lhm_ok), \
         patch("modules.tools.monitora_gpu", return_value={
             "gpu": "NVIDIA GeForce RTX 3070", "utilizzo_percent": "10%", "temperatura_c": "42°C",
             "temperatura_num": 42, "vram_usata_mb": "800", "vram_totale_mb": "8192",
             "consumo_watt": "28 W", "ventola_percent": "0%", "clock_mhz": "210 MHz"
         }), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Ethernet", "ip": "192.168.1.2", "link_mbps": 1000}), \
         patch("modules.tools.misura_ping", return_value={"stato": "12 ms"}), \
         patch("modules.tools.stato_ottimizzazioni_gaming", return_value={"testo_barra": "Gaming: OK", "colore": "#81c784"}):
        with pytest.raises(KeyboardInterrupt):
            app._loop_telemetria()
        root.update()

    assert "CPU: 22.0%" in app.lbl_cpu.cget("text")
    assert "RTX 3070" in app.lbl_gpu.cget("text")
    assert "Ping: 12 ms" in app.lbl_net.cget("text")
    assert "41°C" in app.disk_labels["C"].cget("text")
    assert "Good 89%" in app.disk_labels["C"].cget("text")
    assert app.disk_labels["C"].cget("fg") == "#ff5252"

    # Verifica che il ping resti attivo anche in Gaming Mode (intervallo 2.5s)
    wait_calls["n"] = 0
    app._telemetry_interval = 2.5
    with patch.object(app._telemetry_wake, "wait", side_effect=fake_wait), \
         patch("modules.tools.elenca_lettere_dischi", return_value=["C"]), \
         patch("modules.tools.mappa_info_dischi_fisici", return_value=fake_info_dischi), \
         patch("modules.tools.mappa_dischi_fisici", return_value={"C": "PhysicalDrive0"}), \
         patch("psutil.disk_io_counters", return_value=io_disk), \
         patch("psutil.net_io_counters", return_value=io_net), \
         patch("psutil.disk_usage", return_value=fake_disk), \
         patch("psutil.cpu_percent", return_value=22.0), \
         patch("psutil.virtual_memory", return_value=fake_ram), \
         patch("modules.tools.leggi_sensori_lhm", return_value={"temperatura_c": "40 °C", "potenza_w": "20 W", "ventole_rpm": [], "dischi_lhm": {}}), \
         patch("modules.tools.monitora_gpu", return_value={"errore": "N/D"}), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Ethernet", "ip": "192.168.1.2", "link_mbps": 1000}), \
         patch("modules.tools.misura_ping", return_value={"stato": "15 ms"}) as mock_ping, \
         patch("modules.tools.stato_ottimizzazioni_gaming", return_value={"testo_barra": "Gaming: OK", "colore": "#81c784"}):
        with pytest.raises(KeyboardInterrupt):
            app._loop_telemetria()
        root.update()
    mock_ping.assert_called_once()
    assert "Ping: 15 ms" in app.lbl_net.cget("text")


def test_gui_local_actions_and_chat_flow(gui_app):
    app, root, _ = gui_app

    with patch("modules.tools.analizza_sistema", return_value={
        "cpu_percent": 18.5, "ram_usata_gb": 8.0, "ram_totale_gb": 24.0, "ram_percent": 33.3,
        "top_processi_cpu": [{"name": "a.exe", "pid": 1, "cpu_percent": 10.0, "ram_mb": 50.0, "parent": "explorer.exe (500)"}],
        "top_processi_ram": [{"name": "b.exe", "pid": 2, "ram_mb": 200.0, "cpu_percent": 2.0, "parent": "services.exe (400)"}],
        "top_app_ram": [{"name": "b.exe", "istanze": 3, "ram_mb": 450.0, "cpu_percent": 4.5}],
    }):
        app.azione_stato_locale()
        root.update()
        txt_proc = app.chat_area.get("1.0", tk.END)
        assert "processi RAM" in txt_proc
        assert "explorer.exe (500)" in txt_proc
        assert "Totale aggregato per applicazione" in txt_proc

    with patch("modules.tools.monitora_archiviazione", return_value=[{"unita": "C:\\", "usati_gb": 200, "totali_gb": 220, "percent": 91.0, "liberi_gb": 20}]), \
         patch("modules.tools.stato_salute_dischi", return_value={"C": {"modello": "Samsung 850 EVO", "tipo": "SSD", "bus": "SATA", "etichetta": "Good 89%", "temperatura_c": "41°C", "power_on_hours": 29000, "data_written_gb": 44870.0}}), \
         patch("modules.tools.analizza_spazio_disco", return_value={"cartelle_analizzate": [{"cartella": "Temp", "mb": 50.0, "percorso": "C:\\Temp"}]}):
        app.azione_dischi_locale()
        root.update()
        txt_disk = app.chat_area.get("1.0", tk.END)
        assert "SPAZIO CRITICO" in txt_disk
        assert "Good 89%" in txt_disk
        assert "41°C" in txt_disk

    with patch("modules.tools.stato_ottimizzazioni_gaming", return_value={"testo_barra": "Gaming: FPS Cap 72 ●", "colore": "#81c784"}), \
         patch("modules.tools.attiva_modalita_prestazioni", return_value="Perf OK"), \
         patch("modules.tools.pulisci_file_temporanei", return_value="Temp OK"), \
         patch("modules.tools.diagnostica_pre_partita", return_value={"ok": True, "avvisi": [], "testo": "Check-up OK", "consiglia_dldsr": None, "dldsr_attivo": True, "risoluzioni_dldsr": ["3413x1440"]}), \
         patch("modules.tools.servizi_gaming_attivi", return_value=["WSearch"]), \
         patch("modules.tools._leggi_hags_attivo", return_value=False), \
         patch("modules.tools._leggi_physx_auto", return_value=False), \
         patch.object(app, "_chiedi_conferma_utente", return_value=True), \
         patch("modules.tools.pausa_servizi_gaming", return_value="Servizi in pausa OK"), \
         patch("modules.tools.abilita_hags", return_value="HAGS abilitato OK"):
        app.azione_gaming_locale()
        root.update()
        txt = app.chat_area.get("1.0", tk.END)
        assert "Perf OK" in txt
        assert "Check-up OK" in txt
        assert "Servizi in pausa OK" in txt
        assert "HAGS abilitato OK" in txt
        assert "DLDSR: ATTIVO ●" in txt
        assert "PhysX NVIDIA: GPU dedicata ●" in txt
        assert "FPS Cap 72 ●" in app.lbl_gaming_status.cget("text")

    # Feedback esplicito su scelta 'No' per Servizi, HAGS, DLDSR e PhysX
    with patch("modules.tools.stato_ottimizzazioni_gaming", return_value={"testo_barra": "Gaming: FPS Cap 72 ● | DLDSR: OFF ○", "colore": "#ffb74d"}), \
         patch("modules.tools.attiva_modalita_prestazioni", return_value="Perf OK"), \
         patch("modules.tools.pulisci_file_temporanei", return_value="Temp OK"), \
         patch("modules.tools.diagnostica_pre_partita", return_value={
             "ok": False, "avvisi": ["DLDSR"], "testo": "Check-up WARN",
             "consiglia_dldsr": {"nativa": "2560x1080", "res_178": "3413x1440", "res_225": "3840x1620"},
             "dldsr_attivo": False, "risoluzioni_dldsr": []
         }), \
         patch("modules.tools.servizi_gaming_attivi", return_value=["WSearch"]), \
         patch("modules.tools._leggi_hags_attivo", return_value=False), \
         patch("modules.tools._leggi_physx_auto", return_value=True), \
         patch.object(app, "_chiedi_conferma_utente", return_value=False):
        app.azione_gaming_locale()
        root.update()
        txt_no = app.chat_area.get("1.0", tk.END)
        assert "Servizi background lasciati attivi" in txt_no
        assert "HAGS lasciato disattivo" in txt_no
        assert "DLDSR lasciato disattivo" in txt_no
        assert "PhysX NVIDIA lasciato su 'Selezione automatica'" in txt_no

    with patch("modules.tools.stato_ottimizzazioni_gaming", return_value={"testo_barra": "Gaming: FPS Cap OFF ○", "colore": "#9e9e9e"}), \
         patch("modules.tools.ripristina_modalita_bilanciata", return_value="Bil OK"), \
         patch("modules.tools.ha_servizi_gaming_in_pausa", return_value=True), \
         patch("modules.tools.riavvia_servizi_gaming", return_value="Servizi riavviati OK"):
        app.azione_bilanciato_locale()
        root.update()
        txt = app.chat_area.get("1.0", tk.END)
        assert "Bil OK" in txt
        assert "Servizi riavviati OK" in txt
        assert "FPS Cap OFF ○" in app.lbl_gaming_status.cget("text")

    with patch("modules.tools.elenca_app_avvio", return_value={"utente_corrente": {"App1": "x"}, "sistema": {}}):
        app.azione_avvio_locale()
        root.update()
        assert "App1" in app.chat_area.get("1.0", tk.END)

    with patch("modules.tools.info_banchi_ram", return_value={
        "totale_gb": 16, "tipo": "DDR4", "frequenza_mhz": 3200, "modalita_canale": "Dual Channel",
        "banchi": [{"slot": "ChA-0", "bank": "B0", "gb": 8, "tipo": "DDR4", "frequenza_mhz": 3200, "voltaggio": "1.20V", "part_number": "XYZ"}]
    }):
        app.azione_ram_locale()
        root.update()
        assert "3200 MHz" in app.chat_area.get("1.0", tk.END)

    # Chat send: empty ignored
    app.invia_messaggio()
    assert str(app.send_btn.cget("state")) == "normal"

    # Chat send: valid message disables send_btn and _mostra_risposta re-enables it
    app.entry.insert(0, "ciao agent")
    with patch("threading.Thread"):
        app.invia_messaggio()
    assert str(app.send_btn.cget("state")) == "disabled"
    app._mostra_risposta("Risposta test")
    assert str(app.send_btn.cget("state")) == "normal"
    assert "Risposta test" in app.chat_area.get("1.0", tk.END)


def test_gui_chiedi_conferma_utente(gui_app):
    app, _, _ = gui_app
    with patch("modules.agent_win11.messagebox.askyesno", return_value=True) as m_yes:
        assert app._chiedi_conferma_utente("Confermi?") is True
        m_yes.assert_called_once()
    with patch("modules.agent_win11.messagebox.askyesno", return_value=False):
        assert app._chiedi_conferma_utente("Confermi?") is False


def test_gui_lock_lhm_button_and_action(gui_app):
    app, root, _ = gui_app
    app._aggiorna_stato_lhm_btn({"attivo": True, "sicuro": False})
    assert app.btn_lhm_lock.cget("text") == "Lock LHM !"

    app._aggiorna_stato_lhm_btn({"attivo": True, "sicuro": True})
    assert "Locked" in app.btn_lhm_lock.cget("text")

    with patch.object(app, "_chiedi_conferma_utente", return_value=False):
        app.azione_blocca_lhm_locale()
        root.update()
        assert "annullata" in app.chat_area.get("1.0", tk.END).lower()

    with patch.object(app, "_chiedi_conferma_utente", return_value=True), \
         patch("modules.tools.blocca_lhm_da_lan", return_value="Regola creata OK"), \
         patch("modules.tools.stato_sicurezza_lhm", return_value={"attivo": True, "sicuro": True}):
        app.azione_blocca_lhm_locale()
        root.update()
        assert "Regola creata OK" in app.chat_area.get("1.0", tk.END)
        assert "Locked" in app.btn_lhm_lock.cget("text")
