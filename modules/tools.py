import atexit
import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import urllib.request
import winreg
import psutil
from config.settings import (
    SAFE_TO_CLOSE, PROTECTED_PROCESSES, NO_WINDOW,
    DISK_CRIT, GPU_TEMP_WARN, GAMING_PAUSABLE_SERVICES,
    GAMING_THROTTLE_PROCESSES, GAMING_OPTIONAL_LAUNCHERS,
    GAMING_STATE_FILE, TELEMETRY_INTERVAL_NORMAL, TELEMETRY_INTERVAL_GAMING,
    FPS_CAP_MARGIN_HZ, FPS_CAP_MIN,
    DISK_TEMP_WARN_HDD, DISK_TEMP_CRIT_HDD, DISK_TEMP_WARN_SSD, DISK_TEMP_CRIT_SSD,
)

def _trova_nvidia_smi() -> str:
    """Trova il percorso assoluto di nvidia-smi.exe su Windows."""
    percorso = shutil.which("nvidia-smi")
    if percorso:
        return percorso
    candidati = [
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    ]
    for c in candidati:
        if os.path.exists(c):
            return c
    return "nvidia-smi"

def analizza_sistema(limite: int = 10) -> dict:
    """Campiona l'utilizzo reale di CPU, RAM, i Top N processi CPU/RAM (con processo padre) e il riepilogo aggregato per app."""
    limite = max(1, min(int(limite), 25))
    n_logici = psutil.cpu_count(logical=True) or 1

    # Passo 1: priming dei contatori CPU per processo (la 1a lettura di psutil è sempre 0.0%)
    snapshot_procs = []
    for p in psutil.process_iter(['pid', 'ppid', 'name', 'cpu_percent', 'memory_info']):
        try:
            nome = p.info.get('name')
            if not nome or nome == 'System Idle Process':
                continue
            if callable(getattr(p, "cpu_percent", None)):
                p.cpu_percent(interval=None)
            snapshot_procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Passo 2: finestra di campionamento condivisa (0.8s) per CPU globale e delta per-processo
    cpu = psutil.cpu_percent(interval=0.8)
    ram = psutil.virtual_memory()

    # Mappa PID -> nome per risolvere velocemente il processo padre senza chiamate extra
    pid_to_name = {}
    for p in snapshot_procs:
        pid_val = p.info.get('pid')
        if pid_val is not None:
            pid_to_name[pid_val] = p.info.get('name') or ""

    processi = []
    per_app = {}
    for p in snapshot_procs:
        try:
            nome = p.info.get('name')
            if not nome or nome == 'System Idle Process':
                continue
            if callable(getattr(p, "cpu_percent", None)):
                raw_cpu = p.cpu_percent(interval=None)
                cpu_norm = round(min(raw_cpu / n_logici, 100.0), 1)
            else:
                cpu_norm = round(float(p.info.get('cpu_percent') or 0.0), 1)

            mem = None
            if callable(getattr(p, "memory_info", None)):
                try:
                    mem = p.memory_info()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    mem = p.info.get('memory_info')
            else:
                mem = p.info.get('memory_info')
            ram_mb = round(mem.rss / (1024 * 1024), 1) if mem else 0.0

            ppid = p.info.get('ppid')
            parent_name = pid_to_name.get(ppid, "") if ppid else ""
            if not parent_name and ppid and ppid > 0:
                try:
                    parent_name = psutil.Process(ppid).name()
                except Exception:
                    parent_name = f"PID {ppid}"
            parent_label = f"{parent_name} ({ppid})" if (parent_name and ppid and not parent_name.startswith("PID ")) else (parent_name or "Sistema")

            item = {
                'pid': p.info['pid'],
                'ppid': ppid,
                'name': nome,
                'parent': parent_label,
                'cpu_percent': cpu_norm,
                'ram_mb': ram_mb,
            }
            processi.append(item)

            agg = per_app.setdefault(nome, {'name': nome, 'istanze': 0, 'cpu_percent': 0.0, 'ram_mb': 0.0})
            agg['istanze'] += 1
            agg['cpu_percent'] = round(agg['cpu_percent'] + cpu_norm, 1)
            agg['ram_mb'] = round(agg['ram_mb'] + ram_mb, 1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    top_cpu = sorted(processi, key=lambda x: (x['cpu_percent'], x['ram_mb']), reverse=True)[:limite]
    top_ram = sorted(processi, key=lambda x: x['ram_mb'], reverse=True)[:limite]
    top_app_ram = sorted(per_app.values(), key=lambda x: x['ram_mb'], reverse=True)[:5]
    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_usata_gb": round(ram.used / (1024**3), 2),
        "ram_totale_gb": round(ram.total / (1024**3), 2),
        "top_processi_cpu": top_cpu,
        "top_processi_ram": top_ram,
        "top_app_ram": top_app_ram,
    }

_NVML_INITIALIZED = False
_NVML_HANDLE = None
_NVML_ATEXIT_REGISTERED = False


def _chiudi_nvml() -> None:
    """Chiude in modo pulito la sessione NVML alla chiusura del processo."""
    global _NVML_INITIALIZED, _NVML_HANDLE
    if _NVML_INITIALIZED:
        try:
            import pynvml
            pynvml.nvmlShutdown()
        except Exception:
            pass
    _NVML_INITIALIZED = False
    _NVML_HANDLE = None


def _monitora_gpu_nvml() -> dict | None:
    """Legge la telemetria GPU NVIDIA direttamente in-process via NVML (pynvml) senza creare processi esterni."""
    global _NVML_INITIALIZED, _NVML_HANDLE, _NVML_ATEXIT_REGISTERED
    try:
        import pynvml
    except Exception:
        return None

    try:
        if not _NVML_INITIALIZED or _NVML_HANDLE is None:
            pynvml.nvmlInit()
            _NVML_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
            _NVML_INITIALIZED = True
            if not _NVML_ATEXIT_REGISTERED:
                atexit.register(_chiudi_nvml)
                _NVML_ATEXIT_REGISTERED = True

        h = _NVML_HANDLE
        nome_raw = pynvml.nvmlDeviceGetName(h)
        nome = nome_raw.decode("utf-8", errors="ignore") if isinstance(nome_raw, bytes) else str(nome_raw)
        util_num = int(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        temp_num = int(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        vram_usata = str(int(mem.used // (1024 * 1024)))
        vram_tot = str(int(mem.total // (1024 * 1024)))

        try:
            watt_str = f"{pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0:.2f} W"
        except Exception:
            watt_str = "N/D"
        try:
            fan_str = f"{int(pynvml.nvmlDeviceGetFanSpeed(h))}%"
        except Exception:
            fan_str = "N/D"
        try:
            clock_str = f"{int(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS))} MHz"
        except Exception:
            clock_str = "N/D"
        try:
            pstate_str = f"P{int(pynvml.nvmlDeviceGetPerformanceState(h))}"
        except Exception:
            pstate_str = "N/D"

        return {
            "gpu": nome.strip(),
            "utilizzo_percent": f"{util_num}%",
            "utilizzo_num": util_num,
            "temperatura_c": f"{temp_num}°C",
            "temperatura_num": temp_num,
            "vram_usata_mb": vram_usata,
            "vram_totale_mb": vram_tot,
            "consumo_watt": watt_str,
            "ventola_percent": fan_str,
            "clock_mhz": clock_str,
            "pstate": pstate_str,
        }
    except Exception:
        _chiudi_nvml()
        return None


def monitora_gpu() -> dict:
    """Legge utilizzo, temperatura, VRAM usata/totale, consumo W, ventola % e clock MHz della GPU NVIDIA (NVML con fallback nvidia-smi)."""
    nvml_res = _monitora_gpu_nvml()
    if nvml_res is not None:
        return nvml_res
    try:
        smi = _trova_nvidia_smi()
        cmd = [
            smi,
            "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw,fan.speed,clocks.gr,pstate",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(
            cmd, encoding="utf-8", stderr=subprocess.STDOUT, timeout=5, creationflags=NO_WINDOW
        ).strip()
        prima_riga = output.splitlines()[0]
        nome, util, temp, vram_usata, vram_tot, watt, fan, clock, pstate = [x.strip() for x in prima_riga.split(",")]
        try:
            util_num = int(float(util))
        except ValueError:
            util_num = 0
        try:
            temp_num = int(float(temp))
        except ValueError:
            temp_num = 0
        return {
            "gpu": nome,
            "utilizzo_percent": f"{util}%",
            "utilizzo_num": util_num,
            "temperatura_c": f"{temp}°C",
            "temperatura_num": temp_num,
            "vram_usata_mb": vram_usata,
            "vram_totale_mb": vram_tot,
            "consumo_watt": f"{watt} W",
            "ventola_percent": f"{fan}%",
            "clock_mhz": f"{clock} MHz",
            "pstate": pstate
        }
    except Exception as e:
        return {"errore": str(e)}

def _cerca_temp_cpu(nodo) -> str | None:
    """Cerca il sensore temperatura CPU Package (°C) nel JSON di LibreHardwareMonitor."""
    if isinstance(nodo, dict):
        testo = nodo.get("Text", "")
        valore = nodo.get("Value", "")
        if ("CPU Package" in testo or "Core Average" in testo) and "°C" in valore:
            return valore
        for figlio in nodo.get("Children", []):
            trovato = _cerca_temp_cpu(figlio)
            if trovato:
                return trovato
    elif isinstance(nodo, list):
        for elem in nodo:
            trovato = _cerca_temp_cpu(elem)
            if trovato:
                return trovato
    return None

def _cerca_potenza_cpu(nodo, target="CPU Package") -> str | None:
    """Cerca il sensore potenza CPU (W) nel JSON di LibreHardwareMonitor."""
    if isinstance(nodo, dict):
        testo = nodo.get("Text", "")
        valore = nodo.get("Value", "")
        if target in testo and "W" in valore:
            return valore
        for figlio in nodo.get("Children", []):
            trovato = _cerca_potenza_cpu(figlio, target)
            if trovato:
                return trovato
    elif isinstance(nodo, list):
        for elem in nodo:
            trovato = _cerca_potenza_cpu(elem, target)
            if trovato:
                return trovato
    return None

def _cerca_ventole_attive(nodo, risultati=None) -> list[str]:
    """Cerca le ventole di sistema attive (> 0 RPM, esclusa GPU) nel JSON di LibreHardwareMonitor."""
    if risultati is None:
        risultati = []
    if isinstance(nodo, dict):
        testo = nodo.get("Text", "")
        valore = nodo.get("Value", "")
        if "RPM" in valore and "gpu" not in testo.lower():
            m = re.search(r"(\d+)", valore)
            if m and int(m.group(1)) > 0:
                etichetta = testo.replace("Fan #", "F").strip()
                risultati.append(f"{etichetta}: {m.group(1)} RPM")
        for figlio in nodo.get("Children", []):
            _cerca_ventole_attive(figlio, risultati)
    elif isinstance(nodo, list):
        for elem in nodo:
            _cerca_ventole_attive(elem, risultati)
    return risultati

def _parse_numero_lhm(valore: str) -> float | None:
    """Estrae un valore numerico float da una stringa sensore LHM (es. '41,0 °C' -> 41.0)."""
    m = re.search(r"(-?\d+(?:[.,]\d+)?)", str(valore or ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _raccogli_sensori_drive_lhm(nodo, acc: dict) -> None:
    """Raccoglie ricorsivamente temperatura, vita residua e metriche S.M.A.R.T. di un singolo drive nel JSON LHM."""
    if isinstance(nodo, dict):
        testo = str(nodo.get("Text", "")).strip()
        valore = str(nodo.get("Value", "")).strip()
        tl = testo.lower()
        if valore:
            num = _parse_numero_lhm(valore)
            if "°c" in valore.lower() and num is not None:
                if "composite" in tl:
                    acc["temp_composite"] = num
                elif tl == "temperature":
                    acc["temp_main"] = num
                elif tl == "temperature #1" and "temp_alt" not in acc:
                    acc["temp_alt"] = num
            elif "%" in valore and num is not None:
                if tl in ("life", "remaining life", "health"):
                    acc["life_percent"] = max(0.0, min(100.0, num))
                elif "percentage used" in tl and "life_percent" not in acc:
                    acc["life_percent"] = max(0.0, min(100.0, 100.0 - num))
                elif "available spare" in tl and "threshold" not in tl:
                    acc["available_spare"] = num
            elif num is not None:
                if "power on hours" in tl:
                    acc["power_on_hours"] = int(round(num))
                elif "data written" in tl or "total lbas written" in tl:
                    if "tb" in valore.lower():
                        acc["data_written_gb"] = round(num * 1024.0, 1)
                    elif "gb" in valore.lower():
                        acc["data_written_gb"] = round(num, 1)
                elif "reallocated" in tl and "event" not in tl:
                    acc["reallocated"] = int(round(num))
                elif "pending" in tl:
                    acc["pending"] = int(round(num))
                elif "uncorrectable" in tl or "media errors" in tl:
                    acc["uncorrectable"] = int(round(num))
        for figlio in nodo.get("Children", []):
            _raccogli_sensori_drive_lhm(figlio, acc)
    elif isinstance(nodo, list):
        for elem in nodo:
            _raccogli_sensori_drive_lhm(elem, acc)


def _estrai_sensori_dischi_lhm(nodo, risultati=None) -> dict:
    """Estrae dal JSON LHM i sensori S.M.A.R.T./temperatura di tutti i dischi fisici indicizzati per nome normalizzato."""
    if risultati is None:
        risultati = {}
    if isinstance(nodo, dict):
        img = str(nodo.get("ImageURL", "")).lower()
        if "hdd.png" in img:
            nome = str(nodo.get("Text", "")).strip()
            if nome:
                acc = {}
                _raccogli_sensori_drive_lhm(nodo, acc)
                temp_num = acc.get("temp_composite")
                if temp_num is None:
                    temp_num = acc.get("temp_main")
                if temp_num is None:
                    temp_num = acc.get("temp_alt")
                risultati[nome.lower()] = {
                    "modello_lhm": nome,
                    "temp_num": int(round(temp_num)) if temp_num is not None else None,
                    "temperatura_c": f"{int(round(temp_num))}°C" if temp_num is not None else "N/D",
                    "life_percent": int(round(acc["life_percent"])) if "life_percent" in acc else None,
                    "available_spare": int(round(acc["available_spare"])) if "available_spare" in acc else None,
                    "power_on_hours": acc.get("power_on_hours"),
                    "data_written_gb": acc.get("data_written_gb"),
                    "reallocated": acc.get("reallocated", 0),
                    "pending": acc.get("pending", 0),
                    "uncorrectable": acc.get("uncorrectable", 0),
                }
            return risultati
        for figlio in nodo.get("Children", []):
            _estrai_sensori_dischi_lhm(figlio, risultati)
    elif isinstance(nodo, list):
        for elem in nodo:
            _estrai_sensori_dischi_lhm(elem, risultati)
    return risultati


def leggi_sensori_lhm() -> dict:
    """Legge in una sola chiamata HTTP a LibreHardwareMonitor sia i sensori CPU/ventole sia temperature/S.M.A.R.T. dei dischi."""
    try:
        # URL locale fisso http://localhost:8085/data.json (nessun input utente)
        with urllib.request.urlopen("http://localhost:8085/data.json", timeout=0.4) as resp:  # nosec B310
            dati = json.loads(resp.read().decode("utf-8"))
            temp = _cerca_temp_cpu(dati) or "N/D"
            watt = _cerca_potenza_cpu(dati, "CPU Package") or _cerca_potenza_cpu(dati, "CPU Cores") or "N/D"
            ventole = _cerca_ventole_attive(dati)
            dischi = _estrai_sensori_dischi_lhm(dati)
            return {
                "temperatura_c": temp,
                "potenza_w": watt,
                "ventole_rpm": ventole,
                "dischi_lhm": dischi,
            }
    except Exception:
        return {
            "temperatura_c": "-- °C (avvia LHM)",
            "potenza_w": "-- W",
            "ventole_rpm": [],
            "dischi_lhm": {},
        }


def leggi_sensori_cpu() -> dict:
    """Legge temperatura (°C), potenza (W) della CPU e ventole di sistema (RPM) da LibreHardwareMonitor."""
    dati = leggi_sensori_lhm()
    return {
        "temperatura_c": dati["temperatura_c"],
        "potenza_w": dati["potenza_w"],
        "ventole_rpm": dati["ventole_rpm"],
    }

def leggi_temp_cpu() -> str:
    """Legge la temperatura della CPU da LibreHardwareMonitor (http://localhost:8085/data.json) se attivo."""
    return leggi_sensori_cpu()["temperatura_c"]

def elenca_lettere_dischi() -> list[str]:
    """Restituisce tutte le lettere di unità disco attualmente montate e accessibili."""
    lettere = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or part.fstype == "":
            continue
        if part.device and len(part.device) >= 1 and part.device[0].isalpha():
            lettera = part.device[0].upper()
            if lettera not in lettere:
                lettere.append(lettera)
    return sorted(lettere)

def mappa_info_dischi_fisici(lettere=None) -> dict:
    """Associa ogni lettera di unità a PhysicalDriveX, modello, tipo (SSD/HDD), bus (NVMe/SATA) e HealthStatus Windows."""
    mappa = {}
    try:
        ps_cmd = (
            "$pds = Get-PhysicalDisk; "
            "Get-Partition | Where-Object {$_.DriveLetter} | ForEach-Object { "
            "$num = $_.DiskNumber; "
            "$pd = $pds | Where-Object {$_.DeviceId -eq [string]$num} | Select-Object -First 1; "
            "[PSCustomObject]@{ "
            "Letter = [string]$_.DriveLetter; "
            "Drive = 'PhysicalDrive' + $num; "
            "Model = if($pd){$pd.FriendlyName}else{''}; "
            "MediaType = if($pd){[string]$pd.MediaType}else{''}; "
            "BusType = if($pd){[string]$pd.BusType}else{''}; "
            "Health = if($pd){[string]$pd.HealthStatus}else{'Unknown'} "
            "} } | ConvertTo-Json -Compress"
        )
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=10, creationflags=NO_WINDOW
        ).strip()
        if output:
            dati = json.loads(output)
            if isinstance(dati, dict):
                dati = [dati]
            for item in dati:
                lettera = str(item.get("Letter") or "").strip().upper()
                if not lettera or (lettere is not None and lettera not in lettere):
                    continue
                modello = str(item.get("Model") or "").strip()
                media = str(item.get("MediaType") or "").strip()
                bus = str(item.get("BusType") or "").strip()
                if media in ("", "Unspecified"):
                    media = "SSD" if ("ssd" in modello.lower() or bus.upper() == "NVME") else "HDD"
                mappa[lettera] = {
                    "drive": str(item.get("Drive") or "").strip(),
                    "modello": modello,
                    "tipo": media,
                    "bus": bus,
                    "health_win": str(item.get("Health") or "Unknown").strip(),
                }
    except Exception:
        pass
    return mappa


def _abbina_lhm_disco(modello: str, dischi_lhm: dict) -> dict:
    """Abbina un modello disco di Windows alla relativa voce LHM (match esatto o per sottostringa)."""
    if not modello or not dischi_lhm:
        return {}
    m_low = modello.strip().lower()
    if m_low in dischi_lhm:
        return dischi_lhm[m_low]
    for k, val in dischi_lhm.items():
        if m_low in k or k in m_low:
            return val
    return {}


def _valuta_salute_disco(info_disco: dict, sensori_lhm: dict) -> dict:
    """Calcola stato salute stile CrystalDiskInfo ('Good', 'Caution', 'Bad', 'Unknown') da Health Windows, vita SSD, S.M.A.R.T. e temperatura."""
    health_win = str(info_disco.get("health_win") or "Unknown")
    tipo = str(info_disco.get("tipo") or "HDD").upper()
    is_ssd = tipo == "SSD" or str(info_disco.get("bus") or "").upper() == "NVME"
    temp_warn = DISK_TEMP_WARN_SSD if is_ssd else DISK_TEMP_WARN_HDD
    temp_crit = DISK_TEMP_CRIT_SSD if is_ssd else DISK_TEMP_CRIT_HDD

    temp_num = sensori_lhm.get("temp_num")
    life_pct = sensori_lhm.get("life_percent")
    reallocated = sensori_lhm.get("reallocated", 0) or 0
    pending = sensori_lhm.get("pending", 0) or 0
    uncorrectable = sensori_lhm.get("uncorrectable", 0) or 0

    motivi = []
    stato = "Good" if health_win.lower() == "healthy" else "Unknown"

    if health_win.lower() in ("unhealthy", "failed"):
        stato = "Bad"
        motivi.append(f"Windows: {health_win}")
    elif health_win.lower() in ("warning", "degraded"):
        stato = "Caution"
        motivi.append(f"Windows: {health_win}")

    if uncorrectable > 0 or reallocated >= 10:
        stato = "Bad"
        motivi.append("errori S.M.A.R.T.")
    elif reallocated > 0 or pending > 0:
        if stato != "Bad":
            stato = "Caution"
        motivi.append("settori riallocati/pendenti")

    if life_pct is not None:
        if life_pct <= 10:
            stato = "Bad"
            motivi.append(f"vita {life_pct}%")
        elif life_pct <= 30:
            if stato != "Bad":
                stato = "Caution"
            motivi.append(f"vita {life_pct}%")

    if temp_num is not None:
        if temp_num >= temp_crit:
            stato = "Bad"
            motivi.append(f"Temp {temp_num}°C")
        elif temp_num >= temp_warn:
            if stato != "Bad":
                stato = "Caution"
            motivi.append(f"Temp {temp_num}°C")

    if stato == "Good" and life_pct is not None:
        etichetta = f"Good {life_pct}%"
    elif motivi:
        etichetta = f"{stato} ({', '.join(motivi)})"
    else:
        etichetta = stato

    return {
        "stato": stato,
        "etichetta": etichetta,
        "etichetta_breve": f"Good {life_pct}%" if (stato == "Good" and life_pct is not None) else stato,
        "temp_num": temp_num,
        "temperatura_c": sensori_lhm.get("temperatura_c", "N/D"),
        "temp_alta": temp_num is not None and temp_num >= temp_warn,
        "life_percent": life_pct,
        "power_on_hours": sensori_lhm.get("power_on_hours"),
        "data_written_gb": sensori_lhm.get("data_written_gb"),
        "modello": info_disco.get("modello", ""),
        "tipo": info_disco.get("tipo", ""),
        "bus": info_disco.get("bus", ""),
        "health_win": health_win,
    }


def stato_salute_dischi(mappa_info: dict | None = None, dischi_lhm: dict | None = None) -> dict:
    """Restituisce temperatura e stato salute stile CrystalDiskInfo (Good/Caution/Bad) per ogni lettera di unità montata."""
    info_map = mappa_info if mappa_info is not None else mappa_info_dischi_fisici()
    lhm_map = dischi_lhm if dischi_lhm is not None else leggi_sensori_lhm().get("dischi_lhm", {})
    risultato = {}
    for lettera, info in info_map.items():
        sens = _abbina_lhm_disco(info.get("modello", ""), lhm_map)
        risultato[lettera] = _valuta_salute_disco(info, sens)
    return risultato


def mappa_dischi_fisici(lettere=None) -> dict:
    """Associa le lettere di unità (es. C, D, E, ...) al rispettivo PhysicalDriveX di Windows."""
    mappa = {}
    try:
        ps_cmd = 'Get-Partition | Where-Object {$_.DriveLetter} | ForEach-Object {"$($_.DriveLetter):PhysicalDrive$($_.DiskNumber)"}'
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=10, creationflags=NO_WINDOW
        ).strip()
        for riga in output.splitlines():
            if ":" in riga:
                lettera, drive = riga.split(":", 1)
                lettera = lettera.strip().upper()
                if lettere is None or lettera in lettere:
                    mappa[lettera] = drive.strip()
    except Exception:
        pass
    return mappa

def info_versioni_sistema() -> dict:
    """Legge versione di Windows 11 installata (da registro) e versione del driver grafico NVIDIA."""
    win_str = "Windows 11 (N/D)"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            product = winreg.QueryValueEx(key, "ProductName")[0]
            try:
                display_ver = winreg.QueryValueEx(key, "DisplayVersion")[0]
            except OSError:
                display_ver = ""
            build = winreg.QueryValueEx(key, "CurrentBuild")[0]
            try:
                ubr = winreg.QueryValueEx(key, "UBR")[0]
            except OSError:
                ubr = None
            try:
                if int(build) >= 22000 and "Windows 10" in product:
                    product = product.replace("Windows 10", "Windows 11")
            except ValueError:
                pass
            build_full = f"{build}.{ubr}" if ubr is not None else str(build)
            ver_part = f" {display_ver}" if display_ver else ""
            win_str = f"{product}{ver_part} (Build {build_full})"
    except Exception:
        pass

    driver_str = "N/D"
    try:
        smi = _trova_nvidia_smi()
        out = subprocess.check_output(
            [smi, "--query-gpu=driver_version", "--format=csv,noheader"],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
        ).strip()
        if out:
            driver_str = out.splitlines()[0].strip()
    except Exception:
        pass

    return {"windows": win_str, "driver_gpu": driver_str}

def info_cpu_nome() -> str:
    """Legge il nome del processore installato dal registro di Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except Exception:
        return "CPU Windows"

def info_banchi_ram() -> dict:
    """Legge i dettagli hardware di tutti i banchi RAM installati (slot, GB, DDR, frequenza MHz, voltaggio, codice)."""
    tipi_ddr = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
    banchi = []
    try:
        ps_cmd = (
            "Get-CimInstance Win32_PhysicalMemory | "
            "Select-Object BankLabel, DeviceLocator, PartNumber, Capacity, Speed, "
            "ConfiguredClockSpeed, ConfiguredVoltage, SMBIOSMemoryType | ConvertTo-Json -Compress"
        )
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            encoding="utf-8", stderr=subprocess.DEVNULL, timeout=10, creationflags=NO_WINDOW
        ).strip()
        if output:
            dati = json.loads(output)
            if isinstance(dati, dict):
                dati = [dati]
            for item in dati:
                cap_bytes = item.get("Capacity") or 0
                gb = round(cap_bytes / (1024**3))
                freq = item.get("ConfiguredClockSpeed") or item.get("Speed") or 0
                volt_mv = item.get("ConfiguredVoltage") or 0
                volt_str = f"{volt_mv / 1000:.2f}V" if volt_mv else "N/D"
                smbios_type = item.get("SMBIOSMemoryType") or 0
                tipo = tipi_ddr.get(smbios_type, "RAM")
                locator = (item.get("DeviceLocator") or item.get("BankLabel") or "DIMM").strip()
                slot_breve = locator.replace("Channel", "Ch").replace("DIMM_", "DIMM")
                part = (item.get("PartNumber") or "").strip()
                banchi.append({
                    "bank": (item.get("BankLabel") or "").strip(),
                    "slot": locator,
                    "slot_breve": slot_breve,
                    "gb": gb,
                    "tipo": tipo,
                    "frequenza_mhz": int(freq) if freq else 0,
                    "voltaggio": volt_str,
                    "part_number": part
                })
    except Exception:
        pass

    canali = set()
    for b in banchi:
        m = re.search(r"Channel\s*([A-Za-z0-9]+)", b["slot"], re.IGNORECASE)
        if m:
            canali.add(m.group(1).upper())
    if len(canali) >= 2:
        modalita = "Dual Channel" if len(canali) == 2 else f"{len(canali)}-Channel"
    elif len(banchi) == 1 or len(canali) == 1:
        modalita = "Single Channel"
    else:
        modalita = f"{len(banchi)} banchi" if banchi else "N/D"

    freq_attiva = banchi[0]["frequenza_mhz"] if banchi else 0
    tipo_ram = banchi[0]["tipo"] if banchi else "RAM"
    return {
        "banchi": banchi,
        "frequenza_mhz": freq_attiva,
        "tipo": tipo_ram,
        "modalita_canale": modalita,
        "totale_gb": sum(b["gb"] for b in banchi)
    }

def info_rete_attiva() -> dict:
    """Rileva l'interfaccia di rete attiva principale (nome, IPv4, velocità link in Mbps)."""
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        migliore = None
        for nome, st in stats.items():
            if not st.isup or "loopback" in nome.lower():
                continue
            ipv4_list = [
                a.address for a in addrs.get(nome, [])
                if a.family == socket.AF_INET and not a.address.startswith("169.254.")
            ]
            if ipv4_list:
                info = {"nome": nome, "ip": ipv4_list[0], "link_mbps": st.speed}
                if migliore is None or (st.speed > migliore["link_mbps"]):
                    migliore = info
        if migliore:
            return migliore
    except Exception:
        pass
    return {"nome": "Offline", "ip": "N/D", "link_mbps": 0}

def formatta_velocita_rete(bytes_sec: float) -> str:
    """Formatta byte/s in Mbps o Kbps leggibili."""
    bps = max(bytes_sec, 0.0) * 8.0
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mbps"
    return f"{bps / 1_000:.1f} Kbps"

def misura_ping(host: str = "1.1.1.1") -> dict:
    """Misura la latenza di rete (ping in ms) verso un host valido (default 1.1.1.1)."""
    host_clean = str(host).strip()
    if not host_clean or host_clean.startswith(("-", "/")) or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host_clean):
        return {"host": host_clean, "ms": None, "stato": "Host non valido"}
    try:
        out = subprocess.check_output(
            ["ping", "-n", "1", "-w", "1000", host_clean],
            encoding="cp850", errors="ignore", stderr=subprocess.DEVNULL, timeout=3, creationflags=NO_WINDOW
        )
        m = re.search(r"(?:durata|time)\s*([<=])\s*(\d+)\s*ms", out, re.IGNORECASE)
        if m:
            op, val = m.group(1), int(m.group(2))
            stato = f"<{val} ms" if op == "<" else f"{val} ms"
            return {"host": host_clean, "ms": val, "stato": stato}
        return {"host": host_clean, "ms": None, "stato": "Timeout"}
    except Exception:
        return {"host": host_clean, "ms": None, "stato": "N/D"}

def piano_energetico_attivo() -> dict:
    """Rileva il piano energetico di Windows attualmente attivo."""
    try:
        out = subprocess.check_output(
            ["powercfg", "/getactivescheme"],
            encoding="cp850", errors="ignore", stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
        ).strip()
        m_guid = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", out)
        m_nome = re.search(r"\((.+)\)", out)
        guid = m_guid.group(1) if m_guid else ""
        nome = m_nome.group(1).strip() if m_nome else out
        nome_low = nome.lower()
        if any(k in nome_low for k in ("eccellenti", "elevate", "ultimate", "high performance")):
            modalita = "gaming"
        elif any(k in nome_low for k in ("bilanciato", "balanced")):
            modalita = "bilanciato"
        else:
            modalita = "altro"
        return {"guid": guid, "nome": nome, "modalita": modalita}
    except Exception:
        return {"guid": "", "nome": "N/D", "modalita": "altro"}

def _dimensione_cartella_bytes(percorso: str) -> int:
    """Calcola la dimensione totale in byte di una cartella ignorando errori di permessi."""
    tot = 0
    stack = [percorso]
    while stack:
        curr = stack.pop()
        try:
            with os.scandir(curr) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            tot += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        pass
        except OSError:
            pass
    return tot

def maschera_percorso_utente(testo: str) -> str:
    """Sostituisce la cartella home utente (es. C:\\Users\\Nome) con %USERPROFILE% per tutelare la privacy."""
    if not testo:
        return testo
    home = os.path.expanduser("~")
    if home and len(home) > 3:
        return re.sub(re.escape(home), "%USERPROFILE%", str(testo), flags=re.IGNORECASE)
    return str(testo)


def analizza_spazio_disco(unita: str = "C:") -> dict:
    """Analizza le principali cartelle cache/utente sul disco indicato (es. 'C:') per individuare cosa occupa spazio."""
    unita_norm = str(unita).strip().rstrip("\\").upper()
    if len(unita_norm) == 1 and unita_norm.isalpha():
        unita_norm += ":"
    if not re.fullmatch(r"[A-Z]:", unita_norm) or not os.path.exists(unita_norm + "\\"):
        return {
            "unita": unita_norm,
            "errore": f"Unità '{unita}' non valida o non accessibile.",
            "cartelle_analizzate": []
        }
    user_home = os.path.expanduser("~")
    win_dir = os.environ.get("SystemRoot", r"C:\Windows")
    candidati = [
        ("File Temporanei Utente", tempfile.gettempdir()),
        ("Windows Temp", os.path.join(win_dir, "Temp")),
        ("Windows Update Cache", os.path.join(win_dir, r"SoftwareDistribution\Download")),
        ("NVIDIA DXCache", os.path.join(user_home, r"AppData\Local\NVIDIA\DXCache")),
        ("NVIDIA GLCache", os.path.join(user_home, r"AppData\Local\NVIDIA\GLCache")),
        ("Download Utente", os.path.join(user_home, "Downloads")),
    ]
    risultati = []
    for etichetta, path in candidati:
        if path.upper().startswith(unita_norm) and os.path.exists(path):
            mb = round(_dimensione_cartella_bytes(path) / (1024 * 1024), 1)
            risultati.append({"cartella": etichetta, "percorso": maschera_percorso_utente(path), "mb": mb})
    risultati.sort(key=lambda x: x["mb"], reverse=True)
    uso = psutil.disk_usage(unita_norm + "\\")
    return {
        "unita": unita_norm,
        "percent": uso.percent,
        "liberi_gb": round(uso.free / (1024**3), 1),
        "totali_gb": round(uso.total / (1024**3), 1),
        "cartelle_analizzate": risultati
    }

_PROCESSI_SISTEMA_PROTETTI = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
    "dwm.exe", "explorer.exe", "taskmgr.exe", "audiodg.exe", "fontdrvhost.exe",
    "memory compression", "sihost.exe", "ctfmon.exe", "searchhost.exe",
    "librehardwaremonitor.exe"
}

def termina_processo(target: str) -> str:
    """Termina in modo sicuro un processo dato il suo PID numerico o il nome esatto (es. 'notepad.exe'). Blocca sempre processi di sistema e protetti."""
    target_str = str(target).strip()
    if not target_str or any(c in target_str for c in ("\\", "/", ";", "&", "|", "`", "$", "\n", "\r")):
        return "Specificare un PID numerico o un nome processo valido (senza percorsi o metacaratteri)."

    bloccati = PROTECTED_PROCESSES | _PROCESSI_SISTEMA_PROTETTI
    mio_pid = os.getpid()

    if target_str.isdigit():
        pid = int(target_str)
        if pid == mio_pid:
            return "Operazione bloccata: non posso terminare me stesso."
        try:
            p = psutil.Process(pid)
            nome = p.name()
            if nome.lower() in bloccati:
                return f"Operazione bloccata: '{nome}' (PID {pid}) è un processo protetto o di sistema."
            p.terminate()
            return f"Processo '{nome}' (PID {pid}) terminato correttamente."
        except psutil.NoSuchProcess:
            return f"Nessun processo trovato con PID {pid}."
        except psutil.AccessDenied:
            return f"Permessi insufficienti per terminare il PID {pid}."
        except Exception as e:
            return f"Errore durante la terminazione del PID {pid}: {e}"

    nome_target = target_str.lower()
    if not nome_target.endswith(".exe"):
        nome_target_exe = nome_target + ".exe"
    else:
        nome_target_exe = nome_target

    if nome_target in bloccati or nome_target_exe in bloccati:
        return f"Operazione bloccata: '{target_str}' è un processo protetto o di sistema."

    terminati = 0
    errori_permessi = 0
    for p in psutil.process_iter(['pid', 'name']):
        try:
            nome = (p.info['name'] or "").lower()
            if nome in (nome_target, nome_target_exe):
                if p.info['pid'] == mio_pid:
                    continue
                p.terminate()
                terminati += 1
        except psutil.AccessDenied:
            errori_permessi += 1
        except psutil.NoSuchProcess:
            pass

    if terminati > 0:
        extra = f" ({errori_permessi} istanze non terminate per permessi insufficienti)" if errori_permessi else ""
        return f"Terminati {terminati} processi '{target_str}'{extra}."
    if errori_permessi > 0:
        return f"Permessi insufficienti per terminare '{target_str}'."
    return f"Nessun processo attivo trovato con nome '{target_str}'."

def monitora_archiviazione() -> list:
    """Legge spazio usato, libero e percentuale di tutte le partizioni fisse."""
    dischi = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or part.fstype == "":
            continue
        try:
            uso = psutil.disk_usage(part.mountpoint)
            dischi.append({
                "unita": part.device,
                "usati_gb": round(uso.used / (1024**3), 1),
                "liberi_gb": round(uso.free / (1024**3), 1),
                "totali_gb": round(uso.total / (1024**3), 1),
                "percent": uso.percent
            })
        except PermissionError:
            continue
    return dischi

def elenca_app_avvio() -> dict:
    """Elenca i programmi configurati per avviarsi automaticamente con Windows (Utente e Sistema)."""
    percorso = r"Software\Microsoft\Windows\CurrentVersion\Run"
    risultato = {"utente_corrente": {}, "sistema": {}}
    for chiave_root, etichetta in [(winreg.HKEY_CURRENT_USER, "utente_corrente"), (winreg.HKEY_LOCAL_MACHINE, "sistema")]:
        try:
            with winreg.OpenKey(chiave_root, percorso, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        nome, valore, _ = winreg.EnumValue(key, i)
                        risultato[etichetta][nome] = maschera_percorso_utente(str(valore))
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass
    return risultato

def disabilita_app_avvio(nome_app: str) -> str:
    """Rimuove un'app dall'avvio automatico dell'utente corrente (HKCU Run) usando il nome esatto."""
    percorso = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, percorso, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, nome_app)
        return f"'{nome_app}' rimossa correttamente dall'avvio automatico."
    except FileNotFoundError:
        return f"'{nome_app}' non trovata tra le app utente. Se è un'app di sistema (HKLM), disattivala da Gestione Attività > App di avvio."
    except Exception as e:
        return f"Errore durante la rimozione di '{nome_app}': {e}"

def _trova_o_crea_prestazioni_eccellenti() -> str | None:
    """Trova il GUID del piano 'Prestazioni eccellenti' o lo sblocca se nascosto."""
    try:
        out = subprocess.check_output(
            ["powercfg", "/list"], encoding="cp850", errors="ignore", timeout=5, creationflags=NO_WINDOW
        )
        for riga in out.splitlines():
            if "eccellenti" in riga.lower() or "ultimate performance" in riga.lower():
                m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", riga)
                if m:
                    return m.group(1)

        # Se non esiste ancora, lo sblocca duplicando il modello di sistema
        dup = subprocess.check_output(
            ["powercfg", "-duplicatescheme", "e9a42b02-d5df-448d-aa00-03f14749eb61"],
            encoding="cp850", errors="ignore", timeout=5, creationflags=NO_WINDOW
        )
        m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", dup)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_POWERCFG_GAMING_TWEAKS = (
    ("USB Suspend OFF", "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0"),
    ("PCIe Power Mgmt OFF", "501a4d13-42af-4429-9fd1-a8218c268e20", "ee12f906-d277-404b-b6da-e5fa1a576df5", "0"),
    ("Disk Standby OFF", "0012ee47-9041-4b5d-9b77-535fba8b1442", "6738e2c4-e8a5-4a42-b16a-e040e769756e", "0"),
    ("CPU Core Unpark 100%", "54533251-82be-4824-96c1-47b60b740d00", "0cc5b647-c1df-4637-891a-dec35c318583", "100"),
)

_GAMING_REG_SETTINGS = (
    ("Windows Game Mode ON", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1),
    ("Windows Game Mode Allow", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1),
    ("Game DVR OFF", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0),
    ("Game DVR Store OFF", r"System\GameConfigStore", "GameDVR_Enabled", 0),
    ("Notifiche Toast OFF", r"Software\Microsoft\Windows\CurrentVersion\PushNotifications", "ToastEnabled", 0),
    ("Non Disturbare ON", r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings", "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 0),
    ("Suoni Notifiche OFF", r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings", "NOC_GLOBAL_SETTING_ALLOW_NOTIFICATION_SOUND", 0),
    ("Trasparenze DWM OFF", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0),
    ("Effetti Visivi Ridotti", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2),
)

_GAMING_REG_SNAPSHOT: dict[tuple[str, str], tuple[bool, int | None]] = {}


def _carica_gaming_state() -> dict:
    """Carica lo snapshot persistente della Gaming Mode da disco (se presente)."""
    try:
        if os.path.isfile(GAMING_STATE_FILE):
            with open(GAMING_STATE_FILE, "r", encoding="utf-8") as f:
                dati = json.load(f)
                if isinstance(dati, dict):
                    return dati
    except Exception:
        pass
    return {}


def _salva_gaming_state(stato: dict) -> None:
    """Salva lo snapshot persistente della Gaming Mode su disco (o rimuove il file se vuoto)."""
    if not stato:
        _rimuovi_gaming_state()
        return
    try:
        os.makedirs(os.path.dirname(GAMING_STATE_FILE), exist_ok=True)
        with open(GAMING_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(stato, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _rimuovi_gaming_state() -> None:
    """Elimina il file di snapshot della Gaming Mode se presente."""
    try:
        if os.path.isfile(GAMING_STATE_FILE):
            os.remove(GAMING_STATE_FILE)
    except Exception:
        pass


def _ottimizza_piano_gaming(guid: str) -> list[str]:
    """Applica il tuning fino via powercfg al piano Gaming (USB, PCIe, Disk Standby)."""
    if not guid or not _UUID_RE.fullmatch(guid):
        return []
    applicati = []
    for etichetta, sub_guid, setting_guid, valore in _POWERCFG_GAMING_TWEAKS:
        try:
            res = subprocess.run(
                ["powercfg", "/setacvalueindex", guid, sub_guid, setting_guid, valore],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
            )
            if res.returncode == 0:
                applicati.append(etichetta)
        except Exception:
            pass
    return applicati


_DIRECTX_PREFS_PATH = r"Software\Microsoft\DirectX\UserGpuPreferences"
_DIRECTX_GLOBAL_VAL = "DirectXUserGlobalSettings"


def _parse_directx_global_settings(raw: str) -> dict[str, str]:
    """Parsa la stringa DirectXUserGlobalSettings (es. 'SwapEffectUpgradeEnable=1;VRROptimizeEnable=1;')."""
    risultato: dict[str, str] = {}
    for token in str(raw or "").split(";"):
        token = token.strip()
        if "=" in token:
            k, v = token.split("=", 1)
            k = k.strip()
            if k:
                risultato[k] = v.strip()
    return risultato


def _leggi_vrr_attivo() -> bool | None:
    """Verifica se VRR di Windows (VRROptimizeEnable=1) è attivo in HKCU."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _DIRECTX_PREFS_PATH, 0, winreg.KEY_READ) as key:
            raw, _ = winreg.QueryValueEx(key, _DIRECTX_GLOBAL_VAL)
            settings = _parse_directx_global_settings(str(raw))
            return settings.get("VRROptimizeEnable") == "1"
    except FileNotFoundError:
        return False
    except Exception:
        return None


def abilita_vrr_windows() -> bool:
    """Abilita VRR (VRROptimizeEnable=1) e Ottimizzazioni giochi in finestra (SwapEffectUpgradeEnable=1) su HKCU senza UAC."""
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, _DIRECTX_PREFS_PATH, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
        ) as key:
            try:
                raw, _ = winreg.QueryValueEx(key, _DIRECTX_GLOBAL_VAL)
            except FileNotFoundError:
                raw = ""
            settings = _parse_directx_global_settings(str(raw))
            settings["SwapEffectUpgradeEnable"] = "1"
            settings["VRROptimizeEnable"] = "1"
            nuova_str = "".join(f"{k}={v};" for k, v in settings.items())
            winreg.SetValueEx(key, _DIRECTX_GLOBAL_VAL, 0, winreg.REG_SZ, nuova_str)
            return True
    except Exception:
        return False


def _imposta_animazioni_ui(attive: bool) -> bool:
    """Disattiva o riattiva le animazioni dell'area client di Windows via SystemParametersInfoW (senza UAC)."""
    try:
        # SPI_SETCLIENTAREAANIMATION = 0x1043, SPIF_SENDCHANGE = 0x0002
        return bool(ctypes.windll.user32.SystemParametersInfoW(0x1043, 0, ctypes.c_void_p(1 if attive else 0), 0x0002))
    except Exception:
        return False


def applica_ottimizzazioni_registro_gaming() -> list[str]:
    """Applica ottimizzazioni Windows Gaming su HKCU (senza UAC) salvando lo stato precedente anche su disco."""
    stato = _carica_gaming_state()
    reg_disk = stato.get("reg_snapshot")
    if isinstance(reg_disk, dict):
        for k_str, val in reg_disk.items():
            if "|" in k_str and isinstance(val, list) and len(val) == 2:
                sub, name = k_str.split("|", 1)
                _GAMING_REG_SNAPSHOT.setdefault((sub, name), (bool(val[0]), val[1]))

    applicati = []
    for etichetta, subpath, val_name, target_val in _GAMING_REG_SETTINGS:
        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, subpath, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
            ) as key:
                snap_key = (subpath, val_name)
                if snap_key not in _GAMING_REG_SNAPSHOT:
                    try:
                        prev_val, _ = winreg.QueryValueEx(key, val_name)
                        _GAMING_REG_SNAPSHOT[snap_key] = (True, int(prev_val))
                    except (FileNotFoundError, OSError, ValueError, TypeError):
                        _GAMING_REG_SNAPSHOT[snap_key] = (False, None)
                winreg.SetValueEx(key, val_name, 0, winreg.REG_DWORD, target_val)
                applicati.append(etichetta)
        except Exception:
            pass

    if _imposta_animazioni_ui(False):
        applicati.append("Animazioni UI OFF")

    if abilita_vrr_windows():
        applicati.append("VRR & Windowed Opt ON")

    if _GAMING_REG_SNAPSHOT:
        stato["reg_snapshot"] = {
            f"{sub}|{name}": [esisteva, prev_val]
            for (sub, name), (esisteva, prev_val) in _GAMING_REG_SNAPSHOT.items()
        }
        _salva_gaming_state(stato)
    return applicati


def ripristina_ottimizzazioni_registro_gaming() -> int:
    """Ripristina le chiavi HKCU modificate dalla Gaming Mode (anche dopo riavvio dell'app)."""
    stato = _carica_gaming_state()
    if not _GAMING_REG_SNAPSHOT:
        reg_disk = stato.get("reg_snapshot")
        if isinstance(reg_disk, dict):
            for k_str, val in reg_disk.items():
                if "|" in k_str and isinstance(val, list) and len(val) == 2:
                    sub, name = k_str.split("|", 1)
                    _GAMING_REG_SNAPSHOT[(sub, name)] = (bool(val[0]), val[1])

    ripristinati = 0
    for (subpath, val_name), (esisteva, prev_val) in list(_GAMING_REG_SNAPSHOT.items()):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subpath, 0, winreg.KEY_SET_VALUE) as key:
                if esisteva and prev_val is not None:
                    winreg.SetValueEx(key, val_name, 0, winreg.REG_DWORD, prev_val)
                else:
                    try:
                        winreg.DeleteValue(key, val_name)
                    except FileNotFoundError:
                        pass
                ripristinati += 1
        except Exception:
            pass
    _GAMING_REG_SNAPSHOT.clear()
    _imposta_animazioni_ui(True)
    if "reg_snapshot" in stato:
        stato.pop("reg_snapshot", None)
        _salva_gaming_state(stato)
    return ripristinati


_ANTICHEAT_MAI_TOCCARE = {
    "vgc.exe", "vgtray.exe",
    "riotclientservices.exe", "riotclientux.exe", "riotclientuxrender.exe",
}

_NVAPI_FRL_FPS_ID = 0x10835002
_NVAPI_IDS = {
    "Init": 0x0150E828,
    "CreateSession": 0x0694D52E,
    "DestroySession": 0xDAD9CFF8,
    "LoadSettings": 0x375DBD6B,
    "SaveSettings": 0xFCBC7E14,
    "GetBaseProfile": 0xDA8466A0,
    "GetSetting": 0x73BF8338,
    "SetSetting": 0x577DD202,
    "DeleteProfileSetting": 0xE4A26362,
}


class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_uint16),
        ("dmDriverVersion", ctypes.c_uint16),
        ("dmSize", ctypes.c_uint16),
        ("dmDriverExtra", ctypes.c_uint16),
        ("dmFields", ctypes.c_uint32),
        ("dmPositionX", ctypes.c_int32),
        ("dmPositionY", ctypes.c_int32),
        ("dmDisplayOrientation", ctypes.c_uint32),
        ("dmDisplayFixedOutput", ctypes.c_uint32),
        ("dmColor", ctypes.c_int16),
        ("dmDuplex", ctypes.c_int16),
        ("dmYResolution", ctypes.c_int16),
        ("dmTTOption", ctypes.c_int16),
        ("dmCollate", ctypes.c_int16),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_uint16),
        ("dmBitsPerPel", ctypes.c_uint32),
        ("dmPelsWidth", ctypes.c_uint32),
        ("dmPelsHeight", ctypes.c_uint32),
        ("dmDisplayFlags", ctypes.c_uint32),
        ("dmDisplayFrequency", ctypes.c_uint32),
        ("dmICMMethod", ctypes.c_uint32),
        ("dmICMIntent", ctypes.c_uint32),
        ("dmMediaType", ctypes.c_uint32),
        ("dmDitherType", ctypes.c_uint32),
        ("dmReserved1", ctypes.c_uint32),
        ("dmReserved2", ctypes.c_uint32),
        ("dmPanningWidth", ctypes.c_uint32),
        ("dmPanningHeight", ctypes.c_uint32),
    ]


class _NVDRS_BINARY_SETTING(ctypes.Structure):
    _fields_ = [("valueLength", ctypes.c_uint32), ("valueData", ctypes.c_ubyte * 4096)]


class _NVDRS_SETTING_UNION(ctypes.Union):
    _fields_ = [
        ("u32Value", ctypes.c_uint32),
        ("binaryValue", _NVDRS_BINARY_SETTING),
        ("wszValue", ctypes.c_uint16 * 2048),
    ]


class _NVDRS_SETTING(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint32),
        ("settingName", ctypes.c_uint16 * 2048),
        ("settingId", ctypes.c_uint32),
        ("settingType", ctypes.c_uint32),
        ("settingLocation", ctypes.c_uint32),
        ("isCurrentPredefined", ctypes.c_uint32),
        ("isPredefinedValid", ctypes.c_uint32),
        ("predefined", _NVDRS_SETTING_UNION),
        ("current", _NVDRS_SETTING_UNION),
    ]


def info_monitor_principale() -> dict:
    """Rileva risoluzione, refresh rate (Hz) e presenza di risoluzioni DSR/DLDSR sul monitor principale."""
    try:
        user32 = ctypes.windll.user32
        dm_curr = _DEVMODEW()
        dm_curr.dmSize = ctypes.sizeof(_DEVMODEW)
        # ENUM_CURRENT_SETTINGS = -1
        if not user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm_curr)):
            return {"larghezza": 0, "altezza": 0, "refresh_hz": 0, "risoluzioni_dldsr": [], "dldsr_attivo": False}

        w = int(dm_curr.dmPelsWidth)
        h = int(dm_curr.dmPelsHeight)
        hz = int(dm_curr.dmDisplayFrequency)
        curr_pixels = w * h

        superiori = set()
        idx = 0
        while idx < 512:
            dm = _DEVMODEW()
            dm.dmSize = ctypes.sizeof(_DEVMODEW)
            if not user32.EnumDisplaySettingsW(None, idx, ctypes.byref(dm)):
                break
            mw, mh = int(dm.dmPelsWidth), int(dm.dmPelsHeight)
            if mw * mh > curr_pixels:
                superiori.add((mw, mh))
            idx += 1

        risoluzioni_sup = [f"{mw}x{mh}" for mw, mh in sorted(superiori)]
        return {
            "larghezza": w,
            "altezza": h,
            "refresh_hz": hz,
            "risoluzioni_dldsr": risoluzioni_sup,
            "dldsr_attivo": bool(risoluzioni_sup),
        }
    except Exception:
        return {"larghezza": 0, "altezza": 0, "refresh_hz": 0, "risoluzioni_dldsr": [], "dldsr_attivo": False}


def _nvapi_drs_frl_fps(azione: str, valore: int | None = None) -> tuple[bool, int | None]:
    """Legge ('get'), imposta ('set') o rimuove ('delete') il Max Frame Rate globale NVIDIA (FRL_FPS) via nvapi64.dll senza UAC."""
    try:
        nvapi = ctypes.WinDLL("nvapi64.dll")
        qi = nvapi.nvapi_QueryInterface
        qi.argtypes = [ctypes.c_uint32]
        qi.restype = ctypes.c_void_p

        ptrs = {k: qi(v) for k, v in _NVAPI_IDS.items()}
        if not all(ptrs.values()):
            return False, None

        c_init = ctypes.CFUNCTYPE(ctypes.c_int)(ptrs["Init"])
        c_create = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(ptrs["CreateSession"])
        c_destroy = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(ptrs["DestroySession"])
        c_load = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(ptrs["LoadSettings"])
        c_save = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(ptrs["SaveSettings"])
        c_base = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(ptrs["GetBaseProfile"])
        c_get = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_NVDRS_SETTING))(ptrs["GetSetting"])
        c_set = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_NVDRS_SETTING))(ptrs["SetSetting"])
        c_del = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32)(ptrs["DeleteProfileSetting"])

        if c_init() != 0:
            return False, None
        h_session = ctypes.c_void_p()
        if c_create(ctypes.byref(h_session)) != 0:
            return False, None
        try:
            if c_load(h_session) != 0:
                return False, None
            h_profile = ctypes.c_void_p()
            if c_base(h_session, ctypes.byref(h_profile)) != 0:
                return False, None

            setting = _NVDRS_SETTING()
            setting.version = ctypes.sizeof(_NVDRS_SETTING) | (1 << 16)

            if azione == "get":
                st = c_get(h_session, h_profile, _NVAPI_FRL_FPS_ID, ctypes.byref(setting))
                if st == 0:
                    return True, int(setting.current.u32Value)
                if st == -160:  # NVAPI_SETTING_NOT_FOUND
                    return True, None
                return False, None

            if azione == "set":
                fps_val = max(int(valore or 0), 0)
                setting.settingId = _NVAPI_FRL_FPS_ID
                setting.settingType = 0
                setting.current.u32Value = fps_val
                if c_set(h_session, h_profile, ctypes.byref(setting)) != 0:
                    return False, None
                return c_save(h_session) == 0, fps_val

            if azione == "delete":
                st = c_del(h_session, h_profile, _NVAPI_FRL_FPS_ID)
                if st not in (0, -160):
                    return False, None
                return c_save(h_session) == 0, None

            return False, None
        finally:
            c_destroy(h_session)
    except Exception:
        return False, None


def applica_fps_cap_gaming(monitor_info: dict | None = None) -> dict:
    """Imposta il Max Frame Rate NVIDIA globale a (refresh_hz - FPS_CAP_MARGIN_HZ) in base al monitor principale, salvando lo stato precedente."""
    mon = monitor_info if monitor_info is not None else info_monitor_principale()
    hz = int(mon.get("refresh_hz") or 0)
    w = int(mon.get("larghezza") or 0)
    h = int(mon.get("altezza") or 0)
    if hz < 35:
        return {"applicato": False, "target_fps": 0, "refresh_hz": hz, "messaggio": ""}

    target_fps = max(hz - FPS_CAP_MARGIN_HZ, FPS_CAP_MIN)
    ok_get, prev_val = _nvapi_drs_frl_fps("get")
    if not ok_get:
        return {"applicato": False, "target_fps": target_fps, "refresh_hz": hz, "messaggio": ""}

    stato = _carica_gaming_state()
    if "prev_nvidia_frl_fps" not in stato:
        stato["prev_nvidia_frl_fps"] = {
            "esisteva": prev_val is not None,
            "valore": prev_val,
        }
        _salva_gaming_state(stato)

    ok_set, _ = _nvapi_drs_frl_fps("set", target_fps)
    if not ok_set:
        return {"applicato": False, "target_fps": target_fps, "refresh_hz": hz, "messaggio": ""}

    res_str = f"{w}x{h} @ {hz} Hz" if (w and h) else f"{hz} Hz"
    return {
        "applicato": True,
        "target_fps": target_fps,
        "refresh_hz": hz,
        "messaggio": f"Limite FPS NVIDIA (Max Frame Rate): {target_fps} FPS (monitor principale {res_str}, margine -{FPS_CAP_MARGIN_HZ} Hz).",
    }


def ripristina_fps_cap_gaming() -> str:
    """Ripristina il Max Frame Rate NVIDIA precedente salvato prima della Gaming Mode (anche dopo riavvio dell'app)."""
    stato = _carica_gaming_state()
    snap = stato.get("prev_nvidia_frl_fps")
    if not isinstance(snap, dict):
        return ""

    esisteva = bool(snap.get("esisteva"))
    prev_val = snap.get("valore")
    if esisteva and isinstance(prev_val, int) and prev_val > 0:
        ok, _ = _nvapi_drs_frl_fps("set", prev_val)
        esito = f" Limite FPS NVIDIA ripristinato a {prev_val} FPS." if ok else ""
    else:
        ok, _ = _nvapi_drs_frl_fps("delete")
        esito = " Limite FPS NVIDIA rimosso (Disattivato)." if ok else ""

    stato.pop("prev_nvidia_frl_fps", None)
    _salva_gaming_state(stato)
    return esito


def apri_pannello_nvidia() -> bool:
    """Apre il Pannello di Controllo NVIDIA in modo sicuro (senza shell)."""
    try:
        subprocess.Popen(
            ["explorer.exe", r"shell:AppsFolder\NVIDIACorp.NVIDIAControlPanel_56jybvy8sckqj!NVIDIACorp.NVIDIAControlPanel"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
        )
        return True
    except Exception:
        try:
            nvcpl = r"C:\Program Files\NVIDIA Corporation\Control Panel Client\nvcplui.exe"
            if os.path.exists(nvcpl):
                subprocess.Popen([nvcpl], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        except Exception:
            pass
    return False


def imposta_priorita_background_gaming(bassa: bool) -> list[str]:
    """Abbassa a BELOW_NORMAL (o ripristina a NORMAL) la priorità CPU dei processi background in GAMING_THROTTLE_PROCESSES senza chiuderli."""
    target = psutil.BELOW_NORMAL_PRIORITY_CLASS if bassa else psutil.NORMAL_PRIORITY_CLASS
    esclusi = _PROCESSI_SISTEMA_PROTETTI | _ANTICHEAT_MAI_TOCCARE
    modificati = set()
    for p in psutil.process_iter(['name']):
        try:
            nome = p.info['name']
            if not nome:
                continue
            nome_lower = nome.lower()
            if nome_lower in esclusi:
                continue
            if nome_lower in GAMING_THROTTLE_PROCESSES:
                p.nice(target)
                modificati.add(nome)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
    return sorted(modificati)


def imposta_priorita_processo_corrente(bassa: bool) -> bool:
    """Imposta la priorità del processo corrente su BELOW_NORMAL (Gaming Mode) o NORMAL (Balance)."""
    try:
        proc = psutil.Process(os.getpid())
        target = psutil.BELOW_NORMAL_PRIORITY_CLASS if bassa else psutil.NORMAL_PRIORITY_CLASS
        proc.nice(target)
        return True
    except Exception:
        return False


def _formatta_ram_liberata(byte_count: int) -> str:
    """Formatta i byte di RAM liberati in MB o GB leggibili."""
    mb = max(byte_count, 0) / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def attiva_modalita_prestazioni() -> str:
    """Attiva il piano energetico Gaming con tuning USB/PCIe/Disk, ottimizzazioni HKCU, priorità ridotta dell'app e chiusura sicura delle app background."""
    guid_eccellenti = _trova_o_crea_prestazioni_eccellenti()
    if guid_eccellenti:
        guid_attivo = guid_eccellenti
        nome_piano = "Prestazioni eccellenti"
    else:
        guid_attivo = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        nome_piano = "Prestazioni elevate (fallback)"

    # Salva il piano energetico precedente nello snapshot persistente (solo se non già salvato)
    stato = _carica_gaming_state()
    if not stato.get("prev_power_guid"):
        piano_prec = piano_energetico_attivo()
        prev_guid = piano_prec.get("guid", "")
        if prev_guid and _UUID_RE.fullmatch(prev_guid) and prev_guid.lower() != guid_attivo.lower():
            stato["prev_power_guid"] = prev_guid
            stato["prev_power_nome"] = piano_prec.get("nome") or "Bilanciato"
            _salva_gaming_state(stato)

    tuning_piano = _ottimizza_piano_gaming(guid_attivo)
    subprocess.run(
        ["powercfg", "/setactive", guid_attivo],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
    )

    ottimizzazioni_reg = applica_ottimizzazioni_registro_gaming()
    fps_cap = applica_fps_cap_gaming()
    imposta_priorita_processo_corrente(True)
    throttled = imposta_priorita_background_gaming(True)

    bloccati = PROTECTED_PROCESSES | _PROCESSI_SISTEMA_PROTETTI
    ram_prima = psutil.virtual_memory().used
    chiusi = set()
    terminati_procs = []
    rss_chiusi_bytes = 0

    for p in psutil.process_iter(['name', 'memory_info']):
        try:
            nome = p.info['name']
            if not nome:
                continue
            nome_lower = nome.lower()
            if nome_lower in bloccati:
                continue
            if nome_lower in SAFE_TO_CLOSE:
                mem = p.info.get('memory_info')
                if mem and getattr(mem, 'rss', 0):
                    rss_chiusi_bytes += mem.rss
                p.terminate()
                terminati_procs.append(p)
                chiusi.add(nome)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if terminati_procs:
        try:
            psutil.wait_procs(terminati_procs, timeout=1.5)
        except Exception:
            pass

    ram_dopo = psutil.virtual_memory().used
    ram_liberata = max(max(ram_prima - ram_dopo, 0), rss_chiusi_bytes)

    righe = [f"Piano '{nome_piano}' attivato."]
    if tuning_piano:
        righe.append(f"Tuning piano energetico: {', '.join(tuning_piano)}.")
    if ottimizzazioni_reg:
        righe.append(f"Ottimizzazioni Windows (HKCU): {', '.join(ottimizzazioni_reg)}.")
    if fps_cap.get("applicato") and fps_cap.get("messaggio"):
        righe.append(fps_cap["messaggio"])
    righe.append(
        f"Processi chiusi: {', '.join(sorted(chiusi)) if chiusi else 'Nessuno'} "
        f"| RAM liberata: {_formatta_ram_liberata(ram_liberata)}."
    )
    if throttled:
        righe.append(f"Priorità CPU ridotta (BELOW_NORMAL): {', '.join(throttled)}.")
    righe.append(
        f"Overhead PC Agent AI ridotto: telemetria Eco ({TELEMETRY_INTERVAL_GAMING}s), priorità BELOW_NORMAL."
    )
    return "\n".join(righe)


def ripristina_modalita_bilanciata() -> str:
    """Riporta Windows al piano energetico precedente (o Bilanciato) e ripristina registro HKCU, limite FPS NVIDIA e priorità normale dell'app."""
    stato = _carica_gaming_state()
    prev_guid = stato.get("prev_power_guid", "")
    if prev_guid and _UUID_RE.fullmatch(prev_guid):
        target_guid = prev_guid
        target_nome = stato.get("prev_power_nome") or "Bilanciato"
    else:
        target_guid = "381b4222-f694-41f0-9685-ff5bb260df2e"
        target_nome = "Bilanciato"

    subprocess.run(
        ["powercfg", "/setactive", target_guid],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
    )
    ripristinati = ripristina_ottimizzazioni_registro_gaming()
    extra_fps = ripristina_fps_cap_gaming()
    imposta_priorita_processo_corrente(False)
    imposta_priorita_background_gaming(False)

    stato = _carica_gaming_state()
    stato.pop("prev_power_guid", None)
    stato.pop("prev_power_nome", None)
    _salva_gaming_state(stato)

    extra_reg = f" Ripristinate {ripristinati} impostazioni Windows (notifiche/GameBar)." if ripristinati else ""
    return f"Piano energetico riportato su '{target_nome}'.{extra_reg}{extra_fps} Telemetria standard ({TELEMETRY_INTERVAL_NORMAL}s) e priorità normale ripristinate."


_SERVIZI_IN_PAUSA: list[str] = []


def _servizi_salvati_da_riavviare() -> list[str]:
    """Unisce i servizi in pausa in memoria e quelli salvati nello snapshot persistente su disco."""
    stato = _carica_gaming_state()
    su_disco = stato.get("servizi_in_pausa", [])
    unione = []
    for s in list(_SERVIZI_IN_PAUSA) + (su_disco if isinstance(su_disco, list) else []):
        if s in GAMING_PAUSABLE_SERVICES and s not in unione:
            unione.append(s)
    return unione


def servizi_gaming_attivi() -> list[str]:
    """Restituisce i servizi dell'allowlist GAMING_PAUSABLE_SERVICES attualmente in esecuzione."""
    attivi = []
    for nome in GAMING_PAUSABLE_SERVICES:
        try:
            svc = psutil.win_service_get(nome)
            if svc.status() == "running":
                attivi.append(nome)
        except Exception:
            pass
    return attivi


def ha_servizi_gaming_in_pausa() -> bool:
    """Indica se esistono servizi messi in pausa dalla Gaming Mode (in memoria o su disco) da riavviare su Balance."""
    return bool(_servizi_salvati_da_riavviare())


def _stato_servizi_dettaglio(nomi: tuple[str, ...] | list[str]) -> dict[str, str]:
    """Legge lo stato reale ('running', 'stopped', ecc.) di ciascun servizio Windows indicato."""
    esiti = {}
    for nome in nomi:
        try:
            esiti[nome] = psutil.win_service_get(nome).status()
        except Exception:
            esiti[nome] = "n/d"
    return esiti


def stato_ottimizzazioni_gaming() -> dict:
    """Restituisce lo stato reale e una riga di riepilogo per la barra Gaming (FPS Cap, Servizi BG, HAGS, DLDSR)."""
    ok_frl, frl_val = _nvapi_drs_frl_fps("get")
    fps_cap = frl_val if (ok_frl and isinstance(frl_val, int) and frl_val > 0) else None

    stati_svc = _stato_servizi_dettaglio(GAMING_PAUSABLE_SERVICES)
    tot_svc = len(GAMING_PAUSABLE_SERVICES)
    in_pausa = [s for s, st in stati_svc.items() if st == "stopped"]
    attivi = [s for s, st in stati_svc.items() if st == "running"]

    hags = _leggi_hags_attivo()
    physx_auto = _leggi_physx_auto()
    vbs_info = _leggi_stato_vbs_hvci()
    vbs_on = vbs_info.get("attivo")
    mon = info_monitor_principale()
    dldsr_on = bool(mon.get("dldsr_attivo", False))
    dldsr_res = mon.get("risoluzioni_dldsr", [])

    fps_txt = f"FPS Cap {fps_cap} ●" if fps_cap else "FPS Cap OFF ○"
    if len(in_pausa) == tot_svc and tot_svc > 0:
        svc_txt = f"Servizi BG: Pausa ({len(in_pausa)}/{tot_svc}) ●"
    elif in_pausa:
        svc_txt = f"Servizi BG: Pausa ({len(in_pausa)}/{tot_svc}) ◐"
    else:
        svc_txt = f"Servizi BG: Attivi ({len(attivi)}/{tot_svc}) ○"

    hags_txt = "HAGS: ON ●" if hags is True else ("HAGS: OFF ○" if hags is False else "HAGS: N/D")
    if dldsr_on:
        prima_res = dldsr_res[0] if dldsr_res else "attivo"
        dldsr_txt = f"DLDSR: ON ({prima_res}) ●"
    else:
        dldsr_txt = "DLDSR: OFF ○"
    physx_txt = "PhysX: GPU ●" if physx_auto is False else ("PhysX: Auto ○" if physx_auto is True else "PhysX: N/D")
    vbs_txt = "VBS/CoreIso: OFF ●" if vbs_on is False else ("VBS/CoreIso: ON ○" if vbs_on is True else "VBS/CoreIso: N/D")

    attivi_count = sum([
        bool(fps_cap),
        len(in_pausa) > 0,
        hags is True,
        dldsr_on,
        physx_auto is False,
        vbs_on is False,
    ])
    colore = "#81c784" if attivi_count >= 3 else ("#ffb74d" if attivi_count >= 1 else "#9e9e9e")

    return {
        "fps_cap": fps_cap,
        "servizi_in_pausa": in_pausa,
        "servizi_attivi": attivi,
        "hags": hags,
        "physx_auto": physx_auto,
        "vbs_attivo": vbs_info.get("vbs_attivo"),
        "hvci_attivo": vbs_info.get("hvci_attivo"),
        "vbs_hvci_attivo": vbs_on,
        "dldsr_attivo": dldsr_on,
        "risoluzioni_dldsr": dldsr_res,
        "testo_barra": f"Gaming: {fps_txt} | {svc_txt} | {hags_txt} | {dldsr_txt} | {physx_txt} | {vbs_txt}",
        "colore": colore,
    }


def pausa_servizi_gaming(servizi: list[str] | None = None) -> str:
    """Mette temporaneamente in pausa i servizi pesanti di Windows (richiede UAC) usando allowlist fissa."""
    candidati = servizi_gaming_attivi() if servizi is None else [s for s in servizi if s in GAMING_PAUSABLE_SERVICES]
    if not candidati:
        return "Nessun servizio background pesante attivo da mettere in pausa."

    nomi_ps = ",".join(candidati)
    parametri = (
        f'-NoProfile -WindowStyle Hidden -Command '
        f'"Stop-Service -Name {nomi_ps} -Force -ErrorAction SilentlyContinue"'
    )
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", parametri, None, 0)
        if ret > 32:
            for s in candidati:
                if s not in _SERVIZI_IN_PAUSA:
                    _SERVIZI_IN_PAUSA.append(s)
            stato = _carica_gaming_state()
            stato["servizi_in_pausa"] = _servizi_salvati_da_riavviare()
            _salva_gaming_state(stato)
            return f"Servizi messi in pausa (UAC confermato): {', '.join(candidati)} ●. Verranno riavviati con Balance."
        return "Pausa servizi annullata dall'utente nella finestra UAC (servizi lasciati attivi ○)."
    except Exception as e:
        return f"Errore durante la pausa dei servizi: {e}"


def riavvia_servizi_gaming() -> str:
    """Riavvia i servizi messi in pausa durante la Gaming Mode (anche dopo riavvio dell'app)."""
    da_riavviare = _servizi_salvati_da_riavviare()
    if not da_riavviare:
        return ""

    nomi_ps = ",".join(da_riavviare)
    parametri = (
        f'-NoProfile -WindowStyle Hidden -Command '
        f'"Start-Service -Name {nomi_ps} -ErrorAction SilentlyContinue"'
    )
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", parametri, None, 0)
        if ret > 32:
            _SERVIZI_IN_PAUSA.clear()
            stato = _carica_gaming_state()
            stato.pop("servizi_in_pausa", None)
            _salva_gaming_state(stato)
            return f"Servizi Windows riavviati (UAC confermato): {', '.join(da_riavviare)} ○."
        return "Riavvio servizi annullato nella finestra UAC (servizi ancora in pausa)."
    except Exception as e:
        return f"Errore durante il riavvio dei servizi: {e}"


def _leggi_hags_attivo() -> bool | None:
    """Legge lo stato di HAGS (Hardware-Accelerated GPU Scheduling) dal registro HKLM (solo lettura)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", 0, winreg.KEY_READ
        ) as key:
            val, _ = winreg.QueryValueEx(key, "HwSchMode")
            return int(val) == 2
    except FileNotFoundError:
        return False
    except Exception:
        return None


def abilita_hags() -> str:
    """Abilita HAGS (HwSchMode=2 in HKLM) tramite reg.exe con conferma UAC. Richiede riavvio di Windows."""
    if _leggi_hags_attivo() is True:
        return "HAGS (Hardware-Accelerated GPU Scheduling) è già attivo."
    parametri = (
        r'add "HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers" '
        r'/v HwSchMode /t REG_DWORD /d 2 /f'
    )
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "reg.exe", parametri, None, 0)
        if ret > 32:
            return (
                "HAGS abilitato nel registro di Windows (UAC confermato). "
                "Riavvia il PC per rendere effettiva la modifica."
            )
        return "Abilitazione HAGS annullata dall'utente nella finestra UAC."
    except Exception as e:
        return f"Errore durante l'abilitazione di HAGS: {e}"


def _leggi_physx_auto() -> bool | None:
    """Verifica se PhysX NVIDIA è impostato su 'Selezione automatica' (NvCplPhysxAuto=1), controllando prima il percorso DCH."""
    percorsi = (
        r"SYSTEM\CurrentControlSet\Services\nvlddmkm\Parameters\Global\NVTweak",
        r"SYSTEM\CurrentControlSet\Services\nvlddmkm\Global\NVTweak",
    )
    for subpath in percorsi:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subpath, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "NvCplPhysxAuto")
                return int(val) == 1
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None


def _leggi_stato_vbs_hvci() -> dict:
    """Legge lo stato di VBS e Integrità della memoria (HVCI / Core Isolation) dal registro HKLM (sola lettura, zero UAC)."""
    hvci: bool | None = False
    vbs: bool | None = False
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
            0, winreg.KEY_READ,
        ) as key:
            val, _ = winreg.QueryValueEx(key, "Enabled")
            hvci = int(val) == 1
    except FileNotFoundError:
        hvci = False
    except Exception:
        hvci = None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\DeviceGuard",
            0, winreg.KEY_READ,
        ) as key:
            val, _ = winreg.QueryValueEx(key, "EnableVirtualizationBasedSecurity")
            vbs = int(val) == 1
    except FileNotFoundError:
        vbs = False
    except Exception:
        vbs = None

    if hvci is None and vbs is None:
        attivo: bool | None = None
    else:
        attivo = bool(hvci) or bool(vbs)
    return {"vbs_attivo": vbs, "hvci_attivo": hvci, "attivo": attivo}


def apri_isolamento_core_windows() -> bool:
    """Apre direttamente Sicurezza di Windows > Sicurezza dispositivi > Isolamento core senza shell."""
    try:
        subprocess.Popen(
            ["explorer.exe", "windowsdefender://coreisolation"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW,
        )
        return True
    except Exception:
        return False


def _launcher_opzionali_attivi() -> list[str]:
    """Rileva eventuali launcher secondari aperti in background (es. Epic, EA App, Ubisoft, Battle.net, GOG, Xbox)."""
    trovati = set()
    for p in psutil.process_iter(['name']):
        try:
            nome = p.info.get('name') or ""
            if nome.lower() in GAMING_OPTIONAL_LAUNCHERS:
                trovati.add(nome)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass
    return sorted(trovati)


def diagnostica_pre_partita(ram_info: dict | None = None, dischi_info: dict | None = None) -> dict:
    """Esegue un check-up rapido (sola lettura, zero UAC) segnalando solo eventuali colli di bottiglia reali."""
    avvisi = []

    # 1. HAGS (Hardware-Accelerated GPU Scheduling), VRR Windows, PhysX NVIDIA e VBS / Core Isolation
    hags = _leggi_hags_attivo()
    if hags is False:
        avvisi.append("HAGS non attivo: abilitalo in Impostazioni > Schermo > Grafica per ridurre la latenza GPU.")

    vrr = _leggi_vrr_attivo()
    if vrr is False:
        avvisi.append("VRR (Frequenza di aggiornamento variabile) non attivo in Windows.")

    if _leggi_physx_auto() is True:
        avvisi.append("PhysX NVIDIA è su 'Selezione automatica': imposta la GPU NVIDIA nel Pannello di Controllo NVIDIA > Configura Surround, PhysX.")

    vbs_info = _leggi_stato_vbs_hvci()
    vbs_hvci_attivo = vbs_info.get("attivo")
    if vbs_hvci_attivo is True:
        avvisi.append(
            "Integrità della memoria (Isolamento core / VBS) attiva: su CPU meno recenti può ridurre gli FPS "
            "e aumentare la latenza. Valuta di disattivarla in Sicurezza di Windows > Sicurezza dispositivi > "
            "Isolamento core (abbassa leggermente la protezione da malware avanzati, richiede riavvio)."
        )

    # 2. Rete (Wi-Fi / Offline / Ping alto)
    rete = info_rete_attiva()
    nome_rete = rete.get("nome", "Offline")
    if nome_rete == "Offline":
        avvisi.append("Rete offline: nessuna connessione attiva rilevata.")
    else:
        if any(k in nome_rete.lower() for k in ("wi-fi", "wifi", "wireless")):
            avvisi.append(f"Connessione Wi-Fi ({nome_rete}): il cavo Ethernet garantisce ping più stabile.")
        ping = misura_ping()
        if ping.get("ms") is not None and ping["ms"] >= 50:
            avvisi.append(f"Ping elevato verso 1.1.1.1 ({ping['stato']}): possibile congestione di rete.")

    # 3. Spazio critico su C: e dischi meccanici HDD con Windows Search attivo
    try:
        uso_c = psutil.disk_usage("C:\\")
        if uso_c.percent >= DISK_CRIT:
            liberi_gb = round(uso_c.free / (1024**3), 1)
            avvisi.append(f"Disco C: quasi pieno ({uso_c.percent}%, {liberi_gb} GB liberi): gli SSD rallentano oltre il {DISK_CRIT}%.")
    except Exception:
        pass

    info_dischi = dischi_info if dischi_info is not None else mappa_info_dischi_fisici()
    hdd_rilevati = sorted(
        lettera for lettera, info in (info_dischi or {}).items()
        if str(info.get("tipo", "")).upper() == "HDD"
    )
    if hdd_rilevati and _stato_servizi_dettaglio(("WSearch",)).get("WSearch") == "running":
        hdd_str = ", ".join(f"{l}:" for l in hdd_rilevati)
        avvisi.append(
            f"Disco meccanico HDD rilevato ({hdd_str}) con Windows Search (WSearch) attivo: "
            "mettere in pausa l'indicizzazione riduce drasticamente i picchi di disco e CPU."
        )

    # 4. Temperature GPU / CPU già alte prima di iniziare
    gpu = monitora_gpu()
    if "errore" not in gpu and gpu.get("temperatura_num", 0) >= GPU_TEMP_WARN:
        avvisi.append(f"Temperatura GPU già alta prima del gioco ({gpu['temperatura_c']}).")

    sensori_cpu = leggi_sensori_cpu()
    temp_cpu_str = sensori_cpu.get("temperatura_c", "")
    m_cpu = re.search(r"(\d+(?:[.,]\d+)?)", temp_cpu_str)
    if m_cpu:
        try:
            temp_cpu_val = float(m_cpu.group(1).replace(",", "."))
            if temp_cpu_val >= 75.0:
                avvisi.append(f"Temperatura CPU già alta prima del gioco ({temp_cpu_str}).")
        except ValueError:
            pass

    # 5. RAM (Single Channel o frequenza base JEDEC / XMP spento) e launcher secondari aperti
    ram_hw = ram_info if (ram_info and ram_info.get("banchi")) else info_banchi_ram()
    if ram_hw.get("modalita_canale") == "Single Channel":
        avvisi.append("RAM in Single Channel: il Dual Channel migliora sensibilmente gli 1% low.")
    tipo_ram = ram_hw.get("tipo", "")
    freq_ram = ram_hw.get("frequenza_mhz", 0) or 0
    if (tipo_ram == "DDR4" and 0 < freq_ram <= 2133) or (tipo_ram == "DDR5" and 0 < freq_ram <= 4800):
        avvisi.append(f"RAM {tipo_ram} a {freq_ram} MHz (frequenza base): verifica se XMP/EXPO è attivo nel BIOS.")

    launcher_opz = _launcher_opzionali_attivi()
    if launcher_opz:
        avvisi.append(
            f"Launcher secondari aperti in background ({', '.join(launcher_opz)}): "
            "priorità ridotta a BELOW_NORMAL; chiudi quelli non necessari per questa sessione."
        )

    # 6. Bilanciamento CPU-bound / DLDSR su GPU NVIDIA RTX con margine di risoluzione
    consiglia_dldsr = None
    mon = info_monitor_principale()
    gpu_nome = str(gpu.get("gpu", "")) if "errore" not in gpu else ""
    try:
        vram_tot_mb = int(float(gpu.get("vram_totale_mb", 0))) if "errore" not in gpu else 0
    except (ValueError, TypeError):
        vram_tot_mb = 0
    cpu_threads = psutil.cpu_count(logical=True) or 0
    mw, mh = mon.get("larghezza", 0), mon.get("altezza", 0)
    if (
        "rtx" in gpu_nome.lower()
        and vram_tot_mb >= 6000
        and 0 < cpu_threads <= 6
        and mw > 0 and mh > 0
        and (mw * mh) <= (2560 * 1440)
        and not mon.get("dldsr_attivo", False)
    ):
        r178 = f"{round(mw * 1.3333)}x{round(mh * 1.3333)}"
        r225 = f"{round(mw * 1.5)}x{round(mh * 1.5)}"
        consiglia_dldsr = {"nativa": f"{mw}x{mh}", "res_178": r178, "res_225": r225}
        avvisi.append(
            f"DLDSR non attivo su sistema CPU-bound ({cpu_threads} thread + {gpu_nome.replace('NVIDIA GeForce ', '')} su {mw}x{mh}): "
            f"abilita Fattori DSR 1.78x DL ({r178}) o 2.25x DL ({r225}) nel Pannello NVIDIA e alza la qualità grafica nei giochi "
            "per spostare carico sulla GPU e rendere il frametime più regolare."
        )

    if avvisi:
        testo = "Check-up pre-partita — avvisi rilevati:\n" + "\n".join(f"  - {a}" for a in avvisi)
    else:
        testo = "Check-up pre-partita: tutto OK, nessun collo di bottiglia rilevato."

    return {
        "ok": len(avvisi) == 0,
        "avvisi": avvisi,
        "testo": testo,
        "consiglia_dldsr": consiglia_dldsr,
        "dldsr_attivo": bool(mon.get("dldsr_attivo", False)),
        "risoluzioni_dldsr": mon.get("risoluzioni_dldsr", []),
        "vbs_hvci_attivo": vbs_hvci_attivo,
        "hdd_rilevati": hdd_rilevati,
        "launcher_opzionali_attivi": launcher_opz,
    }

def pulisci_file_temporanei() -> str:
    """Elimina i file temporanei non in uso dalla cartella TEMP di Windows."""
    temp_dir = tempfile.gettempdir()
    rimossi = 0
    for item in os.listdir(temp_dir):
        path = os.path.join(temp_dir, item)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
                rimossi += 1
            elif os.path.isdir(path):
                shutil.rmtree(path)
                rimossi += 1
        except Exception:
            pass
    return f"Pulizia completata: rimossi {rimossi} elementi temporanei."

_REGOLA_FIREWALL_LHM = "PC_Agent_AI_Block_LHM_8085"

def stato_sicurezza_lhm() -> dict:
    """Verifica se LibreHardwareMonitor (porta 8085) è esposto sulla LAN e se esiste la regola Firewall di blocco."""
    listen_addrs = []
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == 8085 and conn.status == psutil.CONN_LISTEN:
                listen_addrs.append(conn.laddr.ip)
    except Exception:
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetTCPConnection -LocalPort 8085 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalAddress"],
                encoding="utf-8", errors="ignore", stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
            )
            listen_addrs = [r.strip() for r in out.splitlines() if r.strip()]
        except Exception:
            pass

    # Controllo difensivo per rilevare esposizione su LAN (nessun bind socket)
    esposto_lan = any(ip in ("0.0.0.0", "::", "") for ip in listen_addrs)  # nosec B104
    protetto_fw = False
    try:
        res = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={_REGOLA_FIREWALL_LHM}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, creationflags=NO_WINDOW
        )
        protetto_fw = res.returncode == 0
    except Exception:
        pass

    return {
        "attivo": bool(listen_addrs),
        "esposto_lan": esposto_lan,
        "protetto_firewall": protetto_fw,
        "sicuro": (not esposto_lan) or protetto_fw,
    }

def blocca_lhm_da_lan() -> str:
    """Crea una regola Windows Firewall (richiede UAC) per bloccare l'accesso LAN alla porta 8085 di LHM mantenendo attivo localhost."""
    stato = stato_sicurezza_lhm()
    if stato["protetto_firewall"]:
        return f"La porta 8085 è già protetta dalla regola Windows Firewall '{_REGOLA_FIREWALL_LHM}'."
    parametri = (
        f'advfirewall firewall add rule name="{_REGOLA_FIREWALL_LHM}" '
        "dir=in action=block protocol=TCP localport=8085"
    )
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh.exe", parametri, None, 0)
        if ret > 32:
            return (
                f"Richiesta UAC confermata: regola Windows Firewall '{_REGOLA_FIREWALL_LHM}' aggiunta. "
                "La porta 8085 è ora bloccata dalla LAN e resta accessibile solo su localhost."
            )
        return "Operazione annullata dall'utente nella finestra UAC di Windows."
    except Exception as e:
        return f"Errore durante la creazione della regola Firewall: {e}"