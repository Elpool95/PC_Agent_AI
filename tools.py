import json
import os
import re
import shutil
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
    """Legge l'utilizzo attuale di CPU, RAM e i 5 processi più pesanti sulla CPU."""
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    processi = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            if p.info['name'] != 'System Idle Process':
                processi.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top_cpu = sorted(processi, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:5]
    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_usata_gb": round(ram.used / (1024**3), 2),
        "ram_totale_gb": round(ram.total / (1024**3), 2),
        "top_processi_cpu": top_cpu
    }

def monitora_gpu() -> dict:
    """Legge utilizzo, temperatura, VRAM usata/totale e consumo energetico della RTX 3070."""
    try:
        smi = _trova_nvidia_smi()
        cmd = [
            smi,
            "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.STDOUT, creationflags=NO_WINDOW).strip()
        prima_riga = output.splitlines()[0]
        nome, util, temp, vram_usata, vram_tot, watt = [x.strip() for x in prima_riga.split(",")]
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
            "consumo_watt": f"{watt} W"
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

def leggi_sensori_cpu() -> tuple[str, str]:
    """Legge temperatura (°C) e potenza (W) della CPU da LibreHardwareMonitor (http://localhost:8085/data.json)."""
    try:
        with urllib.request.urlopen("http://localhost:8085/data.json", timeout=0.4) as resp:
            dati = json.loads(resp.read().decode("utf-8"))
            temp = _cerca_temp_cpu(dati) or "N/D"
            watt = _cerca_potenza_cpu(dati, "CPU Package") or _cerca_potenza_cpu(dati, "CPU Cores") or "N/D"
            return temp, watt
    except Exception:
        return "-- °C (avvia LHM)", "-- W"

def leggi_temp_cpu() -> str:
    """Legge la temperatura della CPU da LibreHardwareMonitor (http://localhost:8085/data.json) se attivo."""
    return leggi_sensori_cpu()[0]

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