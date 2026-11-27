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
        self.root.geometry("880x640")
        self.root.configure(bg="#1e1e1e")

        self.agent = GeminiAgent()

        # --- BARRA TELEMETRIA IN TEMPO REALE (3 RIGHE) ---
        tele_frame = tk.Frame(root, bg="#141414", bd=1, relief=tk.SOLID)
        tele_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        row1 = tk.Frame(tele_frame, bg="#141414")
        row1.pack(fill=tk.X, padx=8, pady=(6, 2))

        self.lbl_cpu = tk.Label(row1, text="CPU: --% | -- °C", bg="#141414", fg="#81c784", font=("Consolas", 10, "bold"))
        self.lbl_cpu.pack(side=tk.LEFT, padx=(4, 18))

        self.lbl_ram = tk.Label(row1, text="RAM: --/-- GB (--%)", bg="#141414", fg="#4fc3f7", font=("Consolas", 10, "bold"))
        self.lbl_ram.pack(side=tk.LEFT)

        row2 = tk.Frame(tele_frame, bg="#141414")
        row2.pack(fill=tk.X, padx=8, pady=2)

        self.lbl_disk = tk.Label(row2, text="Dischi C: / E: rilevamento in corso...", bg="#141414", fg="#ce93d8", font=("Consolas", 10, "bold"))
        self.lbl_disk.pack(side=tk.LEFT, padx=4)

        row3 = tk.Frame(tele_frame, bg="#141414")
        row3.pack(fill=tk.X, padx=8, pady=(2, 6))

        self.lbl_gpu = tk.Label(row3, text="RTX 3070: --% | --°C | VRAM: --/-- MB | Consumo: -- W", bg="#141414", fg="#ffb74d", font=("Consolas", 10, "bold"))
        self.lbl_gpu.pack(side=tk.LEFT, padx=4)

        # --- PULSANTI RAPIDI LOCALI ---
        btn_frame = tk.Frame(root, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=10, pady=(5, 5))

        tk.Button(
            btn_frame, text="Top Processi CPU", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_stato_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Archiviazione", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_dischi_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        self.btn_gaming = tk.Button(
            btn_frame, text="Modalità Gaming", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_gaming_locale, daemon=True).start()
        )
        self.btn_gaming.pack(side=tk.LEFT, padx=4)

        self.btn_bilanciato = tk.Button(
            btn_frame, text="Bilanciato", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_bilanciato_locale, daemon=True).start()
        )
        self.btn_bilanciato.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="App all'Avvio", bg="#2d2d30", fg="#ffffff",
            activebackground="#3e3e42", activeforeground="#ffffff",
            relief=tk.FLAT, padx=10, pady=5,
            command=lambda: threading.Thread(target=self.azione_avvio_locale, daemon=True).start()
        ).pack(side=tk.LEFT, padx=4)

        # --- AREA CHAT ---
        self.chat_area = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, bg="#252526", fg="#e0e0e0",
            font=("Segoe UI", 10), state=tk.DISABLED, relief=tk.FLAT, padx=10, pady=10
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_area.tag_config("utente", foreground="#4fc3f7", font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("agent", foreground="#81c784", font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("locale", foreground="#ffb74d", font=("Segoe UI", 10, "bold"))

        # --- BARRA DI INPUT ---
        input_frame = tk.Frame(root, bg="#1e1e1e")
        input_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.entry = tk.Entry(
            input_frame, bg="#2d2d30", fg="#ffffff", insertbackground="#ffffff",
            font=("Segoe UI", 10), relief=tk.FLAT
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.invia_messaggio())

        self.send_btn = tk.Button(
            input_frame, text="Invia", bg="#007acc", fg="#ffffff",
            activebackground="#005a9e", activeforeground="#ffffff",
            relief=tk.FLAT, padx=16, pady=6, command=self.invia_messaggio
        )
        self.send_btn.pack(side=tk.RIGHT)

        self.aggiungi_testo("Agent", "Pronto. Telemetria live attiva: CPU (+ Temp), RAM, Dischi C:/E: e RTX 3070.\n")

        psutil.cpu_percent(interval=None)
        threading.Thread(target=self._loop_telemetria, daemon=True).start()

    def _imposta_stato_modalita(self, modalita):
        if modalita == "gaming":
            self.btn_gaming.config(text="Modalità Gaming ● ATTIVA", bg="#2e7d32", activebackground="#388e3c")
            self.btn_bilanciato.config(text="Bilanciato", bg="#2d2d30", activebackground="#3e3e42")
        elif modalita == "bilanciato":
            self.btn_gaming.config(text="Modalità Gaming", bg="#2d2d30", activebackground="#3e3e42")
            self.btn_bilanciato.config(text="Bilanciato ● ATTIVO", bg="#0277bd", activebackground="#0288d1")

    def _loop_telemetria(self):
        mappa_dischi = tools.mappa_dischi_fisici(("C", "E"))
        prev_io = psutil.disk_io_counters(perdisk=True)
        prev_time = time.time()

        while True:
            time.sleep(2)
            try:
                now = time.time()
                dt = max(now - prev_time, 0.1)
                curr_io = psutil.disk_io_counters(perdisk=True)

                parti_dischi = []
                for lettera in ("C", "E"):
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
                disk_text = "  |  ".join(parti_dischi)
                disk_color = "#ce93d8"

                cpu = psutil.cpu_percent(interval=None)
                cpu_temp = tools.leggi_temp_cpu()
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

                self.root.after(
                    0, self._aggiorna_barra,
                    f"CPU: {cpu}% | {cpu_temp}", cpu_color,
                    f"RAM: {ram_used}/{ram_tot} GB ({ram.percent}%)", ram_color,
                    disk_text, disk_color,
                    gpu_text, gpu_color
                )
            except Exception:
                pass

    def _aggiorna_barra(self, cpu_txt, cpu_col, ram_txt, ram_col, disk_txt, disk_col, gpu_txt, gpu_col):
        self.lbl_cpu.config(text=cpu_txt, fg=cpu_col)
        self.lbl_ram.config(text=ram_txt, fg=ram_col)
        self.lbl_disk.config(text=disk_txt, fg=disk_col)
        self.lbl_gpu.config(text=gpu_txt, fg=gpu_col)

    def aggiungi_testo(self, mittente, testo):
        self.chat_area.config(state=tk.NORMAL)
        tag = "utente" if mittente == "Tu" else ("locale" if mittente == "Sistema" else "agent")
        self.chat_area.insert(tk.END, f"{mittente}: ", tag)
        self.chat_area.insert(tk.END, f"{testo}\n")
        self.chat_area.see(tk.END)
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