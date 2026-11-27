import threading
import time
import tkinter as tk
from tkinter import scrolledtext
import psutil
import config
import tools
from ai_agent import GeminiAgent

class PCAgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PC Agent AI — Windows 11 + RTX 3070")
        self.root.geometry("900x760")
        self.root.minsize(820, 620)
        self.root.configure(bg="#1e1e1e")

        self.agent = GeminiAgent()

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

        self.lbl_disk = tk.Label(
            row2, text="Dischi: rilevamento in corso...", bg="#141414", fg="#ce93d8",
            font=("Consolas", 10, "bold"), justify=tk.LEFT, anchor="w"
        )
        self.lbl_disk.pack(side=tk.LEFT, fill=tk.X, padx=4)

        row3 = tk.Frame(tele_frame, bg="#141414")
        row3.pack(fill=tk.X, padx=8, pady=2)

        self.lbl_gpu = tk.Label(row3, text="RTX 3070: --% | --°C | VRAM: --/-- MB | Consumo: -- W", bg="#141414", fg="#ffb74d", font=("Consolas", 10, "bold"))
        self.lbl_gpu.pack(side=tk.LEFT, padx=4)

        row4 = tk.Frame(tele_frame, bg="#141414")
        row4.pack(fill=tk.X, padx=8, pady=(2, 6))

        self.lbl_net = tk.Label(row4, text="Rete: rilevamento in corso...", bg="#141414", fg="#4db6ac", font=("Consolas", 10, "bold"))
        self.lbl_net.pack(side=tk.LEFT, padx=4)

        # --- PULSANTI RAPIDI LOCALI ---
        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        tk.Button(
            btn_frame, text="Top CPU Process", bg="#2d2d30", fg="#ffffff",
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

        self.aggiungi_testo("Agent", "Pronto. Telemetria live attiva: CPU (Temp + W), RAM, tutti i dischi, RTX 3070 e Rete.\n")

        self.ram_info_hw = {"banchi": [], "frequenza_mhz": 0, "tipo": "RAM", "modalita_canale": "", "totale_gb": 0}

        psutil.cpu_percent(interval=None)
        threading.Thread(target=self._carica_info_hw, daemon=True).start()
        threading.Thread(target=self._loop_telemetria, daemon=True).start()

    def _carica_info_hw(self):
        info = tools.info_versioni_sistema()
        testo_footer = f"OS: {info['windows']}   |   Driver Grafico NVIDIA: {info['driver_gpu']}"
        self.root.after(0, lambda: self.lbl_footer.config(text=testo_footer))

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

    def _imposta_stato_modalita(self, modalita):
        if modalita == "gaming":
            self.btn_gaming.config(text="Gaming Mode ●", bg="#2e7d32", activebackground="#388e3c")
            self.btn_bilanciato.config(text="Balance", bg="#2d2d30", activebackground="#3e3e42")
        elif modalita == "bilanciato":
            self.btn_gaming.config(text="Gaming Mode", bg="#2d2d30", activebackground="#3e3e42")
            self.btn_bilanciato.config(text="Balance ●", bg="#0277bd", activebackground="#0288d1")

    def _loop_telemetria(self):
        lettere_correnti = tools.elenca_lettere_dischi()
        mappa_dischi = tools.mappa_dischi_fisici()
        prev_io = psutil.disk_io_counters(perdisk=True)
        prev_net = psutil.net_io_counters(pernic=True)
        prev_time = time.time()

        while True:
            time.sleep(2)
            try:
                now = time.time()
                dt = max(now - prev_time, 0.1)
                curr_io = psutil.disk_io_counters(perdisk=True)
                curr_net = psutil.net_io_counters(pernic=True)

                nuove_lettere = tools.elenca_lettere_dischi()
                if nuove_lettere != lettere_correnti:
                    lettere_correnti = nuove_lettere
                    mappa_dischi = tools.mappa_dischi_fisici()

                parti_dischi = []
                for lettera in lettere_correnti:
                    try:
                        uso = psutil.disk_usage(f"{lettera}:\\")
                        liberi = round(uso.free / (1024**3), 0)
                        info = f"{lettera}: {uso.percent}% ({int(liberi)}GB liberi)"
                    except Exception:
                        info = f"{lettera}: N/D"

                    drive_fisico = mappa_dischi.get(lettera)
                    if drive_fisico and drive_fisico in curr_io and drive_fisico in prev_io:
                        r_mb = round((curr_io[drive_fisico].read_bytes - prev_io[drive_fisico].read_bytes) / dt / (1024 * 1024), 1)
                        w_mb = round((curr_io[drive_fisico].write_bytes - prev_io[drive_fisico].write_bytes) / dt / (1024 * 1024), 1)
                        info += f" R {r_mb}/W {w_mb} MB/s"
                    parti_dischi.append(info)

                prev_io, prev_time = curr_io, now
                if parti_dischi:
                    righe_dischi = [
                        "  |  ".join(parti_dischi[i:i + 2])
                        for i in range(0, len(parti_dischi), 2)
                    ]
                    disk_text = "\n".join(righe_dischi)
                else:
                    disk_text = "Nessun disco rilevato"
                disk_color = "#ce93d8"

                cpu = psutil.cpu_percent(interval=None)
                cpu_temp, cpu_watt = tools.leggi_sensori_cpu()
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
                    gpu_text = (
                        f"RTX 3070: {gpu['utilizzo_percent']} | {gpu['temperatura_c']} | "
                        f"VRAM: {gpu['vram_usata_mb']}/{gpu['vram_totale_mb']} MB | Consumo: {gpu['consumo_watt']}"
                    )
                    gpu_color = "#ff5252" if temp_num >= config.GPU_TEMP_CRIT else ("#ffb74d" if temp_num >= config.GPU_TEMP_WARN else "#81c784")

                rete = tools.info_rete_attiva()
                nome_nic = rete["nome"]
                if nome_nic == "Offline":
                    net_text = "Rete: Offline"
                    net_color = "#ff5252"
                else:
                    if nome_nic in curr_net and nome_nic in prev_net:
                        dl_bs = (curr_net[nome_nic].bytes_recv - prev_net[nome_nic].bytes_recv) / dt
                        ul_bs = (curr_net[nome_nic].bytes_sent - prev_net[nome_nic].bytes_sent) / dt
                    else:
                        dl_bs = 0.0
                        ul_bs = 0.0
                    link_str = f" {rete['link_mbps']} Mbps" if rete["link_mbps"] else ""
                    dl_str = tools.formatta_velocita_rete(dl_bs)
                    ul_str = tools.formatta_velocita_rete(ul_bs)
                    net_text = f"Rete ({nome_nic}{link_str} | {rete['ip']}): ↓ {dl_str} | ↑ {ul_str}"
                    net_color = "#4db6ac"
                prev_net = curr_net

                ram_extra = ""
                if self.ram_info_hw.get("frequenza_mhz"):
                    ram_extra = f" | {self.ram_info_hw['tipo']} {self.ram_info_hw['frequenza_mhz']} MHz ({self.ram_info_hw['modalita_canale']})"

                self.root.after(
                    0, self._aggiorna_barra,
                    f"CPU: {cpu}% | {cpu_temp} | {cpu_watt}", cpu_color,
                    f"RAM: {ram_used}/{ram_tot} GB ({ram.percent}%){ram_extra}", ram_color,
                    disk_text, disk_color,
                    gpu_text, gpu_color,
                    net_text, net_color
                )
            except Exception:
                pass

    def _aggiorna_barra(self, cpu_txt, cpu_col, ram_txt, ram_col, disk_txt, disk_col, gpu_txt, gpu_col, net_txt, net_col):
        self.lbl_cpu.config(text=cpu_txt, fg=cpu_col)
        self.lbl_ram.config(text=ram_txt, fg=ram_col)
        self.lbl_disk.config(text=disk_txt, fg=disk_col)
        self.lbl_gpu.config(text=gpu_txt, fg=gpu_col)
        self.lbl_net.config(text=net_txt, fg=net_col)

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
        sys_info = tools.analizza_sistema()
        top = "\n".join([f"  - {p['name']} (PID {p['pid']}): {p['cpu_percent']}%" for p in sys_info['top_processi_cpu']])
        self.root.after(0, self.aggiungi_testo, "Sistema", f"Top 5 processi sulla CPU:\n{top}\n")

    def azione_dischi_locale(self):
        dischi = tools.monitora_archiviazione()
        righe = ["Stato partizioni e dischi:"]
        for d in dischi:
            righe.append(f"  - {d['unita']}  Usati: {d['usati_gb']}/{d['totali_gb']} GB ({d['percent']}%) | Liberi: {d['liberi_gb']} GB")
        righe.append("")
        self.root.after(0, self.aggiungi_testo, "Sistema", "\n".join(righe))

    def azione_gaming_locale(self):
        res_perf = tools.attiva_modalita_prestazioni()
        res_temp = tools.pulisci_file_temporanei()
        self.root.after(0, self._imposta_stato_modalita, "gaming")
        self.root.after(0, self.aggiungi_testo, "Sistema", f"{res_perf}\n{res_temp}\n")

    def azione_bilanciato_locale(self):
        res = tools.ripristina_modalita_bilanciata()
        self.root.after(0, self._imposta_stato_modalita, "bilanciato")
        self.root.after(0, self.aggiungi_testo, "Sistema", f"{res}\n")

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
        def avvisa_retry(num):
            self.root.after(0, self.aggiungi_testo, "Agent", f"Server occupato, nuovo tentativo {num}/3...")

        risposta = self.agent.invia(testo, on_retry=avvisa_retry)
        self.root.after(0, self._mostra_risposta, risposta)

    def _mostra_risposta(self, testo_risposta):
        self.aggiungi_testo("Agent", testo_risposta)
        self.send_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = PCAgentGUI(root)
    root.mainloop()