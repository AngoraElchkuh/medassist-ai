# app_combined.py  –  MedAssist AI (Cloud + Lokal + Vergleich)
# Gestartet wenn config.json → mode = "both"
# Bietet: /api/chat?model=cloud|local und /api/chat/compare (parallel)

import os, json, re, uuid, asyncio, threading, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from auto_history import auto_save, get_history, get_entry, delete_entry
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional

try:
    import anthropic as _anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

app = FastAPI(title="MedAssist AI – Kombiniert")

OLLAMA_URL   = os.environ.get("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
PATIENTS_DIR = Path(__file__).parent / "patients"
PATIENTS_DIR.mkdir(exist_ok=True)
CONFIG_FILE  = Path(__file__).parent / "config.json"

# ── Session-Speicher (getrennt je Engine) ──────────────────────────────────────
cloud_sessions: Dict[str, List[Dict]] = {}
local_sessions: Dict[str, List[Dict]] = {}

MEDICAL_SYSTEM_PROMPT = """Du bist MedAssist AI, ein hochqualifizierter KI-Medizinberater mit dem umfassenden Fachwissen und der klinischen Urteilsfähigkeit eines erfahrenen deutschen Allgemeinmediziners (Hausarztes) mit über 20 Jahren Berufserfahrung.

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

# ── Pydantic-Modelle ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: str = "cloud"   # "cloud" | "local"

class CompareRequest(BaseModel):
    message: str
    cloud_session_id: str
    local_session_id: str

class ResetRequest(BaseModel):
    session_id: str
    model: str = "cloud"   # "cloud" | "local" | "both"

class RestoreRequest(BaseModel):
    session_id: str
    messages: list

class SaveRequest(BaseModel):
    session_id: str
    patient_name: str
    model: str = "cloud"   # which session store to save from

# ── Hilfsfunktionen Patientendaten ─────────────────────────────────────────────
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

# ── Streaming-Funktionen ───────────────────────────────────────────────────────
def _do_stream_cloud(messages_snapshot, queue, loop, prefix=""):
    """Anthropic streaming → queue. prefix="" für single, "cloud_" für compare."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not HAS_ANTHROPIC or not api_key:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            (prefix + "error", "API-Key nicht gesetzt oder anthropic-Paket fehlt."),
        )
        return
    try:
        client = _anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=MEDICAL_SYSTEM_PROMPT,
            messages=messages_snapshot,
        ) as stream:
            for text in stream.text_stream:
                loop.call_soon_threadsafe(queue.put_nowait, (prefix + "text", text))
        loop.call_soon_threadsafe(queue.put_nowait, (prefix + "done", None))
    except Exception as exc:
        loop.call_soon_threadsafe(queue.put_nowait, (prefix + "error", str(exc)))


def _do_stream_local(messages_with_system, queue, loop, prefix=""):
    """Ollama streaming → queue. prefix="" für single, "local_" für compare."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
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
                    loop.call_soon_threadsafe(queue.put_nowait, (prefix + "done", None))
                    return
                text = data.get("message", {}).get("content", "")
                if text:
                    loop.call_soon_threadsafe(queue.put_nowait, (prefix + "text", text))
        loop.call_soon_threadsafe(queue.put_nowait, (prefix + "done", None))
    except urllib.error.URLError as e:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            (prefix + "error", f"Ollama nicht erreichbar: {e.reason}"),
        )
    except Exception as exc:
        loop.call_soon_threadsafe(queue.put_nowait, (prefix + "error", str(exc)))


# ── Helper: Session vorbereiten ────────────────────────────────────────────────
def _prep_session(store: dict, sid: str, message: str):
    if sid not in store:
        store[sid] = []
    while store[sid] and store[sid][-1]["role"] == "user":
        store[sid].pop()
    store[sid].append({"role": "user", "content": message})
    return list(store[sid])

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    tpl = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(
        content=tpl.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )

@app.get("/api/config")
async def get_config():
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {
                "mode": cfg.get("mode", "cloud"),
                "ollama_model": OLLAMA_MODEL,
                "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
            }
        except Exception:
            pass
    return {"mode": "cloud", "ollama_model": OLLAMA_MODEL, "has_api_key": False}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    sid   = request.session_id
    mdl   = request.model.lower()
    store = cloud_sessions if mdl == "cloud" else local_sessions
    snap  = _prep_session(store, sid, request.message)
    loop  = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    if mdl == "cloud":
        threading.Thread(
            target=_do_stream_cloud, args=(snap, queue, loop, ""), daemon=True
        ).start()
    else:
        msgs_with_sys = [{"role": "system", "content": MEDICAL_SYSTEM_PROMPT}, *snap]
        threading.Thread(
            target=_do_stream_local, args=(msgs_with_sys, queue, loop, ""), daemon=True
        ).start()

    async def generate():
        full = ""
        while True:
            kind, data = await queue.get()
            if kind == "text":
                full += data
                yield f"data: {json.dumps({'text': data, 'done': False})}\n\n"
            elif kind == "done":
                store[sid].append({"role": "assistant", "content": full})
                auto_save(sid, list(store[sid]), mdl)
                yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"
                return
            elif kind == "error":
                if store.get(sid) and store[sid][-1]["role"] == "user":
                    store[sid].pop()
                yield f"data: {json.dumps({'error': data, 'done': True})}\n\n"
                return

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/compare")
async def chat_compare(request: CompareRequest):
    csid = request.cloud_session_id
    lsid = request.local_session_id

    cloud_snap = _prep_session(cloud_sessions, csid, request.message)
    local_snap = _prep_session(local_sessions, lsid, request.message)
    local_with_sys = [{"role": "system", "content": MEDICAL_SYSTEM_PROMPT}, *local_snap]

    loop  = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    threading.Thread(
        target=_do_stream_cloud, args=(cloud_snap, queue, loop, "cloud_"), daemon=True
    ).start()
    threading.Thread(
        target=_do_stream_local, args=(local_with_sys, queue, loop, "local_"), daemon=True
    ).start()

    async def generate():
        cloud_done = False
        local_done = False
        cloud_resp = ""
        local_resp = ""
        while not (cloud_done and local_done):
            kind, data = await queue.get()
            if kind == "cloud_text":
                cloud_resp += data
                yield f"data: {json.dumps({'source':'cloud','text':data,'done':False})}\n\n"
            elif kind == "cloud_done":
                cloud_sessions[csid].append({"role": "assistant", "content": cloud_resp})
                auto_save(csid, list(cloud_sessions[csid]), "cloud")
                yield f"data: {json.dumps({'source':'cloud','text':'','done':True})}\n\n"
                cloud_done = True
            elif kind == "cloud_error":
                yield f"data: {json.dumps({'source':'cloud','error':data,'done':True})}\n\n"
                cloud_done = True
            elif kind == "local_text":
                local_resp += data
                yield f"data: {json.dumps({'source':'local','text':data,'done':False})}\n\n"
            elif kind == "local_done":
                local_sessions[lsid].append({"role": "assistant", "content": local_resp})
                auto_save(lsid, list(local_sessions[lsid]), "local")
                yield f"data: {json.dumps({'source':'local','text':'','done':True})}\n\n"
                local_done = True
            elif kind == "local_error":
                yield f"data: {json.dumps({'source':'local','error':data,'done':True})}\n\n"
                local_done = True

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/restore-session")
async def restore_session(req: RestoreRequest):
    restored = [
        {"role": m["role"], "content": m["content"]}
        for m in req.messages
        if m.get("role") in ("user", "assistant")
    ]
    cloud_sessions[req.session_id] = list(restored)
    local_sessions[req.session_id] = list(restored)
    return {"status": "ok", "count": len(restored)}


@app.post("/api/reset")
async def reset(request: ResetRequest):
    sid = request.session_id
    mdl = request.model.lower()
    if mdl in ("cloud", "both"):
        cloud_sessions.pop(sid, None)
    if mdl in ("local", "both"):
        local_sessions.pop(sid, None)
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    result: dict = {}
    # Cloud
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    result["cloud"] = {"has_key": bool(api_key)}
    if api_key and HAS_ANTHROPIC:
        try:
            c = _anthropic.Anthropic(api_key=api_key)
            c.messages.create(model="claude-opus-4-6", max_tokens=5,
                              messages=[{"role": "user", "content": "Hi"}])
            result["cloud"]["status"] = "ok"
        except Exception as e:
            result["cloud"]["status"] = "error"
            result["cloud"]["detail"] = str(e)
    # Local
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            tags = json.loads(r.read())
        models = [m["name"] for m in tags.get("models", [])]
        model_ok = any(OLLAMA_MODEL.split(":")[0] in m for m in models)
        result["local"] = {"status": "ok" if model_ok else "model_missing",
                           "model": OLLAMA_MODEL, "available_models": models}
    except Exception as e:
        result["local"] = {"status": "error", "detail": str(e)}
    return result


# ── Patientenakten ─────────────────────────────────────────────────────────────
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
    store = cloud_sessions if req.model == "cloud" else local_sessions
    messages = store.get(req.session_id, [])
    if not any(m["role"] == "user" for m in messages):
        raise HTTPException(status_code=400, detail="Sitzung leer oder nicht gefunden")
    patient_name = req.patient_name.strip()
    if not patient_name:
        raise HTTPException(status_code=400, detail="Patientenname erforderlich")
    slug    = name_to_slug(patient_name)
    chat_id = uuid.uuid4().hex[:12]
    first   = next((m["content"] for m in messages if m["role"] == "user"), "")
    label   = first[:70] + ("…" if len(first) > 70 else "")
    data    = load_patient(slug) or {
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
             "model": e.get("model", "cloud")} for e in entries]

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
    print("  MedAssist AI – Kombinierter Modus (Cloud + Lokal)")
    print("=" * 60)
    print(f"  Ollama:  {OLLAMA_URL}  /  Modell: {OLLAMA_MODEL}")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    print(f"  API-Key: {'OK' if has_key else 'NICHT GESETZT'}")
    print("  URL:     http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
