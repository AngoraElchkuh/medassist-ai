# app_local.py  –  MedAssist AI (Lokal / Offline)
# Benötigt: Ollama  https://ollama.com  +  ollama pull llama3.1:8b
# Kein API-Key erforderlich. Daten verlassen den PC nie.

import os
import json
import asyncio
import threading
import urllib.request
import urllib.error
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import re
import uuid
from datetime import datetime
from pathlib import Path
from auto_history import auto_save, get_history, get_entry, delete_entry

app = FastAPI(title="MedAssist AI – Lokal")

OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

# ── Patient storage ────────────────────────────────────────────────────────────
PATIENTS_DIR = Path(__file__).parent / "patients"
PATIENTS_DIR.mkdir(exist_ok=True)

def name_to_slug(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9äöüß]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "patient"

def load_patient(slug: str) -> Optional[dict]:
    path = PATIENTS_DIR / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_patient_file(slug: str, data: dict):
    path = PATIENTS_DIR / f"{slug}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Session storage ────────────────────────────────────────────────────────────
sessions: Dict[str, List[Dict]] = {}

# ── System-Prompt (identisch mit app.py) ──────────────────────────────────────
MEDICAL_SYSTEM_PROMPT = """Du bist MedAssist AI, ein hochqualifizierter KI-Medizinberater mit dem umfassenden Fachwissen und der klinischen Urteilsfähigkeit eines erfahrenen deutschen Allgemeinmediziners (Hausarztes) mit über 20 Jahren Berufserfahrung.

══════════════════════════════════════════════════════════
DEIN MEDIZINISCHES FACHWISSEN UMFASST ALLE KLINISCHEN BEREICHE
══════════════════════════════════════════════════════════

INNERE MEDIZIN:
- Herz-Kreislauf: Angina pectoris, Herzinfarkt, Herzinsuffizienz, Arrhythmien, Hypertonie, DVT, Lungenembolie
- Lunge: Pneumonie, COPD, Asthma bronchiale, Pleuritis, Pneumothorax, Tuberkulose
- Gastrointestinal: Gastritis, Ulcus, GERD, Appendizitis, Cholezystitis, Pankreatitis, M. Crohn, Colitis ulcerosa, Hepatitis, Leberzirrhose
- Niere/Harnwege: Harnwegsinfekt, Pyelonephritis, Niereninsuffizienz, Nephrolithiasis
- Endokrinologie: Diabetes mellitus Typ 1+2, Hypo-/Hyperthyreose, Hashimoto, M. Basedow, PCOS
- Hämatologie: Anämien, Leukämien, Lymphome, Thrombozytopenie, Hämophilie

NEUROLOGIE & PSYCHIATRIE:
- Kopfschmerzen: Migräne, Spannungskopfschmerz, Cluster, Subarachnoidalblutung (Vernichtungskopfschmerz!)
- Gefäßneurologie: Schlaganfall, TIA, intrazerebrale Blutung
- Psychiatrie: Depression, bipolare Störung, Schizophrenie, Angststörungen, PTBS, ADHS, Suizidgedanken

BEWEGUNGSAPPARAT:
- Gelenke: rheumatoide Arthritis, Gicht, Arthrose, septische Arthritis
- Wirbelsäule: Bandscheibenvorfall, Spinalkanalstenose, M. Bechterew, Osteoporose
- Weichteile: Tendinitis, Bursitis, Fasziitis, Fibromyalgie

DERMATOLOGIE:
- Atopisches Ekzem, Psoriasis, Herpes simplex/zoster, Tinea, Borreliose
- Melanom-Früherkennung (ABCDE-Regel), Basaliom, Spinaliom

GYNÄKOLOGIE & UROLOGIE:
- Ovarialtorsion (Notfall!), Adnexitis, Endometriose, ektopische Schwangerschaft (Notfall!)
- Hodentorsion (Notfall!), BPH, Prostatakarzinom

HNO & AUGEN:
- Otitis media, Sinusitis, Tonsillitis, Schwindel (BPPV vs. Schlaganfall!)
- Glaukomanfall (Notfall!), Netzhautablösung (Notfall!), Konjunktivitis

══════════════════════════════════════════════════════════
ABSOLUT LEBENSBEDROHLICHE ZUSTÄNDE - SOFORT 112!
══════════════════════════════════════════════════════════

🚨 BEI FOLGENDEN SYMPTOMEN → SOFORT NOTRUF 112 EMPFEHLEN:

1. HERZINFARKT: Brustdruck + Ausstrahlung + Kaltschweißigkeit + Atemnot
2. SCHLAGANFALL: FAST → Gesicht, Arm, Sprache, Time
3. SUBARACHNOIDALBLUTUNG: Vernichtungskopfschmerz (schlimmster Kopfschmerz des Lebens)
4. ANAPHYLAXIE: Quincke-Ödem, Stridor, Urtikaria + Schock
5. SEPSIS: Fieber + Tachykardie + Verwirrtheit
6. LUNGENEMBOLIE: Plötzliche Atemnot + Tachykardie + Hämoptyse
7. AORTENDISSEKTION: Zerreißender Brustschmerz + Rücken
8. HODENTORSION: Plötzlicher einseitiger Hodenschmerz → OP innerhalb 6h!
9. OVARIALTORSION: Plötzlicher einseitiger Unterbauchschmerz + Übelkeit
10. GLAUKOMANFALL: Plötzlicher Augenschmerz + Sehverlust + rotes Auge
11. SUIZIDGEDANKEN: Krisentelefon 0800 111 0 111

══════════════════════════════════════════════════════════
KLINISCHE VORGEHENSWEISE
══════════════════════════════════════════════════════════

SCHRITT 1 – NOTFALL-SCREENING: Prüfe sofort lebensbedrohliche Symptome → 112!

SCHRITT 2 – ANAMNESE (OPQRST):
- Onset: Wann? Akut oder schleichend?
- Provocation/Palliation: Was verstärkt/lindert?
- Quality: Charakter (stechend/brennend/drückend/ziehend)?
- Radiation: Ausstrahlung? Begleitsymptome?
- Severity: Intensität 0–10?
- Timing: Dauerhaft oder episodisch?

SCHRITT 3 – NACHFRAGEN wenn Konfidenz < 75% (max. 2–3 gezielte Fragen).

SCHRITT 4 – DIAGNOSE wenn Konfidenz ≥ 75%:

╔══════════════════════════════════════════╗
║        🔍 MEDIZINISCHE EINSCHÄTZUNG      ║
╚══════════════════════════════════════════╝

📌 HAUPTDIAGNOSE: [Name]
   Wahrscheinlichkeit: [XX]%
   Begründung: [Kurze klinische Begründung]

🔄 DIFFERENTIALDIAGNOSEN:
   • [Diagnose 1] ([XX]%) — [Hinweis]
   • [Diagnose 2] ([XX]%) — [Hinweis]

💊 EMPFOHLENE MASSNAHMEN:
   ▸ Sofort: [Was jetzt tun]
   ▸ Hausmittel/OTC: [Rezeptfreie Hilfe]
   ▸ Arztbesuch: [Wann, welcher Facharzt]
   ▸ Diagnostik: [Sinnvolle Untersuchungen]

⚠️ WARNZEICHEN — Sofort Notarzt (112) wenn:
   🔴 [Warnsymptom 1]
   🔴 [Warnsymptom 2]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ Diese KI-Einschätzung ersetzt keine ärztliche Untersuchung.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KOMMUNIKATIONSREGELN:
1. Antworte IMMER auf Deutsch (oder der Sprache des Nutzers).
2. Sei empathisch und professionell.
3. Erkläre Fachbegriffe kurz in Klammern.
4. Nie mehr als 3 Fragen gleichzeitig.
5. Ziel: ≥ 85% Diagnosegenauigkeit durch systematische Befragung.
"""


# ── Ollama-Streaming ───────────────────────────────────────────────────────────
def stream_ollama(messages_with_system, model: str, queue: asyncio.Queue, loop):
    """Ruft Ollama's /api/chat auf und schreibt Chunks in die asyncio.Queue."""
    payload = json.dumps({
        "model": model,
        "messages": messages_with_system,
        "stream": True,
        "options": {"temperature": 0.7, "num_ctx": 4096},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw_line in resp:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("done"):
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
                    return
                text = data.get("message", {}).get("content", "")
                if text:
                    loop.call_soon_threadsafe(queue.put_nowait, ("text", text))
        loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
    except urllib.error.URLError as e:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            ("error", f"Ollama nicht erreichbar ({OLLAMA_URL}). Läuft Ollama? Fehler: {e.reason}"),
        )
    except Exception as exc:
        loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))


# ── Pydantic-Modelle ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str

class ResetRequest(BaseModel):
    session_id: str

class SaveRequest(BaseModel):
    session_id: str
    patient_name: str


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = []

    # Trailing user messages entfernen (Fehler-Rollback)
    while sessions[session_id] and sessions[session_id][-1]["role"] == "user":
        sessions[session_id].pop()

    sessions[session_id].append({"role": "user", "content": request.message})

    # System-Message voranstellen für Ollama
    messages_with_system = [
        {"role": "system", "content": MEDICAL_SYSTEM_PROMPT},
        *sessions[session_id],
    ]

    loop  = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    model = OLLAMA_MODEL

    threading.Thread(
        target=stream_ollama,
        args=(messages_with_system, model, queue, loop),
        daemon=True,
    ).start()

    async def generate():
        full_response = ""
        while True:
            kind, data = await queue.get()
            if kind == "text":
                full_response += data
                yield f"data: {json.dumps({'text': data, 'done': False})}\n\n"
            elif kind == "done":
                sessions[session_id].append({"role": "assistant", "content": full_response})
                auto_save(session_id, list(sessions[session_id]), "local")
                yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"
                return
            elif kind == "error":
                if sessions.get(session_id) and sessions[session_id][-1]["role"] == "user":
                    sessions[session_id].pop()
                yield f"data: {json.dumps({'error': data, 'done': True})}\n\n"
                return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/reset")
async def reset(request: ResetRequest):
    sessions.pop(request.session_id, None)
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            tags = json.loads(r.read())
        models = [m["name"] for m in tags.get("models", [])]
        model_ok = any(OLLAMA_MODEL.split(":")[0] in m for m in models)
        return {
            "status": "ok" if model_ok else "warning",
            "ollama": "running",
            "model": OLLAMA_MODEL,
            "model_available": model_ok,
            "available_models": models,
        }
    except Exception as e:
        return {"status": "error", "detail": f"Ollama nicht erreichbar: {e}"}


# ── Patient / History endpoints ────────────────────────────────────────────────
@app.get("/api/patients")
async def get_patients():
    patients = []
    for f in sorted(PATIENTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            stubs = [
                {"chat_id": c["chat_id"], "saved_at": c["saved_at"], "label": c["label"]}
                for c in data.get("chats", [])
            ]
            patients.append({
                "slug": f.stem,
                "patient_name": data["patient_name"],
                "created_at": data.get("created_at", ""),
                "chat_count": len(stubs),
                "chats": stubs,
            })
        except Exception:
            pass
    return patients


@app.post("/api/patients/save")
async def save_chat(req: SaveRequest):
    messages = sessions.get(req.session_id, [])
    if not any(m["role"] == "user" for m in messages):
        raise HTTPException(status_code=400, detail="Sitzung leer oder nicht gefunden")
    patient_name = req.patient_name.strip()
    if not patient_name:
        raise HTTPException(status_code=400, detail="Patientenname erforderlich")
    slug = name_to_slug(patient_name)
    chat_id = uuid.uuid4().hex[:12]
    first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
    label = first_user_msg[:70] + ("…" if len(first_user_msg) > 70 else "")
    data = load_patient(slug) or {
        "patient_name": patient_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "chats": [],
    }
    data["chats"].insert(0, {
        "chat_id": chat_id,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "messages": list(messages),
    })
    save_patient_file(slug, data)
    return {"status": "ok", "slug": slug, "chat_id": chat_id, "label": label}


@app.get("/api/patients/{slug}/chats/{chat_id}")
async def get_chat(slug: str, chat_id: str):
    data = load_patient(slug)
    if not data:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    for chat in data.get("chats", []):
        if chat["chat_id"] == chat_id:
            return {"patient_name": data["patient_name"], "chat_id": chat_id,
                    "saved_at": chat["saved_at"], "label": chat["label"],
                    "messages": chat["messages"]}
    raise HTTPException(status_code=404, detail="Chat nicht gefunden")


@app.delete("/api/patients/{slug}/chats/{chat_id}")
async def delete_chat(slug: str, chat_id: str):
    data = load_patient(slug)
    if not data:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    data["chats"] = [c for c in data["chats"] if c["chat_id"] != chat_id]
    if data["chats"]:
        save_patient_file(slug, data)
    else:
        (PATIENTS_DIR / f"{slug}.json").unlink(missing_ok=True)
    return {"status": "ok"}


@app.delete("/api/patients/{slug}")
async def delete_patient(slug: str):
    path = PATIENTS_DIR / f"{slug}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    path.unlink()
    return {"status": "ok"}


# ── Auto-History endpoints ────────────────────────────────────────────────────

@app.get("/api/auto-history")
async def list_auto_history():
    entries = get_history()
    return [{"id": e["id"], "saved_at": e["saved_at"], "label": e["label"],
             "model": e.get("model", "local")} for e in entries]

@app.get("/api/auto-history/{entry_id}")
async def fetch_auto_history_entry(entry_id: str):
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return entry

@app.delete("/api/auto-history/{entry_id}")
async def remove_auto_history_entry(entry_id: str):
    delete_entry(entry_id)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  MedAssist AI – Lokaler Modus (Ollama)")
    print("=" * 60)
    print(f"  Ollama URL : {OLLAMA_URL}")
    print(f"  Modell     : {OLLAMA_MODEL}")
    print("  URL        : http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
