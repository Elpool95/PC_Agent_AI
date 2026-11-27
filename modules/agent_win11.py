# Copyright (c) 2026 Elpool95
# SPDX-License-Identifier: MIT

import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext
import psutil
from config import settings as config
from modules import tools
from modules.ai_agent import GeminiAgent

class PCAgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PC Agent AI — Windows Monitor & Optimizer")
        self.root.geometry("900x760")
        self.root.minsize(820, 620)
        self.root.configure(bg="#1e1e1e")
        icon_path = os.path.join(config.BASE_DIR, "doc", "assets", "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.agent = None

        # --- BARRA TELEMETRIA IN TEMPO REALE ---
        tele_frame = tk.Frame(root, bg="#141414", bd=1, relief=tk.SOLID)
        tele_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        row1 = tk.Frame(tele_frame, bg="#141414")
        row1.pack(fill=tk.X, padx=8, pady=(6, 2))

        self.lbl_cpu = tk.Label(row1, text="CPU: --% | -- °C | -- W", bg="#141414", fg="#81c784", font=("Consolas", 10, "bold"))
        self.lbl_cpu.pack(side=tk.LEFT, padx=4)

        row_ram_main = tk.Frame(tele_frame, bg="#141414")
        row_ram_main.pack(fill=tk.X, padx=8, pady=2)

        self.lbl_ram = tk.Label(row_ram_main, text="RAM: --/-- GB (--%)", bg="#141414", fg="#4fc3f7", font=("Consolas", 10, "bold"))
        self.lbl_ram.pack(side=tk.LEFT, padx=4)

        row_ram = tk.Frame(tele_frame, bg="#141414")
        row_ram.pack(fill=tk.X, padx=8, pady=(0, 2))

        self.lbl_ram_banchi = tk.Label(
            row_ram, text="Banchi RAM: rilevamento in corso...", bg="#141414", fg="#80deea",
            font=("Consolas", 9), justify=tk.LEFT, anchor="w"
        )
        self.lbl_ram_banchi.pack(side=tk.LEFT, fill=tk.X, padx=4)

        row2 = tk.Frame(tele_frame, bg="#141414")
        row2.pack(fill=tk.X, padx=8, pady=2)

        self.disk_frame = row2
        self.disk_labels = {}
        self.lbl_disk_placeholder = tk.Label(
            row2, text="Dischi: rilevamento in corso...", bg="#141414", fg="#ce93d8",
            font=("Consolas", 10, "bold"), justify=tk.LEFT, anchor="w"
        )
        self.lbl_disk_placeholder.grid(row=0, column=0, sticky="w", padx=4)

        row3 = tk.Frame(tele_frame, bg="#141414")
        row3.pack(fill=tk.X, padx=8, pady=2)

        self.lbl_gpu = tk.Label(row3, text="GPU: --% | --°C | VRAM: --/-- MB | -- W", bg="#141414", fg="#ffb74d", font=("Consolas", 10, "bold"))
        self.lbl_gpu.pack(side=tk.LEFT, padx=4)

        row4 = tk.Frame(tele_frame, bg="#141414")
        row4.pack(fill=tk.X, padx=8, pady=(2, 2))

        self.lbl_net = tk.Label(row4, text="Rete: rilevamento in corso...", bg="#141414", fg="#4db6ac", font=("Consolas", 10, "bold"))
        self.lbl_net.pack(side=tk.LEFT, padx=4)

        row5 = tk.Frame(tele_frame, bg="#141414")
        row5.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.lbl_gaming_status = tk.Label(
            row5, text="Gaming: rilevamento stato...", bg="#141414", fg="#9e9e9e",
            font=("Consolas", 9, "bold"), anchor="w"
        )
        self.lbl_gaming_status.pack(side=tk.LEFT, padx=4)

        # --- PULSANTI RAPIDI LOCALI ---
        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        tk.Button(
            btn_frame, text="Top Process", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_stato_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Storage", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_dischi_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        self.btn_gaming = tk.Button(
            btn_frame, text="Gaming Mode", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_gaming_locale, daemon=True).start()
        )
        self.btn_gaming.pack(side=tk.LEFT, padx=4)

        self.btn_bilanciato = tk.Button(
            btn_frame, text="Balance", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_bilanciato_locale, daemon=True).start()
        )
        self.btn_bilanciato.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Start App", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_avvio_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="RAM Detail", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_ram_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        self.btn_lhm_lock = tk.Button(
            btn_frame, text="Lock LHM", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_blocca_lhm_locale, daemon=True).start()
        )
        self.btn_lhm_lock.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Clear", bg="#3a2626", fg="#ffffff",
            activebackground="#5a3434", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=self.pulisci_console
        ).pack(side=tk.RIGHT, padx=4)

        # --- BARRA INFERIORE VERSIONI SISTEMA (ancorata in basso) ---
        footer_frame = tk.Frame(root, bg="#141414", bd=1, relief=tk.SOLID)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(2, 8))

        self.lbl_footer = tk.Label(
            footer_frame, text="Rilevamento versione Windows 11 e driver grafico...",
            bg="#141414", fg="#9e9e9e", font=("Consolas", 9), anchor="w"
        )
        self.lbl_footer.pack(fill=tk.X, padx=8, pady=4)

        # --- BARRA DI INPUT (ancorata sopra il footer) ---
        input_frame = tk.Frame(root, bg="#1e1e1e")
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 4))

        self.entry = tk.Entry(
            input_frame, bg="#2d2d30", fg="#ffffff", insertbackground="#ffffff",
            font=("Segoe UI", 10), relief=tk.FLAT
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.invia_messaggio())

        self.send_btn = tk.Button(
            input_frame, text="Send", bg="#007acc", fg="#ffffff",
            activebackground="#005a9e", activeforeground="#ffffff",
            relief=tk.FLAT, padx=16, pady=6, command=self.invia_messaggio
        )
        self.send_btn.pack(side=tk.RIGHT)

        # --- AREA CHAT ---
        self.chat_area = scrolledtext.ScrolledText(
            root, height=10, wrap=tk.WORD, bg="#252526", fg="#e0e0e0",
            font=("Segoe UI", 10), state=tk.DISABLED, relief=tk.FLAT, padx=10, pady=10
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_area.tag_config("utente", foreground="#4fc3f7", font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("agent", foreground="#81c784", font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("locale", foreground="#ffb74d", font=("Segoe UI", 10, "bold"))

        self.aggiungi_testo("Agent", "Pronto. Telemetria live attiva: CPU (Temp + W), RAM, tutti i dischi, GPU e Rete.\n")

        self.ram_info_hw = {"banchi": [], "frequenza_mhz": 0, "tipo": "RAM", "modalita_canale": "", "totale_gb": 0}
        self.dischi_info_hw = {}
        self._telemetry_interval = config.TELEMETRY_INTERVAL_NORMAL
        self._telemetry_wake = threading.Event()
        self._window_minimized = False

        self.root.bind("<Unmap>", self._on_window_state_change)
        self.root.bind("<Map>", self._on_window_state_change)

        psutil.cpu_percent(interval=None)
        threading.Thread(target=self._carica_info_hw, daemon=True).start()
        threading.Thread(target=self._loop_telemetria, daemon=True).start()

    def _on_window_state_change(self, _event=None):
        """Sospende il polling telemetria quando la finestra è minimizzata e lo riattiva subito al ripristino."""
        try:
            minimized = self.root.state() == "iconic"
        except Exception:
            minimized = False
        if minimized != self._window_minimized:
            self._window_minimized = minimized
            if not minimized:
                self._telemetry_wake.set()

    def _carica_info_hw(self):
        info = tools.info_versioni_sistema()
        testo_footer = f"OS: {info['windows']}   |   Driver Grafico NVIDIA: {info['driver_gpu']}"
        self.root.after(0, lambda: self.lbl_footer.config(text=testo_footer))

        piano = tools.piano_energetico_attivo()
        if piano["modalita"] in ("gaming", "bilanciato"):
            self.root.after(0, self._imposta_stato_modalita, piano["modalita"])

        ram_hw = tools.info_banchi_ram()
        self.ram_info_hw = ram_hw
        banchi = ram_hw.get("banchi", [])
        if banchi:
            voci = []
            for b in banchi:
                part = f" ({b['part_number']})" if b["part_number"] else ""
                voci.append(f"{b['slot_breve']}: {b['gb']}GB {b['frequenza_mhz']}MHz {b['voltaggio']}{part}")
            righe = ["  |  ".join(voci[i:i + 2]) for i in range(0, len(voci), 2)]
            testo_banchi = "\n".join(righe)
        else:
            testo_banchi = "Banchi RAM: N/D"
        self.root.after(0, lambda: self.lbl_ram_banchi.config(text=testo_banchi))

        self.agent = GeminiAgent(confirm_callback=self._chiedi_conferma_utente)
        if self.agent.errore_init:
            err = self.agent.errore_init
            self.root.after(0, self.aggiungi_testo, "Sistema", f"Avviso Agent AI offline ({err}). La telemetria locale resta attiva.\n")

        lhm_sec = tools.stato_sicurezza_lhm()
        self.root.after(0, self._aggiorna_stato_lhm_btn, lhm_sec)
        if lhm_sec["attivo"] and not lhm_sec["sicuro"]:
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                "Avviso sicurezza: LibreHardwareMonitor (porta 8085) è esposto sulla LAN. "
                "Clicca il pulsante 'Lock LHM' per proteggerlo via Windows Firewall.\n"
            )

        self._aggiorna_barra_gaming_async()

    def _aggiorna_barra_gaming_async(self):
        """Aggiorna la riga di stato Gaming (FPS Cap, Servizi BG, HAGS, DLDSR) in modo non bloccante."""
        stato_g = tools.stato_ottimizzazioni_gaming()
        self.root.after(0, self._aggiorna_stato_gaming_ui, stato_g["testo_barra"], stato_g["colore"])

    def _aggiorna_stato_gaming_ui(self, testo: str, colore: str):
        self.lbl_gaming_status.config(text=testo, fg=colore)

    def _aggiorna_stato_lhm_btn(self, lhm_sec: dict):
        if lhm_sec.get("sicuro"):
            self.btn_lhm_lock.config(text="LHM Locked ●", bg="#2e7d32", activebackground="#388e3c")
        elif lhm_sec.get("attivo"):
            self.btn_lhm_lock.config(text="Lock LHM !", bg="#8c5a00", activebackground="#a86d00")
        else:
            self.btn_lhm_lock.config(text="Lock LHM", bg="#2d2d30", activebackground="#3e3e42")

    def _chiedi_conferma_utente(self, messaggio: str) -> bool:
        """Mostra un popup nativo sul thread GUI per confermare azioni sensibili richieste dall'AI."""
        if threading.current_thread() is threading.main_thread():
            return messagebox.askyesno("Conferma azione — PC Agent AI", messaggio, parent=self.root)
        risultato = {"ok": False}
        done = threading.Event()

        def _apri_dialog():
            try:
                risultato["ok"] = messagebox.askyesno("Conferma azione — PC Agent AI", messaggio, parent=self.root)
            finally:
                done.set()

        self.root.after(0, _apri_dialog)
        done.wait()
        return risultato["ok"]

    def _imposta_stato_modalita(self, modalita):
        if modalita == "gaming":
            self.btn_gaming.config(text="Gaming Mode ●", bg="#2e7d32", activebackground="#388e3c")
            self.btn_bilanciato.config(text="Balance", bg="#2d2d30", activebackground="#3e3e42")
            self._telemetry_interval = config.TELEMETRY_INTERVAL_GAMING
            tools.imposta_priorita_processo_corrente(True)
            self._telemetry_wake.set()
        elif modalita == "bilanciato":
            self.btn_gaming.config(text="Gaming Mode", bg="#2d2d30", activebackground="#3e3e42")
            self.btn_bilanciato.config(text="Balance ●", bg="#0277bd", activebackground="#0288d1")
            self._telemetry_interval = config.TELEMETRY_INTERVAL_NORMAL
            tools.imposta_priorita_processo_corrente(False)
            self._telemetry_wake.set()

    def _loop_telemetria(self):
        lettere_correnti = tools.elenca_lettere_dischi()
        mappa_info = tools.mappa_info_dischi_fisici()
        self.dischi_info_hw = mappa_info
        mappa_dischi = {k: v["drive"] for k, v in mappa_info.items() if v.get("drive")} or tools.mappa_dischi_fisici()
        prev_io = psutil.disk_io_counters(perdisk=True)
        prev_net = psutil.net_io_counters(pernic=True)
        prev_time = time.time()
        ultimo_ping = "-- ms"
        ciclo = 0

        while True:
            self._telemetry_wake.wait(timeout=self._telemetry_interval)
            self._telemetry_wake.clear()
            if self._window_minimized:
                continue
            ciclo += 1
            try:
                now = time.time()
                dt = max(now - prev_time, 0.1)
                curr_io = psutil.disk_io_counters(perdisk=True)
                curr_net = psutil.net_io_counters(pernic=True)

                nuove_lettere = tools.elenca_lettere_dischi()
                if nuove_lettere != lettere_correnti:
                    lettere_correnti = nuove_lettere
                    mappa_info = tools.mappa_info_dischi_fisici()
                    self.dischi_info_hw = mappa_info
                    mappa_dischi = {k: v["drive"] for k, v in mappa_info.items() if v.get("drive")} or tools.mappa_dischi_fisici()

                cpu = psutil.cpu_percent(interval=None)
                sensori_lhm = tools.leggi_sensori_lhm()
                cpu_temp = sensori_lhm["temperatura_c"]
                cpu_watt = sensori_lhm["potenza_w"]
                ventole = sensori_lhm["ventole_rpm"]
                ventole_str = f"  |  {' '.join(ventole[:3])}" if ventole else ""
                salute_dischi = tools.stato_salute_dischi(mappa_info, sensori_lhm.get("dischi_lhm", {}))

                dischi_items = []
                for lettera in lettere_correnti:
                    salute = salute_dischi.get(lettera, {})
                    stato_h = salute.get("stato", "Unknown")
                    temp_str = salute.get("temperatura_c", "N/D")
                    health_tag = salute.get("etichetta_breve", "")
                    try:
                        uso = psutil.disk_usage(f"{lettera}:\\")
                        liberi = round(uso.free / (1024**3), 0)
                        avviso = " [!]" if uso.percent >= config.DISK_CRIT else ""
                        info = f"{lettera}: {uso.percent}%{avviso} ({int(liberi)}GB)"
                        if temp_str and temp_str != "N/D":
                            t_warn = " [!]" if salute.get("temp_alta") else ""
                            info += f" | {temp_str}{t_warn}"
                        if health_tag and health_tag != "Unknown":
                            info += f" | {health_tag}"
                        if uso.percent >= config.DISK_CRIT or stato_h == "Bad":
                            colore = "#ff5252"
                        elif uso.percent >= config.DISK_WARN or stato_h == "Caution":
                            colore = "#ffb74d"
                        else:
                            colore = "#ce93d8"
                    except Exception:
                        info = f"{lettera}: N/D"
                        colore = "#ce93d8"

                    drive_fisico = mappa_dischi.get(lettera)
                    if drive_fisico and drive_fisico in curr_io and drive_fisico in prev_io:
                        r_mb = round((curr_io[drive_fisico].read_bytes - prev_io[drive_fisico].read_bytes) / dt / (1024 * 1024), 1)
                        w_mb = round((curr_io[drive_fisico].write_bytes - prev_io[drive_fisico].write_bytes) / dt / (1024 * 1024), 1)
                        info += f" | R {r_mb}/W {w_mb} MB/s"
                    dischi_items.append((lettera, info, colore))

                prev_io, prev_time = curr_io, now

                ram = psutil.virtual_memory()
                ram_used = round(ram.used / (1024**3), 1)
                ram_tot = round(ram.total / (1024**3), 1)

                gpu = tools.monitora_gpu()

                cpu_color = "#ff5252" if cpu >= config.CPU_CRIT else ("#ffb74d" if cpu >= config.CPU_WARN else "#81c784")
                ram_color = "#ff5252" if ram.percent >= config.RAM_CRIT else "#4fc3f7"

                if "errore" in gpu:
                    gpu_text = f"GPU N/D ({gpu['errore'][:45]})"
                    gpu_color = "#ff5252"
                else:
                    temp_num = gpu["temperatura_num"]
                    gpu_nome = gpu["gpu"].replace("NVIDIA GeForce ", "").strip()
                    gpu_text = (
                        f"{gpu_nome}: {gpu['utilizzo_percent']} | {gpu['temperatura_c']} | "
                        f"VRAM: {gpu['vram_usata_mb']}/{gpu['vram_totale_mb']} MB | "
                        f"{gpu['consumo_watt']} | Fan: {gpu['ventola_percent']} | {gpu['clock_mhz']}"
                    )
                    gpu_color = "#ff5252" if temp_num >= config.GPU_TEMP_CRIT else ("#ffb74d" if temp_num >= config.GPU_TEMP_WARN else "#81c784")

                rete = tools.info_rete_attiva()
                nome_nic = rete["nome"]
                if nome_nic == "Offline":
                    net_text = "Rete: Offline"
                    net_color = "#ff5252"
                else:
                    if ciclo == 1 or ciclo % 3 == 0:
                        ultimo_ping = tools.misura_ping()["stato"]
                    if nome_nic in curr_net and nome_nic in prev_net:
                        dl_bs = (curr_net[nome_nic].bytes_recv - prev_net[nome_nic].bytes_recv) / dt
                        ul_bs = (curr_net[nome_nic].bytes_sent - prev_net[nome_nic].bytes_sent) / dt
                    else:
                        dl_bs = 0.0
                        ul_bs = 0.0
                    link_str = f" {rete['link_mbps']} Mbps" if rete["link_mbps"] else ""
                    dl_str = tools.formatta_velocita_rete(dl_bs)
                    ul_str = tools.formatta_velocita_rete(ul_bs)
                    net_text = f"Rete ({nome_nic}{link_str} | {rete['ip']}): ↓ {dl_str} | ↑ {ul_str} | Ping: {ultimo_ping}"
                    net_color = "#4db6ac"
                prev_net = curr_net

                ram_extra = ""
                if self.ram_info_hw.get("frequenza_mhz"):
                    ram_extra = f" | {self.ram_info_hw['tipo']} {self.ram_info_hw['frequenza_mhz']} MHz ({self.ram_info_hw['modalita_canale']})"

                self.root.after(
                    0, self._aggiorna_barra,
                    f"CPU: {cpu}% | {cpu_temp} | {cpu_watt}{ventole_str}", cpu_color,
                    f"RAM: {ram_used}/{ram_tot} GB ({ram.percent}%){ram_extra}", ram_color,
                    dischi_items,
                    gpu_text, gpu_color,
                    net_text, net_color
                )
                if ciclo == 1 or ciclo % 5 == 0:
                    stato_g = tools.stato_ottimizzazioni_gaming()
                    self.root.after(0, self._aggiorna_stato_gaming_ui, stato_g["testo_barra"], stato_g["colore"])
            except Exception:
                pass

    def _aggiorna_barra(self, cpu_txt, cpu_col, ram_txt, ram_col, dischi_items, gpu_txt, gpu_col, net_txt, net_col):
        self.lbl_cpu.config(text=cpu_txt, fg=cpu_col)
        self.lbl_ram.config(text=ram_txt, fg=ram_col)
        self._aggiorna_dischi_ui(dischi_items)
        self.lbl_gpu.config(text=gpu_txt, fg=gpu_col)
        self.lbl_net.config(text=net_txt, fg=net_col)

    def _aggiorna_dischi_ui(self, dischi_items):
        if self.lbl_disk_placeholder is not None:
            self.lbl_disk_placeholder.destroy()
            self.lbl_disk_placeholder = None

        lettere_nuove = [item[0] for item in dischi_items]
        if lettere_nuove != list(self.disk_labels.keys()):
            for lbl in self.disk_labels.values():
                lbl.destroy()
            self.disk_labels = {}
            for idx, (lettera, testo, colore) in enumerate(dischi_items):
                r, c = divmod(idx, 2)
                lbl = tk.Label(
                    self.disk_frame, text=testo, bg="#141414", fg=colore,
                    font=("Consolas", 10, "bold"), anchor="w"
                )
                lbl.grid(row=r, column=c, sticky="w", padx=(4, 24))
                self.disk_labels[lettera] = lbl
        else:
            for lettera, testo, colore in dischi_items:
                self.disk_labels[lettera].config(text=testo, fg=colore)

    def aggiungi_testo(self, mittente, testo):
        self.chat_area.config(state=tk.NORMAL)
        tag = "utente" if mittente == "Tu" else ("locale" if mittente == "Sistema" else "agent")
        self.chat_area.insert(tk.END, f"{mittente}: ", tag)
        self.chat_area.insert(tk.END, f"{testo}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def pulisci_console(self):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.config(state=tk.DISABLED)

    # --- AZIONI LOCALI ---

    def azione_stato_locale(self):
        sys_info = tools.analizza_sistema(limite=10)
        righe = [
            f"Stato istantaneo — CPU: {sys_info.get('cpu_percent', 0)}% | "
            f"RAM: {sys_info.get('ram_usata_gb', 0)}/{sys_info.get('ram_totale_gb', 0)} GB ({sys_info.get('ram_percent', 0)}%)",
            f"Top {len(sys_info['top_processi_cpu'])} processi CPU (con processo padre):"
        ]
        for p in sys_info['top_processi_cpu']:
            padre = f"  ← {p['parent']}" if p.get('parent') else ""
            ram_s = f" | {p['ram_mb']} MB" if 'ram_mb' in p else ""
            righe.append(f"  - {p['name']} (PID {p['pid']}): {p['cpu_percent']}%{ram_s}{padre}")

        righe.append(f"Top {len(sys_info['top_processi_ram'])} processi RAM (con processo padre):")
        for p in sys_info['top_processi_ram']:
            padre = f"  ← {p['parent']}" if p.get('parent') else ""
            cpu_s = f" | CPU {p['cpu_percent']}%" if 'cpu_percent' in p else ""
            righe.append(f"  - {p['name']} (PID {p['pid']}): {p['ram_mb']} MB{cpu_s}{padre}")

        if sys_info.get('top_app_ram'):
            righe.append("Totale aggregato per applicazione (Top 5 RAM):")
            for a in sys_info['top_app_ram']:
                righe.append(f"  - {a['name']} ({a['istanze']} proc.): {a['ram_mb']} MB | CPU {a['cpu_percent']}%")

        righe.append("")
        self.root.after(0, self.aggiungi_testo, "Sistema", "\n".join(righe))

    def azione_dischi_locale(self):
        dischi = tools.monitora_archiviazione()
        salute_map = tools.stato_salute_dischi(self.dischi_info_hw or None)
        righe = ["Stato partizioni, salute S.M.A.R.T. e temperature:"]
        for d in dischi:
            lettera = str(d["unita"])[0].upper() if d.get("unita") else ""
            s = salute_map.get(lettera, {})
            avviso = "  [SPAZIO CRITICO]" if d['percent'] >= config.DISK_CRIT else ""
            mod_str = f" [{s['modello']} | {s['tipo']} {s['bus']}]" if s.get("modello") else ""
            righe.append(
                f"  - {d['unita']}{mod_str}  Usati: {d['usati_gb']}/{d['totali_gb']} GB ({d['percent']}%) | Liberi: {d['liberi_gb']} GB{avviso}"
            )
            if s:
                dettagli = [f"Salute: {s.get('etichetta', 'N/D')}", f"Temp: {s.get('temperatura_c', 'N/D')}"]
                if s.get("power_on_hours") is not None:
                    dettagli.append(f"Ore: {s['power_on_hours']} h")
                if s.get("data_written_gb") is not None:
                    gb_w = s["data_written_gb"]
                    dettagli.append(f"Scritture: {gb_w / 1024:.1f} TB" if gb_w >= 1024 else f"Scritture: {gb_w:.0f} GB")
                righe.append("    " + " | ".join(dettagli))
        analisi_c = tools.analizza_spazio_disco("C:")
        if analisi_c["cartelle_analizzate"]:
            righe.append("Principali cartelle/cache su C::")
            for c in analisi_c["cartelle_analizzate"]:
                righe.append(f"  - {c['cartella']}: {c['mb']} MB ({c['percorso']})")
        righe.append("")
        self.root.after(0, self.aggiungi_testo, "Sistema", "\n".join(righe))

    def azione_gaming_locale(self):
        res_perf = tools.attiva_modalita_prestazioni()
        res_temp = tools.pulisci_file_temporanei()
        checkup = tools.diagnostica_pre_partita(self.ram_info_hw, self.dischi_info_hw or None)
        self.root.after(0, self._imposta_stato_modalita, "gaming")
        self.root.after(0, self.aggiungi_testo, "Sistema", f"{res_perf}\n{res_temp}\n{checkup['testo']}\n")

        attivi = tools.servizi_gaming_attivi()
        hdd_list = checkup.get("hdd_rilevati") or []
        hdd_note = (
            f"Rilevato disco meccanico HDD ({', '.join(f'{l}:' for l in hdd_list)}) con Windows Search attivo: "
            "arrestare WSearch riduce drasticamente i picchi di disco e CPU.\n\n"
            if (hdd_list and "WSearch" in attivi) else ""
        )
        if not attivi:
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                f"Servizi background ({', '.join(config.GAMING_PAUSABLE_SERVICES)}): già tutti in pausa ●.\n"
            )
        elif self._chiedi_conferma_utente(
            f"{hdd_note}Vuoi mettere in pausa temporaneamente i servizi background di Windows ({', '.join(attivi)}) "
            "per ridurre picchi disco e micro-stutter?\n\nRichiederà conferma UAC e verranno riavviati su 'Balance'."
        ):
            res_svc = tools.pausa_servizi_gaming(attivi)
            self.root.after(0, self.aggiungi_testo, "Sistema", f"{res_svc}\n")
        else:
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                f"Servizi background lasciati attivi su scelta utente ({', '.join(attivi)}) ○.\n"
            )

        hags_stato = tools._leggi_hags_attivo()
        if hags_stato is False:
            if self._chiedi_conferma_utente(
                "HAGS (Pianificazione GPU con accelerazione hardware) è attualmente spento.\n\n"
                "Vuoi abilitarlo automaticamente ora (richiederà conferma UAC e un riavvio del PC)?"
            ):
                res_hags = tools.abilita_hags()
                self.root.after(0, self.aggiungi_testo, "Sistema", f"{res_hags}\n")
            else:
                self.root.after(
                    0, self.aggiungi_testo, "Sistema",
                    "HAGS lasciato disattivo su scelta utente ○.\n"
                )

        dldsr_tip = checkup.get("consiglia_dldsr")
        if dldsr_tip:
            if self._chiedi_conferma_utente(
                f"Sistema CPU-bound rilevato su {dldsr_tip['nativa']}: attivare DLDSR 1.78x ({dldsr_tip['res_178']}) "
                f"o 2.25x ({dldsr_tip['res_225']}) e alzare la qualità grafica sposta carico sulla GPU RTX e riduce lo stutter.\n\n"
                "Vuoi aprire ora il Pannello di Controllo NVIDIA (Gestisci impostazioni 3D > Fattori DSR) per abilitarlo?"
            ):
                if tools.apri_pannello_nvidia():
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Pannello di Controllo NVIDIA aperto: vai su 'Gestisci impostazioni 3D' > 'Fattori DSR' "
                        f"e spunta 1.78x DL ({dldsr_tip['res_178']}) e/o 2.25x DL ({dldsr_tip['res_225']}), poi seleziona la risoluzione nei giochi. "
                        "Appena applichi, la barra Gaming mostrerà 'DLDSR: ON ●'.\n"
                    )
                else:
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Impossibile aprire automaticamente il Pannello di Controllo NVIDIA: aprilo dal menu Start > 'Gestisci impostazioni 3D' > 'Fattori DSR'.\n"
                    )
            else:
                self.root.after(
                    0, self.aggiungi_testo, "Sistema",
                    f"DLDSR lasciato disattivo su scelta utente (risoluzione nativa {dldsr_tip['nativa']} mantenuta) ○.\n"
                )
        elif checkup.get("dldsr_attivo"):
            res_list = ", ".join(checkup.get("risoluzioni_dldsr", []))
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                f"DLDSR: ATTIVO ● (risoluzioni disponibili: {res_list}).\n"
            )

        physx_auto = tools._leggi_physx_auto()
        if physx_auto is False:
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                "PhysX NVIDIA: GPU dedicata ●.\n"
            )
        elif physx_auto is True:
            if not dldsr_tip and self._chiedi_conferma_utente(
                "PhysX NVIDIA è attualmente su 'Selezione automatica'.\n"
                "Impostare la GPU dedicata evita che alcuni giochi scarichino la fisica sulla CPU.\n\n"
                "Vuoi aprire ora il Pannello di Controllo NVIDIA (Configura Surround, PhysX)?"
            ):
                if tools.apri_pannello_nvidia():
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Pannello di Controllo NVIDIA aperto: vai su 'Configura Surround, PhysX' "
                        "e seleziona la tua GPU NVIDIA dedicata, poi clicca Applica. "
                        "Appena applicato, la barra Gaming mostrerà 'PhysX: GPU ●'.\n"
                    )
                else:
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Impossibile aprire automaticamente il Pannello di Controllo NVIDIA: aprilo dal menu Start > 'Configura Surround, PhysX'.\n"
                    )
            else:
                self.root.after(
                    0, self.aggiungi_testo, "Sistema",
                    "PhysX NVIDIA lasciato su 'Selezione automatica' ○.\n"
                )

        vbs_attivo = checkup.get("vbs_hvci_attivo")
        if vbs_attivo is True:
            self.root.after(
                0, self.aggiungi_testo, "Sistema",
                "VBS / Integrità della memoria (Isolamento core): ON ● (richiesto per anti-cheat e protezione sistema).\n"
            )
        elif vbs_attivo is False:
            if self._chiedi_conferma_utente(
                "VBS / Integrità della memoria (Isolamento core) risulta attualmente disattivo.\n\n"
                "Mantenerlo attivo è necessario per gli anti-cheat moderni (es. Riot Vanguard) "
                "e aiuta a proteggere il sistema da accessi non autorizzati (richiede riavvio).\n\n"
                "Vuoi aprire ora Sicurezza di Windows > Isolamento core per attivarlo?"
            ):
                if tools.apri_isolamento_core_windows():
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Sicurezza di Windows > Isolamento core aperto: attiva 'Integrità della memoria' "
                        "e riavvia il PC per garantire compatibilità anti-cheat e sicurezza.\n"
                    )
                else:
                    self.root.after(
                        0, self.aggiungi_testo, "Sistema",
                        "Impossibile aprire automaticamente Isolamento core: vai in Sicurezza di Windows > "
                        "Sicurezza dispositivi > Isolamento core.\n"
                    )
            else:
                self.root.after(
                    0, self.aggiungi_testo, "Sistema",
                    "VBS / Integrità della memoria (Isolamento core) lasciato disattivo su scelta utente ○.\n"
                )

        self._aggiorna_barra_gaming_async()

    def azione_bilanciato_locale(self):
        res = tools.ripristina_modalita_bilanciata()
        res_svc = tools.riavvia_servizi_gaming() if tools.ha_servizi_gaming_in_pausa() else ""
        self.root.after(0, self._imposta_stato_modalita, "bilanciato")
        testo = f"{res}\n{res_svc}\n" if res_svc else f"{res}\n"
        self.root.after(0, self.aggiungi_testo, "Sistema", testo)
        self._aggiorna_barra_gaming_async()

    def azione_avvio_locale(self):
        apps = tools.elenca_app_avvio()
        righe = ["App all'avvio (Utente corrente):"]
        righe.extend([f"  - {k}" for k in apps["utente_corrente"]] or ["  Nessuna"])
        righe.append("App all'avvio (Sistema):")
        righe.extend([f"  - {k}" for k in apps["sistema"]] or ["  Nessuna"])
        righe.append("")
        self.root.after(0, self.aggiungi_testo, "Sistema", "\n".join(righe))

    def azione_ram_locale(self):
        ram_hw = tools.info_banchi_ram()
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        righe = [
            f"Configurazione RAM: {ram_hw['totale_gb']} GB {ram_hw['tipo']} @ {ram_hw['frequenza_mhz']} MHz ({ram_hw['modalita_canale']})",
            f"Utilizzo attuale: {round(ram.used / (1024**3), 2)} / {round(ram.total / (1024**3), 2)} GB ({ram.percent}%) | Disponibile: {round(ram.available / (1024**3), 2)} GB",
            f"Memoria virtuale (Paging): {round(swap.used / (1024**3), 2)} / {round(swap.total / (1024**3), 2)} GB ({swap.percent}%)",
            "Dettaglio banchi fisici:"
        ]
        for b in ram_hw["banchi"]:
            righe.append(
                f"  - {b['slot']} ({b['bank']}): {b['gb']} GB {b['tipo']} @ {b['frequenza_mhz']} MHz | {b['voltaggio']} | Modello: {b['part_number'] or 'N/D'}"
            )
        righe.append("")
        self.root.after(0, self.aggiungi_testo, "Sistema", "\n".join(righe))

    def azione_blocca_lhm_locale(self):
        if not self._chiedi_conferma_utente(
            "Creare una regola Windows Firewall (richiederà UAC) per bloccare l'accesso esterno (LAN) "
            "alla porta 8085 di LibreHardwareMonitor?\n\nPC Agent AI continuerà a funzionare normalmente su localhost."
        ):
            self.root.after(0, self.aggiungi_testo, "Sistema", "Operazione annullata.\n")
            return
        res = tools.blocca_lhm_da_lan()
        lhm_sec = tools.stato_sicurezza_lhm()
        self.root.after(0, self._aggiorna_stato_lhm_btn, lhm_sec)
        self.root.after(0, self.aggiungi_testo, "Sistema", f"{res}\n")

    # --- CHAT AI ---

    def invia_messaggio(self):
        testo = self.entry.get().strip()
        if not testo:
            return
        self.entry.delete(0, tk.END)

        self.aggiungi_testo("Tu", testo)
        self.aggiungi_testo("Agent", "Elaborazione in corso...")
        self.send_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._chiama_gemini, args=(testo,), daemon=True).start()

    def _chiama_gemini(self, testo):
        def avvisa_retry(msg):
            testo_msg = msg if isinstance(msg, str) else f"Server occupato, nuovo tentativo {msg}/3..."
            self.root.after(0, self.aggiungi_testo, "Agent", testo_msg)

        if self.agent is None:
            self.agent = GeminiAgent(confirm_callback=self._chiedi_conferma_utente)
        risposta = self.agent.invia(testo, on_retry=avvisa_retry)
        self.root.after(0, self._mostra_risposta, risposta)

    def _mostra_risposta(self, testo_risposta):
        self.aggiungi_testo("Agent", testo_risposta)
        self.send_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = PCAgentGUI(root)
    root.mainloop()