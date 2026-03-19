# launcher.pyw  –  MedAssist AI GUI-Starter (kein Konsolenfenster)
# Doppelklick genügt.  Cloud = Anthropic API-Key.  Lokal = Ollama (kein Key).

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import webbrowser
import threading
import json
import os
import sys
import time
import socket
import zipfile
import tempfile
import shutil
import urllib.request
import urllib.error
from pathlib import Path

BASE      = Path(__file__).parent
APP_CLOUD = BASE / "app.py"
APP_LOCAL = BASE / "app_local.py"
APP_BOTH  = BASE / "app_combined.py"
CFG_FILE  = BASE / "config.json"
REQ_FILE  = BASE / "requirements.txt"

OLLAMA_URL     = "http://localhost:11434"
DEFAULT_MODEL  = "llama3.1:8b"
OLLAMA_INSTALL = "https://ollama.com/download"

# ── Versionierung ───────────────────────────────────────────────────────────────
VERSION_FILE = BASE / "version.txt"
UPDATE_CFG   = BASE / "update.json"
APP_VERSION  = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "1.0.0"

# Dateien/Ordner die beim Update NICHT überschrieben werden (Nutzerdaten)
UPDATE_SKIP_FILES = {"config.json", "auto_history.json"}
UPDATE_SKIP_DIRS  = {"patients"}

# ── Konfiguration ──────────────────────────────────────────────────────────────
def load_cfg() -> dict:
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_cfg(data: dict):
    CFG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def load_update_cfg() -> dict:
    if UPDATE_CFG.exists():
        try:
            return json.loads(UPDATE_CFG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

# ── Update-Hilfsfunktionen ─────────────────────────────────────────────────────
def _version_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)

def _is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)

def check_remote_version() -> str | None:
    """Prüft ob eine neue Version verfügbar ist. Gibt Versionsnummer zurück oder None."""
    cfg = load_update_cfg()
    url = cfg.get("version_url", "")
    if not url or "OWNER" in url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MedAssist-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            remote = r.read().decode("utf-8").strip()
        return remote if _is_newer(remote, APP_VERSION) else None
    except Exception:
        return None

def fetch_changelog(max_lines=15) -> str:
    cfg = load_update_cfg()
    url = cfg.get("changelog_url", "")
    if not url or "OWNER" in url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MedAssist-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            lines = r.read().decode("utf-8").splitlines()
        return "\n".join(lines[:max_lines])
    except Exception:
        return ""

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────
def port_free(port=8000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0

def hidden_popen(cmd, env=None):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return subprocess.Popen(
        cmd, env=env,
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def ollama_running() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", 11434)) == 0
    except Exception:
        pass
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        return True
    except Exception:
        return False

def find_ollama() -> str | None:
    path = shutil.which("ollama")
    if path:
        return path
    for candidate in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
    return None

def ensure_ollama_running() -> bool:
    if ollama_running():
        return True
    exe = find_ollama()
    if not exe:
        return False
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(
        [exe, "serve"],
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(1)
        if ollama_running():
            return True
    return False

def ollama_models() -> list:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

# ── Haupt-App ──────────────────────────────────────────────────────────────────
class App:
    W = 460

    def __init__(self):
        self.cfg  = load_cfg()
        self.proc = None

        self.root = tk.Tk()
        self.root.title(f"MedAssist AI – Starter  v{APP_VERSION}")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f4f8")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._switch_mode()
        # Update-Check im Hintergrund starten
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        self.root.mainloop()

    # ── Fenstergröße ───────────────────────────────────────────────────────────
    def _resize_window(self):
        self.root.after(50, self._do_resize)

    def _do_resize(self):
        self.root.update_idletasks()
        h = max(self.root.winfo_reqheight() + 20, 340)
        geo = self.root.geometry()
        parts = geo.replace("x", "+").split("+")
        if len(parts) == 4:
            x, y = int(parts[2]), int(parts[3])
        else:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x, y = (sw - self.W) // 2, (sh - h) // 2
        self.root.geometry(f"{self.W}x{h}+{x}+{y}")

    # ── UI aufbauen ────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg="#1565c0", height=68)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="🏥  MedAssist AI",
                 bg="#1565c0", fg="white",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
        tk.Label(hdr, text="KI-Medizinberater",
                 bg="#1565c0", fg="#90caf9",
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(hdr, text=f"v{APP_VERSION}",
                 bg="#1565c0", fg="#90caf9",
                 font=("Segoe UI", 9)).pack(side="right", padx=16)

        # Update-Banner (anfangs leer/unsichtbar)
        self.update_bar = tk.Frame(self.root, bg="#fff8e1")
        # wird erst bei verfügbarem Update befüllt und sichtbar gemacht

        # Modus-Auswahl
        self._mode_frame = tk.Frame(self.root, bg="#e8f0fe", pady=8)
        self._mode_frame.pack(fill="x")
        tk.Label(self._mode_frame, text="Modus:", bg="#e8f0fe",
                 font=("Segoe UI", 10, "bold"), fg="#1a202c").pack(side="left", padx=(20, 10))

        self.mode = tk.StringVar(value=self.cfg.get("mode", "cloud"))
        for val, label in [("cloud", "☁️  Cloud"),
                           ("local", "💻  Lokal"),
                           ("both",  "⚡  Beide")]:
            tk.Radiobutton(
                self._mode_frame, text=label, variable=self.mode, value=val,
                bg="#e8f0fe", fg="#1a202c", activebackground="#e8f0fe",
                font=("Segoe UI", 10), cursor="hand2",
                command=self._switch_mode,
            ).pack(side="left", padx=6)

        # Body
        self.body = tk.Frame(self.root, bg="#f0f4f8", padx=24, pady=16)
        self.body.pack(fill="both", expand=True)

        # ── Cloud-Bereich ──
        self.cloud_frame = tk.Frame(self.body, bg="#f0f4f8")

        tk.Label(self.cloud_frame, text="Anthropic API-Key",
                 bg="#f0f4f8", fg="#1a202c",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(self.cloud_frame,
                 text="Einmalig eingeben – wird lokal gespeichert.",
                 bg="#f0f4f8", fg="#64748b",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        key_row = tk.Frame(self.cloud_frame, bg="#f0f4f8")
        key_row.pack(fill="x")
        self.key_var = tk.StringVar(value=self.cfg.get("api_key", ""))
        self.key_entry = tk.Entry(
            key_row, textvariable=self.key_var, show="•",
            font=("Segoe UI", 10), relief="flat", bg="white",
            highlightthickness=1, highlightbackground="#dce3ec",
            highlightcolor="#1565c0",
        )
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.show_btn = tk.Button(
            key_row, text="👁", width=3, relief="flat",
            bg="#e3f0ff", fg="#1565c0", cursor="hand2",
            font=("Segoe UI", 10), command=self._toggle_key,
        )
        self.show_btn.pack(side="left", padx=(4, 0))

        # ── Lokal-Bereich ──
        self.local_frame = tk.Frame(self.body, bg="#f0f4f8")

        status_row = tk.Frame(self.local_frame, bg="#f0f4f8")
        status_row.pack(fill="x", pady=(0, 10))
        tk.Label(status_row, text="Ollama-Status:",
                 bg="#f0f4f8", font=("Segoe UI", 10, "bold"),
                 fg="#1a202c").pack(side="left")
        self.ollama_dot = tk.Label(status_row, text="●",
                                   bg="#f0f4f8", font=("Segoe UI", 12),
                                   fg="#94a3b8")
        self.ollama_dot.pack(side="left", padx=6)
        self.ollama_status_var = tk.StringVar(value="nicht geprüft")
        tk.Label(status_row, textvariable=self.ollama_status_var,
                 bg="#f0f4f8", font=("Segoe UI", 9),
                 fg="#64748b").pack(side="left")
        tk.Button(status_row, text="Prüfen", relief="flat",
                  bg="#e3f0ff", fg="#1565c0", cursor="hand2",
                  font=("Segoe UI", 9), padx=8,
                  command=self._check_ollama).pack(side="right")

        model_row = tk.Frame(self.local_frame, bg="#f0f4f8")
        model_row.pack(fill="x", pady=(0, 4))
        tk.Label(model_row, text="Modell:",
                 bg="#f0f4f8", font=("Segoe UI", 10, "bold"),
                 fg="#1a202c").pack(side="left")
        self.model_var = tk.StringVar(value=self.cfg.get("model", DEFAULT_MODEL))
        self.model_entry = tk.Entry(
            model_row, textvariable=self.model_var,
            font=("Segoe UI", 10), relief="flat", bg="white",
            highlightthickness=1, highlightbackground="#dce3ec",
            highlightcolor="#1565c0", width=22,
        )
        self.model_entry.pack(side="left", padx=(10, 0), ipady=5)

        self.model_list_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            model_row, textvariable=self.model_list_var,
            state="readonly", width=0, font=("Segoe UI", 9),
        )
        self.model_combo.pack(side="left", padx=(6, 0))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_select)

        tk.Label(self.local_frame,
                 text="Empfohlen: llama3.1:8b  •  Zum Download: ollama pull llama3.1:8b",
                 bg="#f0f4f8", fg="#64748b", font=("Segoe UI", 8)).pack(anchor="w")

        self.hint_frame = tk.Frame(self.local_frame, bg="#fff8e1",
                                    highlightthickness=1, highlightbackground="#ffe082")
        tk.Label(self.hint_frame,
                 text="ℹ️  Ollama nicht installiert? → ollama.com/download\n"
                      "   Dann im Terminal:  ollama pull llama3.1:8b",
                 bg="#fff8e1", fg="#5d4037", font=("Segoe UI", 9),
                 justify="left").pack(padx=10, pady=6, anchor="w")
        tk.Button(self.hint_frame, text="🔗 ollama.com öffnen",
                  relief="flat", bg="#ffe082", fg="#5d4037",
                  cursor="hand2", font=("Segoe UI", 9),
                  command=lambda: webbrowser.open(OLLAMA_INSTALL),
                  ).pack(padx=10, pady=(0, 8), anchor="w")

        # ── Gemeinsamer Bereich ──
        self.status_var = tk.StringVar(value="Bereit.")
        self.status_lbl = tk.Label(
            self.body, textvariable=self.status_var,
            bg="#f0f4f8", fg="#64748b",
            font=("Segoe UI", 9), wraplength=400, justify="left",
        )
        self.status_lbl.pack(anchor="w", pady=(12, 0))

        self.progress = ttk.Progressbar(self.body, mode="indeterminate", length=410)
        self.progress.pack(pady=(6, 0))

        btn_frame = tk.Frame(self.body, bg="#f0f4f8")
        btn_frame.pack(fill="x", pady=(14, 0))

        self.start_btn = tk.Button(
            btn_frame, text="▶  Starten",
            bg="#1565c0", fg="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=8,
            command=self._start,
        )
        self.start_btn.pack(side="left")

        self.browser_btn = tk.Button(
            btn_frame, text="🌐  Browser",
            bg="#2e7d32", fg="white",
            font=("Segoe UI", 11),
            relief="flat", cursor="hand2", padx=16, pady=8,
            state="disabled",
            command=lambda: webbrowser.open("http://localhost:8000"),
        )
        self.browser_btn.pack(side="left", padx=(8, 0))

        self.stop_btn = tk.Button(
            btn_frame, text="⏹  Stoppen",
            bg="#c62828", fg="white",
            font=("Segoe UI", 11),
            relief="flat", cursor="hand2", padx=16, pady=8,
            state="disabled",
            command=self._stop,
        )
        self.stop_btn.pack(side="right")

        tk.Label(self.root, text="localhost:8000  •  Daten bleiben lokal",
                 bg="#f0f4f8", fg="#94a3b8",
                 font=("Segoe UI", 8)).pack(pady=(0, 6))

    # ── Update-System ──────────────────────────────────────────────────────────
    def _check_update_bg(self):
        """Läuft im Hintergrund-Thread beim Start."""
        remote = check_remote_version()
        if remote:
            self.root.after(0, self._show_update_banner, remote)

    def _show_update_banner(self, remote_version: str):
        """Zeigt den gelben Update-Banner zwischen Header und Modus-Auswahl."""
        for w in self.update_bar.winfo_children():
            w.destroy()

        tk.Label(
            self.update_bar,
            text=f"  🔄  Version {remote_version} verfügbar!  (aktuell: v{APP_VERSION})",
            bg="#fff8e1", fg="#5d4037",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", pady=6, padx=(10, 0))

        tk.Button(
            self.update_bar,
            text="▼ Jetzt aktualisieren",
            bg="#f9a825", fg="white",
            relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            padx=12, pady=4,
            command=lambda: self._confirm_update(remote_version),
        ).pack(side="left", padx=10, pady=5)

        self.update_bar.pack(fill="x", before=self._mode_frame)
        self._resize_window()

    def _confirm_update(self, remote_version: str):
        """Bestätigungsdialog + optionaler Changelog."""
        changelog = fetch_changelog()
        msg = f"Neue Version {remote_version} ist verfügbar.\n\n"
        if changelog:
            msg += "── Änderungen ──────────────────\n"
            msg += changelog[:500] + ("\n…" if len(changelog) > 500 else "")
            msg += "\n────────────────────────────────\n\n"
        msg += "Jetzt aktualisieren?"

        if messagebox.askyesno("Update verfügbar", msg, icon="question"):
            self._start_update(remote_version)

    def _start_update(self, remote_version: str):
        """Öffnet das Update-Fortschrittsfenster und startet den Download."""
        cfg = load_update_cfg()
        download_url = cfg.get("download_url", "")
        zip_prefix   = cfg.get("zip_prefix", "")

        if not download_url or "OWNER" in download_url:
            messagebox.showerror("Update fehlgeschlagen",
                                 "Download-URL nicht konfiguriert.\n"
                                 "Bitte update.json bearbeiten.")
            return

        # Server stoppen falls er läuft
        if self.proc and self.proc.poll() is None:
            self._stop()

        # Fortschrittsfenster
        dlg = tk.Toplevel(self.root)
        dlg.title("MedAssist AI – Update")
        dlg.resizable(False, False)
        dlg.configure(bg="#f0f4f8")
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)  # Schließen sperren

        # Zentrieren
        dlg.update_idletasks()
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        dlg.geometry(f"420x220+{(sw-420)//2}+{(sh-220)//2}")

        tk.Label(dlg, text="🔄  MedAssist AI Update",
                 bg="#f0f4f8", font=("Segoe UI", 13, "bold"),
                 fg="#1565c0").pack(pady=(22, 4))

        tk.Label(dlg, text=f"Lade Version {remote_version} herunter…",
                 bg="#f0f4f8", font=("Segoe UI", 9), fg="#64748b").pack()

        bar = ttk.Progressbar(dlg, length=360, mode="indeterminate")
        bar.pack(pady=14)
        bar.start(10)

        status_var = tk.StringVar(value="Verbinde mit Server…")
        tk.Label(dlg, textvariable=status_var,
                 bg="#f0f4f8", font=("Segoe UI", 9),
                 fg="#64748b", wraplength=380).pack()

        def set_st(msg): dlg.after(0, status_var.set, msg)

        def worker():
            try:
                # 1) Download in temporäre Datei
                set_st("Lade Update herunter…")
                tmp = tempfile.mktemp(suffix=".zip")

                total_ref = [0]
                def reporthook(count, block, total):
                    total_ref[0] = total
                    if total > 0:
                        mb = count * block / 1_048_576
                        tot_mb = total / 1_048_576
                        set_st(f"Lade herunter… {mb:.1f} / {tot_mb:.1f} MB")

                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "MedAssist-Updater/1.0"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp, \
                     open(tmp, "wb") as f:
                    block = 8192
                    total = int(resp.headers.get("Content-Length", 0))
                    total_ref[0] = total
                    count = 0
                    while True:
                        chunk = resp.read(block)
                        if not chunk:
                            break
                        f.write(chunk)
                        count += 1
                        reporthook(count, block, total)

                # 2) Entpacken
                set_st("Entpacke Update…")
                dlg.after(0, bar.stop)
                dlg.after(0, bar.config, {"mode": "determinate", "value": 0})

                with zipfile.ZipFile(tmp) as z:
                    members = z.namelist()
                    # Gemeinsamen Prefix ermitteln (z.B. "medassist-main/")
                    prefix = zip_prefix
                    if not prefix and members:
                        first = members[0]
                        if first.endswith("/"):
                            prefix = first

                    to_extract = [m for m in members if m != prefix]
                    total_files = len(to_extract)

                    for i, member in enumerate(to_extract):
                        rel = member[len(prefix):] if prefix and member.startswith(prefix) else member
                        if not rel:
                            continue

                        # Nutzerdaten überspringen
                        parts = Path(rel).parts
                        if not parts:
                            continue
                        if parts[0] in UPDATE_SKIP_DIRS:
                            continue
                        if rel in UPDATE_SKIP_FILES:
                            continue

                        target = BASE / rel
                        if member.endswith("/"):
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(target, "wb") as dst:
                                shutil.copyfileobj(src, dst)

                        pct = int((i + 1) / total_files * 100)
                        dlg.after(0, bar.config, {"value": pct})
                        set_st(f"Entpacke… {i+1}/{total_files}  ({rel[:45]})")

                # 3) version.txt aktualisieren
                (BASE / "version.txt").write_text(remote_version + "\n", encoding="utf-8")

                # Temp-Datei löschen
                try: os.unlink(tmp)
                except Exception: pass

                # 4) Fertig-Dialog
                dlg.after(0, lambda: _show_done(dlg, remote_version))

            except Exception as exc:
                try: os.unlink(tmp)
                except Exception: pass
                dlg.after(0, lambda: _show_error(dlg, str(exc)))

        def _show_done(d, ver):
            for w in d.winfo_children():
                w.destroy()
            d.geometry("420x200")
            tk.Label(d, text="✅  Update abgeschlossen!",
                     bg="#f0f4f8", font=("Segoe UI", 13, "bold"),
                     fg="#2e7d32").pack(pady=(28, 6))
            tk.Label(d, text=f"Version {ver} wurde installiert.",
                     bg="#f0f4f8", font=("Segoe UI", 10),
                     fg="#64748b").pack()
            tk.Label(d, text="Der Launcher wird jetzt neu gestartet.",
                     bg="#f0f4f8", font=("Segoe UI", 9),
                     fg="#94a3b8").pack(pady=(4, 0))
            tk.Button(
                d, text="🔄  Jetzt neu starten",
                bg="#1565c0", fg="white",
                font=("Segoe UI", 11, "bold"),
                relief="flat", cursor="hand2", padx=20, pady=8,
                command=lambda: self._restart_launcher(d),
            ).pack(pady=20)

        def _show_error(d, err):
            bar.stop()
            for w in d.winfo_children():
                w.destroy()
            d.geometry("420x200")
            tk.Label(d, text="❌  Update fehlgeschlagen",
                     bg="#f0f4f8", font=("Segoe UI", 12, "bold"),
                     fg="#c62828").pack(pady=(24, 8))
            tk.Label(d, text=err[:120], bg="#f0f4f8",
                     font=("Segoe UI", 9), fg="#64748b",
                     wraplength=380).pack()
            tk.Button(d, text="Schließen", relief="flat",
                      bg="#e0e0e0", fg="#1a202c",
                      font=("Segoe UI", 10), cursor="hand2", padx=14,
                      command=d.destroy).pack(pady=16)

        threading.Thread(target=worker, daemon=True).start()

    def _restart_launcher(self, dlg):
        """Schließt alles und startet launcher.pyw neu."""
        dlg.destroy()
        subprocess.Popen([sys.executable, str(BASE / "launcher.pyw")])
        self.root.destroy()

    # ── Modus umschalten ───────────────────────────────────────────────────────
    def _switch_mode(self):
        mode = self.mode.get()
        self.cloud_frame.pack_forget()
        self.local_frame.pack_forget()
        if mode == "cloud":
            self.cloud_frame.pack(fill="x", before=self.status_lbl)
        elif mode == "local":
            self.local_frame.pack(fill="x", before=self.status_lbl)
            threading.Thread(target=self._check_ollama, daemon=True).start()
        else:
            self.cloud_frame.pack(fill="x", before=self.status_lbl)
            self.local_frame.pack(fill="x", before=self.status_lbl)
            threading.Thread(target=self._check_ollama, daemon=True).start()
        self._resize_window()

    # ── API-Key Sichtbarkeit ───────────────────────────────────────────────────
    def _toggle_key(self):
        if self.key_entry.cget("show") == "•":
            self.key_entry.config(show=""); self.show_btn.config(text="🙈")
        else:
            self.key_entry.config(show="•"); self.show_btn.config(text="👁")

    # ── Ollama prüfen ──────────────────────────────────────────────────────────
    def _check_ollama(self):
        self.root.after(0, self.ollama_status_var.set, "prüfe...")
        running = ollama_running()
        if running:
            models = ollama_models()
            model_names = [m.split(":")[0] for m in models]
            target = self.model_var.get().split(":")[0]
            model_ok = target in model_names
            if model_ok:
                self.root.after(0, self._set_ollama_ui, "online", True,
                                f"läuft · Modell verfügbar  ({len(models)} Modelle)")
            else:
                self.root.after(0, self._set_ollama_ui, "warning", True,
                                f"läuft · Modell '{target}' nicht gefunden")
            self.root.after(0, self.model_combo.config, {"values": models})
        else:
            self.root.after(0, self._set_ollama_ui, "offline", False,
                            "nicht erreichbar  →  Ollama starten oder installieren")

    def _set_ollama_ui(self, state: str, ok: bool, msg: str):
        colors = {"online": "#2e7d32", "warning": "#e65100", "offline": "#c62828"}
        self.ollama_dot.config(fg=colors.get(state, "#94a3b8"))
        self.ollama_status_var.set(msg)
        if state == "offline":
            self.hint_frame.pack(fill="x", pady=(10, 0))
        else:
            self.hint_frame.pack_forget()
        self._resize_window()

    def _on_model_select(self, _event=None):
        self.model_var.set(self.model_list_var.get())

    # ── Start ──────────────────────────────────────────────────────────────────
    def _start(self):
        mode = self.mode.get()
        if mode in ("cloud", "both"):
            api_key = self.key_var.get().strip()
            if not api_key:
                messagebox.showerror("API-Key fehlt",
                                     "Bitte einen Anthropic API-Key eingeben.")
                return
            if not api_key.startswith("sk-"):
                if not messagebox.askyesno("API-Key prüfen",
                                           "Der Key beginnt nicht mit 'sk-'.\nTrotzdem fortfahren?"):
                    return
            self.cfg["api_key"] = api_key
        if mode in ("local", "both"):
            self.cfg["model"] = self.model_var.get().strip() or DEFAULT_MODEL

        self.cfg["mode"] = mode
        save_cfg(self.cfg)

        self.start_btn.config(state="disabled")
        self._set_status("Installiere Abhängigkeiten...", "#1565c0")
        self.progress.start(12)

        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        try:
            hidden_popen([sys.executable, "-m", "pip", "install",
                          "-r", str(REQ_FILE), "-q", "--upgrade"]).wait()
        except Exception as e:
            self.root.after(0, self._fail, f"pip-Fehler: {e}")
            return

        if not port_free(8000):
            self.root.after(0, self._set_status,
                            "Port 8000 belegt – Server läuft möglicherweise schon.", "#e65100")
            self.root.after(0, self.progress.stop)
            self.root.after(0, self._set_running_ui)
            return

        mode = self.mode.get()
        if mode in ("local", "both"):
            self.root.after(0, self._set_status, "Ollama wird gestartet...", "#1565c0")
            if not ensure_ollama_running():
                self.root.after(0, self._fail,
                                "Ollama nicht gefunden.\n"
                                "Bitte unter ollama.com/download installieren,\n"
                                "dann 'ollama pull llama3.1:8b' ausführen.")
                return
            self.root.after(0, self._set_status, "Ollama läuft ✓", "#2e7d32")

        env = os.environ.copy()
        if mode == "cloud":
            env["ANTHROPIC_API_KEY"] = self.cfg.get("api_key", "")
            app_script = APP_CLOUD
        elif mode == "local":
            env["OLLAMA_MODEL"] = self.cfg.get("model", DEFAULT_MODEL)
            env["OLLAMA_URL"]   = OLLAMA_URL
            app_script = APP_LOCAL
        else:
            env["ANTHROPIC_API_KEY"] = self.cfg.get("api_key", "")
            env["OLLAMA_MODEL"] = self.cfg.get("model", DEFAULT_MODEL)
            env["OLLAMA_URL"]   = OLLAMA_URL
            app_script = APP_BOTH

        try:
            self.proc = hidden_popen([sys.executable, str(app_script)], env=env)
        except Exception as e:
            self.root.after(0, self._fail, f"Start-Fehler: {e}")
            return

        for _ in range(30):
            time.sleep(0.5)
            if not port_free(8000):
                break
        else:
            self.root.after(0, self._fail, "Server antwortet nicht (Timeout).")
            return

        webbrowser.open("http://localhost:8000")
        self.root.after(0, self._set_running_ui)

    # ── Stop ───────────────────────────────────────────────────────────────────
    def _stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try: self.proc.kill()
                except Exception: pass
            self.proc = None
        self.progress.stop()
        self._set_status("Server gestoppt.", "#64748b")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.browser_btn.config(state="disabled")

    # ── UI-Zustände ────────────────────────────────────────────────────────────
    def _set_running_ui(self):
        mode = self.mode.get()
        if mode == "cloud":
            label = "Cloud (Anthropic)"
        elif mode == "local":
            label = f"Lokal ({self.cfg.get('model', DEFAULT_MODEL)})"
        else:
            label = f"Cloud + Lokal ({self.cfg.get('model', DEFAULT_MODEL)})"
        self.progress.stop()
        self._set_status(f"✅  Server läuft  ·  {label}  ·  http://localhost:8000", "#2e7d32")
        self.stop_btn.config(state="normal")
        self.browser_btn.config(state="normal")

    def _set_status(self, msg: str, color: str = "#64748b"):
        self.status_var.set(msg)
        self.status_lbl.config(fg=color)

    def _fail(self, msg: str):
        self.progress.stop()
        self._set_status(msg, "#c62828")
        self.start_btn.config(state="normal")

    # ── Schließen ──────────────────────────────────────────────────────────────
    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            if messagebox.askyesno("Beenden", "Server läuft noch. Beim Schließen stoppen?"):
                self._stop()
            else:
                self.root.destroy()
                return
        self.root.destroy()


if __name__ == "__main__":
    App()
