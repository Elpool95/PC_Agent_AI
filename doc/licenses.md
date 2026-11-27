# Licenze & Attribuzioni — PC Agent AI

## Licenza del progetto
- **Progetto**: PC Agent AI
- **Autore**: Elpool95 (`https://github.com/Elpool95/PC_Agent_AI`)
- **Licenza**: **MIT License** (vedi file `LICENSE` nella root del repository)

## Dipendenze Python (runtime)
| Pacchetto | Versione minima | Licenza | Note |
| :--- | :--- | :--- | :--- |
| `psutil` | `>=5.9.0` | **BSD-3-Clause** | Telemetria CPU, RAM, dischi, rete e processi |
| `google-genai` | `>=1.0.0` | **Apache-2.0** | SDK ufficiale Google Gemini API |

## Dipendenze Python (sviluppo e test)
| Pacchetto | Versione minima | Licenza | Note |
| :--- | :--- | :--- | :--- |
| `pytest` | `>=8.0.0` | **MIT** | Runner test unitari e report JUnit XML |
| `pytest-cov` | `>=5.0.0` | **MIT** | Calcolo code coverage (`>= 80%`) |

## Strumenti esterni opzionali (non distribuiti nel repository)
| Strumento | Licenza | Modalità d'uso |
| :--- | :--- | :--- |
| **LibreHardwareMonitor** | **MPL-2.0** | Interrogato opzionalmente via HTTP locale (`http://localhost:8085/data.json`) se installato dall'utente |
| **NVIDIA `nvidia-smi`** | **Proprietaria NVIDIA** | Invocato opzionalmente come eseguibile di sistema fornito dai driver NVIDIA dell'utente |
| **Google Gemini API** | **Google API Terms of Service** | Servizio cloud opzionale utilizzato tramite API key personale dell'utente |

> Tutte le dipendenze runtime e dev utilizzano licenze permissive (MIT, BSD-3-Clause, Apache-2.0) pienamente compatibili con la licenza **MIT** del progetto.
