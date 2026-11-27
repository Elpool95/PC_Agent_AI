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
from config import SAFE_TO_CLOSE, PROTECTED_PROCESSES, NO_WINDOW

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

def analizza_sistema() -> dict:
    """Legge l'utilizzo attuale di CPU, RAM, i 5 processi più pesanti sulla CPU e i 5 più pesanti sulla RAM."""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    processi = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            nome = p.info['name']
            if nome and nome != 'System Idle Process':
                mem = p.info.get('memory_info')
                ram_mb = round(mem.rss / (1024 * 1024), 1) if mem else 0.0
                processi.append({
                    'pid': p.info['pid'],
                    'name': nome,
                    'cpu_percent': p.info['cpu_percent'] or 0.0,
                    'ram_mb': ram_mb
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top_cpu = sorted(processi, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    top_ram = sorted(processi, key=lambda x: x['ram_mb'], reverse=True)[:5]
    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_usata_gb": round(ram.used / (1024**3), 2),
        "ram_totale_gb": round(ram.total / (1024**3), 2),
        "top_processi_cpu": top_cpu,
        "top_processi_ram": top_ram
    }

def monitora_gpu() -> dict:
    """Legge utilizzo, temperatura, VRAM usata/totale, consumo W, ventola % e clock MHz della GPU NVIDIA."""
    try:
        smi = _trova_nvidia_smi()
        cmd = [
            smi,
            "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw,fan.speed,clocks.gr,pstate",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.STDOUT, creationflags=NO_WINDOW).strip()
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

def leggi_sensori_cpu() -> dict:
    """Legge temperatura (°C), potenza (W) della CPU e ventole di sistema (RPM) da LibreHardwareMonitor."""
    try:
        with urllib.request.urlopen("http://localhost:8085/data.json", timeout=0.4) as resp:
            dati = json.loads(resp.read().decode("utf-8"))
            temp = _cerca_temp_cpu(dati) or "N/D"
            watt = _cerca_potenza_cpu(dati, "CPU Package") or _cerca_potenza_cpu(dati, "CPU Cores") or "N/D"
            ventole = _cerca_ventole_attive(dati)
            return {"temperatura_c": temp, "potenza_w": watt, "ventole_rpm": ventole}
    except Exception:
        return {"temperatura_c": "-- °C (avvia LHM)", "potenza_w": "-- W", "ventole_rpm": []}

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

def mappa_dischi_fisici(lettere=None) -> dict:
    """Associa le lettere di unità (es. C, D, E, ...) al rispettivo PhysicalDriveX di Windows."""
    mappa = {}
    try:
        ps_cmd = 'Get-Partition | Where-Object {$_.DriveLetter} | ForEach-Object {"$($_.DriveLetter):PhysicalDrive$($_.DiskNumber)"}'
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            encoding="utf-8", stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
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
            encoding="utf-8", stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
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
            encoding="utf-8", stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
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
    """Misura la latenza di rete (ping in ms) verso un host (default 1.1.1.1)."""
    try:
        out = subprocess.check_output(
            ["ping", "-n", "1", "-w", "1000", host],
            encoding="cp850", errors="ignore", stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
        )
        m = re.search(r"(?:durata|time)\s*([<=])\s*(\d+)\s*ms", out, re.IGNORECASE)
        if m:
            op, val = m.group(1), int(m.group(2))
            stato = f"<{val} ms" if op == "<" else f"{val} ms"
            return {"host": host, "ms": val, "stato": stato}
        return {"host": host, "ms": None, "stato": "Timeout"}
    except Exception:
        return {"host": host, "ms": None, "stato": "N/D"}

def piano_energetico_attivo() -> dict:
    """Rileva il piano energetico di Windows attualmente attivo."""
    try:
        out = subprocess.check_output(
            "powercfg /getactivescheme",
            shell=True, encoding="cp850", errors="ignore", stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
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

def analizza_spazio_disco(unita: str = "C:") -> dict:
    """Analizza le principali cartelle cache/utente sul disco indicato per individuare cosa occupa spazio."""
    unita_norm = unita.strip().rstrip("\\").upper()
    if len(unita_norm) == 1:
        unita_norm += ":"
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
            risultati.append({"cartella": etichetta, "percorso": path, "mb": mb})
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
    if not target_str:
        return "Specificare un PID o un nome processo valido."

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
                        risultato[etichetta][nome] = valore
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
            "powercfg /list", shell=True, encoding="cp850", errors="ignore", creationflags=NO_WINDOW
        )
        for riga in out.splitlines():
            if "eccellenti" in riga.lower() or "ultimate performance" in riga.lower():
                m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", riga)
                if m:
                    return m.group(1)

        # Se non esiste ancora, lo sblocca duplicando il modello di sistema
        dup = subprocess.check_output(
            "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61",
            shell=True, encoding="cp850", errors="ignore", creationflags=NO_WINDOW
        )
        m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", dup)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def attiva_modalita_prestazioni() -> str:
    """Attiva il piano energetico Prestazioni Eccellenti e chiude le app pesanti in background (escludendo i processi protetti)."""
    guid_eccellenti = _trova_o_crea_prestazioni_eccellenti()
    if guid_eccellenti:
        subprocess.run(
            f"powercfg /setactive {guid_eccellenti}",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
        )
        nome_piano = "Prestazioni eccellenti"
    else:
        subprocess.run(
            "powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
        )
        nome_piano = "Prestazioni elevate (fallback)"

    chiusi = set()
    for p in psutil.process_iter(['name']):
        try:
            nome = p.info['name']
            if not nome:
                continue
            nome_lower = nome.lower()
            if nome_lower in PROTECTED_PROCESSES:
                continue
            if nome_lower in SAFE_TO_CLOSE:
                p.terminate()
                chiusi.add(nome)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return f"Piano '{nome_piano}' attivato. Processi chiusi: {', '.join(chiusi) if chiusi else 'Nessuno'}."

def ripristina_modalita_bilanciata() -> str:
    """Riporta Windows al piano energetico Bilanciato per ridurre consumi e calore."""
    subprocess.run(
        "powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW
    )
    return "Piano energetico riportato su 'Bilanciato'."

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