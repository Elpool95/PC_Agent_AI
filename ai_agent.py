import time
from google import genai
from google.genai import types
from config import GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_TIMEOUT_MS
import tools

class GeminiAgent:
    def __init__(self):
        self.client = None
        self.chat = None
        self.errore_init = None
        self.modello_corrente = GEMINI_MODEL
        self._config_chat = None
        self._inizializza(GEMINI_MODEL)

    def _costruisci_config(self):
        istruzioni = (
            "Sei un Agent AI di ottimizzazione per Windows 11 23H2 su un PC con Intel i5-6500 (4 core), "
            "24 GB di RAM DDR4 e NVIDIA RTX 3070. Rispondi in italiano in modo conciso e pratico. "
            "Usa gli strumenti disponibili per analizzare CPU/RAM/banchi RAM/ventole, monitorare la RTX 3070, "
            "controllare dischi e spazio occupato, verificare rete e ping, controllare versioni di Windows/driver, "
            "gestire app all'avvio, terminare processi bloccati in modo sicuro, attivare la modalità prestazioni, "
            "pulire file temporanei o ripristinare il piano bilanciato. Non chiudere né suggerire mai di "
            "disabilitare Riot Vanguard, Riot Client, Discord o Steam. Prima di disabilitare un'app all'avvio "
            "o terminare un processo, chiedi sempre conferma esplicita all'utente."
        )
        return types.GenerateContentConfig(
            system_instruction=istruzioni,
            tools=[
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
                tools.elenca_app_avvio,
                tools.disabilita_app_avvio,
                tools.termina_processo,
                tools.attiva_modalita_prestazioni,
                tools.ripristina_modalita_bilanciata,
                tools.pulisci_file_temporanei
            ],
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