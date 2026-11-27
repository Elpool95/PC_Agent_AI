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

    expected = {"Top Process", "Storage", "Gaming Mode", "Balance", "Start App", "RAM Detail", "Clear", "Send"}
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
    app._imposta_stato_modalita("gaming")
    assert "●" in app.btn_gaming.cget("text")
    assert app.btn_bilanciato.cget("text") == "Balance"

    app._imposta_stato_modalita("bilanciato")
    assert "●" in app.btn_bilanciato.cget("text")
    assert app.btn_gaming.cget("text") == "Gaming Mode"

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
         patch("modules.agent_win11.GeminiAgent", return_value=mock_agent):
        app._carica_info_hw()
        root.update()

    assert "Win11" in app.lbl_footer.cget("text")
    assert "ChA-0" in app.lbl_ram_banchi.cget("text")

    app._chiama_gemini("domanda")
    root.update()
    assert "OK AI" in app.chat_area.get("1.0", tk.END)


def test_gui_loop_telemetria_single_tick(gui_app):
    from types import SimpleNamespace
    app, root, _ = gui_app
    app.ram_info_hw = {"frequenza_mhz": 2133, "tipo": "DDR4", "modalita_canale": "Dual Channel"}

    sleep_calls = {"n": 0}
    def fake_sleep(_sec):
        sleep_calls["n"] += 1
        if sleep_calls["n"] > 1:
            raise KeyboardInterrupt()

    io_disk = {"PhysicalDrive0": SimpleNamespace(read_bytes=1024 * 1024, write_bytes=2 * 1024 * 1024)}
    io_net = {"Ethernet": SimpleNamespace(bytes_recv=100_000, bytes_sent=50_000)}
    fake_ram = SimpleNamespace(used=8 * 1024**3, total=24 * 1024**3, percent=33.3)
    fake_disk = SimpleNamespace(free=50 * 1024**3, percent=92.0)

    with patch("time.sleep", side_effect=fake_sleep), \
         patch("modules.tools.elenca_lettere_dischi", return_value=["C"]), \
         patch("modules.tools.mappa_dischi_fisici", return_value={"C": "PhysicalDrive0"}), \
         patch("psutil.disk_io_counters", return_value=io_disk), \
         patch("psutil.net_io_counters", return_value=io_net), \
         patch("psutil.disk_usage", return_value=fake_disk), \
         patch("psutil.cpu_percent", return_value=22.0), \
         patch("psutil.virtual_memory", return_value=fake_ram), \
         patch("modules.tools.leggi_sensori_cpu", return_value={"temperatura_c": "40 °C", "potenza_w": "20 W", "ventole_rpm": ["F1: 1500 RPM"]}), \
         patch("modules.tools.monitora_gpu", return_value={
             "gpu": "NVIDIA GeForce RTX 3070", "utilizzo_percent": "10%", "temperatura_c": "42°C",
             "temperatura_num": 42, "vram_usata_mb": "800", "vram_totale_mb": "8192",
             "consumo_watt": "28 W", "ventola_percent": "0%", "clock_mhz": "210 MHz"
         }), \
         patch("modules.tools.info_rete_attiva", return_value={"nome": "Ethernet", "ip": "192.168.1.2", "link_mbps": 1000}), \
         patch("modules.tools.misura_ping", return_value={"stato": "12 ms"}):
        with pytest.raises(KeyboardInterrupt):
            app._loop_telemetria()
        root.update()

    assert "CPU: 22.0%" in app.lbl_cpu.cget("text")
    assert "RTX 3070" in app.lbl_gpu.cget("text")
    assert "Ping: 12 ms" in app.lbl_net.cget("text")
    assert app.disk_labels["C"].cget("fg") == "#ff5252"


def test_gui_local_actions_and_chat_flow(gui_app):
    app, root, _ = gui_app

    with patch("modules.tools.analizza_sistema", return_value={
        "top_processi_cpu": [{"name": "a.exe", "pid": 1, "cpu_percent": 10.0}],
        "top_processi_ram": [{"name": "b.exe", "pid": 2, "ram_mb": 200.0}],
    }):
        app.azione_stato_locale()
        root.update()
        assert "Top 5 processi RAM" in app.chat_area.get("1.0", tk.END)

    with patch("modules.tools.monitora_archiviazione", return_value=[{"unita": "C:\\", "usati_gb": 200, "totali_gb": 220, "percent": 91.0, "liberi_gb": 20}]), \
         patch("modules.tools.analizza_spazio_disco", return_value={"cartelle_analizzate": [{"cartella": "Temp", "mb": 50.0, "percorso": "C:\\Temp"}]}):
        app.azione_dischi_locale()
        root.update()
        assert "SPAZIO CRITICO" in app.chat_area.get("1.0", tk.END)

    with patch("modules.tools.attiva_modalita_prestazioni", return_value="Perf OK"), \
         patch("modules.tools.pulisci_file_temporanei", return_value="Temp OK"):
        app.azione_gaming_locale()
        root.update()
        assert "Perf OK" in app.chat_area.get("1.0", tk.END)

    with patch("modules.tools.ripristina_modalita_bilanciata", return_value="Bil OK"):
        app.azione_bilanciato_locale()
        root.update()
        assert "Bil OK" in app.chat_area.get("1.0", tk.END)

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
