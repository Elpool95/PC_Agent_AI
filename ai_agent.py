import time
from google import genai
from google.genai import types
from config import GEMINI_MODEL, GEMINI_TIMEOUT_MS
import tools

class GeminiAgent:
    def __init__(self):
        self.client = None
        self.chat = None
        self.errore_init = None
        self._inizializza()

    def _inizializza(self):
        try:
            self.client = genai.Client(http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
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
            self.chat = self.client.chats.create(
                model=GEMINI_MODEL,
                config=types.GenerateContentConfig(
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
            )
            self.errore_init = None
        except Exception as e:
            self.chat = None
            self.errore_init = str(e)

    def invia(self, testo: str, on_retry=None) -> str:
        if self.chat is None:
            self._inizializza()
            if self.chat is None:
                return f"Agent AI non disponibile (controlla connessione o API key): {self.errore_init}"
        for tentativo in range(3):
            try:
                risposta = self.chat.send_message(testo)
                return risposta.text or "Nessuna risposta testuale ricevuta."
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "504" in err_str) and tentativo < 2:
                    if on_retry:
                        on_retry(tentativo + 2)
                    time.sleep(3)
                    continue
                return f"Errore: {e}"
        return "Errore imprevisto durante la richiesta."