import psutil
import time
from google import genai
from google.genai import types
from config.settings import GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_TIMEOUT_MS
from modules import tools

class GeminiAgent:
    def __init__(self, confirm_callback=None):
        self.client = None
        self.chat = None
        self.errore_init = None
        self.modello_corrente = GEMINI_MODEL
        self.confirm_callback = confirm_callback
        self._config_chat = None
        self._inizializza(GEMINI_MODEL)

    def _richiedi_conferma(self, descrizione: str) -> bool:
        """Richiede conferma esplicita lato codice (Human-in-the-Loop) se un callback è configurato."""
        if self.confirm_callback is None:
            return True
        try:
            return bool(self.confirm_callback(descrizione))
        except Exception:
            return False

    def _costruisci_tools(self) -> list:
        def disabilita_app_avvio(nome_app: str) -> str:
            """Rimuove un'app dall'avvio automatico dell'utente corrente (HKCU Run) previa conferma utente."""
            if not self._richiedi_conferma(f"Rimuovere '{nome_app}' dalle app all'avvio automatico?"):
                return "Operazione annullata dall'utente."
            return tools.disabilita_app_avvio(nome_app)

        def termina_processo(target: str) -> str:
            """Termina in modo sicuro un processo dato PID o nome esatto previa conferma utente."""
            if not self._richiedi_conferma(f"Terminare il processo '{target}'?"):
                return "Operazione annullata dall'utente."
            return tools.termina_processo(target)

        def attiva_modalita_prestazioni() -> str:
            """Attiva il piano Prestazioni Eccellenti e chiude app non protette previa conferma utente."""
            if not self._richiedi_conferma("Attivare la Modalità Prestazioni e chiudere le app non essenziali?"):
                return "Operazione annullata dall'utente."
            return tools.attiva_modalita_prestazioni()

        def pulisci_file_temporanei() -> str:
            """Elimina i file temporanei non in uso da TEMP previa conferma utente."""
            if not self._richiedi_conferma("Eliminare i file temporanei non in uso dalla cartella TEMP?"):
                return "Operazione annullata dall'utente."
            return tools.pulisci_file_temporanei()

        def blocca_lhm_da_lan() -> str:
            """Crea una regola Windows Firewall per bloccare la porta 8085 di LHM dalla LAN previa conferma utente."""
            if not self._richiedi_conferma("Creare una regola Windows Firewall (richiederà UAC) per bloccare l'accesso esterno alla porta 8085 di LibreHardwareMonitor?"):
                return "Operazione annullata dall'utente."
            return tools.blocca_lhm_da_lan()

        return [
            tools.analizza_sistema,
            tools.leggi_sensori_cpu,
            tools.monitora_gpu,
            tools.monitora_archiviazione,
            tools.analizza_spazio_disco,
            tools.info_banchi_ram,
            tools.info_rete_attiva,
            tools.misura_ping,
            tools.info_versioni_sistema,
            tools.piano_energetico_attivo,
            tools.stato_sicurezza_lhm,
            tools.elenca_app_avvio,
            disabilita_app_avvio,
            termina_processo,
            attiva_modalita_prestazioni,
            tools.ripristina_modalita_bilanciata,
            pulisci_file_temporanei,
            blocca_lhm_da_lan,
        ]

    def _costruisci_config(self):
        cpu_nome = tools.info_cpu_nome()
        cpu_core = psutil.cpu_count(logical=False) or psutil.cpu_count() or "?"
        ram_gb = round(psutil.virtual_memory().total / (1024**3))
        gpu_info = tools.monitora_gpu()
        gpu_nome = gpu_info.get("gpu", "GPU non rilevata")
        win_ver = tools.info_versioni_sistema().get("windows", "Windows")

        istruzioni = (
            f"Sei un Agent AI di ottimizzazione per {win_ver} su un PC con {cpu_nome} ({cpu_core} core), "
            f"{ram_gb} GB di RAM e {gpu_nome}. Rispondi in italiano in modo conciso e pratico. "
            "Usa gli strumenti disponibili per analizzare CPU/RAM/banchi RAM/ventole, monitorare la GPU, "
            "controllare dischi e spazio occupato, verificare rete e ping, controllare versioni di Windows/driver, "
            "gestire app all'avvio, terminare processi bloccati in modo sicuro, attivare la modalità prestazioni, "
            "pulire file temporanei o ripristinare il piano bilanciato. Non chiudere né suggerire mai di "
            "disabilitare i processi protetti configurati (es. Riot Vanguard, Riot Client, Discord, Steam). "
            "Prima di disabilitare un'app all'avvio o terminare un processo, chiedi sempre conferma esplicita all'utente."
        )
        return types.GenerateContentConfig(
            system_instruction=istruzioni,
            tools=self._costruisci_tools(),
            temperature=0.2,
        )

    def _inizializza(self, modello: str, history=None):
        try:
            if self.client is None:
                self.client = genai.Client(http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
            if self._config_chat is None:
                self._config_chat = self._costruisci_config()
            kwargs = {"model": modello, "config": self._config_chat}
            if history:
                kwargs["history"] = history
            self.chat = self.client.chats.create(**kwargs)
            self.modello_corrente = modello
            self.errore_init = None
        except Exception as e:
            self.chat = None
            self.errore_init = str(e)

    def invia(self, testo: str, on_retry=None) -> str:
        if self.chat is None:
            self._inizializza(self.modello_corrente)
            if self.chat is None:
                return f"Agent AI non disponibile (controlla connessione o API key): {self.errore_init}"

        ordine_modelli = [self.modello_corrente] + [
            m for m in [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS] if m != self.modello_corrente
        ]

        ultimo_errore = ""
        for idx, modello in enumerate(ordine_modelli):
            if modello != self.modello_corrente:
                if on_retry:
                    on_retry(f"Server occupato su {self.modello_corrente}, passaggio a {modello}...")
                try:
                    cronologia = self.chat.get_history() if self.chat else None
                except Exception:
                    cronologia = None
                self._inizializza(modello, history=cronologia)
                if self.chat is None:
                    ultimo_errore = self.errore_init or "Errore inizializzazione fallback"
                    continue

            try:
                risposta = self.chat.send_message(testo)
                return risposta.text or "Nessuna risposta testuale ricevuta."
            except Exception as e:
                err_str = str(e)
                ultimo_errore = err_str
                da_fallback = any(cod in err_str for cod in ("503", "504", "429", "404", "UNAVAILABLE", "OVERLOADED", "NOT_FOUND"))
                if da_fallback:
                    continue
                return f"Errore: {e}"

        return f"Tutti i modelli Gemini risultano temporaneamente occupati. Ultimo errore: {ultimo_errore}"