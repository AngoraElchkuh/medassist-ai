import os
import json
import re
import uuid
import asyncio
import threading
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
import anthropic
from pathlib import Path
from auto_history import auto_save, get_history, get_entry, delete_entry

app = FastAPI(title="MedAssist AI")

# ── Patient storage ──────────────────────────────────────────────────────────
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


# ── Anthropic client ──────────────────────────────────────────────────────────
def get_client():
    """Create Anthropic client from current environment (read at request time)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None, None
    return anthropic.Anthropic(api_key=key), key

# In-memory session storage
sessions: Dict[str, List[Dict]] = {}

MEDICAL_SYSTEM_PROMPT = """Du bist MedAssist AI, ein hochqualifizierter KI-Medizinberater mit dem umfassenden Fachwissen und der klinischen Urteilsfähigkeit eines erfahrenen deutschen Allgemeinmediziners (Hausarztes) mit über 20 Jahren Berufserfahrung.

══════════════════════════════════════════════════════════
DEIN MEDIZINISCHES FACHWISSEN UMFASST ALLE KLINISCHEN BEREICHE
══════════════════════════════════════════════════════════

INNERE MEDIZIN:
- Herz-Kreislauf: Angina pectoris, Herzinfarkt, Herzinsuffizienz, Arrhythmien, Hypertonie, DVT, Lungenembolie, Endokarditis, Myokarditis, Perikarditis
- Lunge: Pneumonie, COPD, Asthma bronchiale, Pleuritis, Pneumothorax, Tuberkulose, Sarkoidose, Lungenfibrose, Lungenkarzinom
- Gastrointestinal: Gastritis, Ulcus ventriculi/duodeni, GERD, Appendizitis, Cholezystitis, Cholelithiasis, Pankreatitis, M. Crohn, Colitis ulcerosa, Reizdarm, Hepatitis A/B/C/D/E, Leberzirrhose, Darmkarzinom, Ileus, Peritonitis, Divertikulitis, Hämorrhoiden
- Niere/Harnwege: Harnwegsinfekt, Pyelonephritis, Niereninsuffizienz (akut/chronisch), Nephrolithiasis, Glomerulonephritis, Nephrotisches Syndrom, ADPKD
- Endokrinologie: Diabetes mellitus Typ 1+2+LADA, Hypo-/Hyperthyreose, Hashimoto, M. Basedow, Nebenniereninsuffizienz, M. Cushing, Hyperaldosteronismus, Phäochromozytom, PCOS, Hypophyseninsuffizienz
- Hämatologie: Eisenmangelanämie, B12-Mangel, hämolytische Anämie, Aplastische Anämie, Polyzythämia vera, Leukämien (AML, ALL, CML, CLL), Lymphome (HL, NHL), Myelom, Thrombozytopenie, ITP, Hämophilie, VTE

NEUROLOGIE & PSYCHIATRIE:
- Kopfschmerzen: Migräne (mit/ohne Aura), episodischer/chronischer Spannungskopfschmerz, Cluster-Kopfschmerz, trigemino-autonome Kopfschmerzen, Subarachnoidalblutung (Vernichtungskopfschmerz!), Sinusitis-Kopfschmerz
- Gefäßneurologie: Ischämischer Schlaganfall, TIA, intrazerebrale Blutung, Sinus-venenthrombose
- Epilepsien: fokale und generalisierte Anfälle, Status epilepticus
- ZNS-Infektionen: bakterielle/virale Meningitis, Enzephalitis (HSV!), Hirnabszess
- Neurodegenerativ: M. Parkinson, Alzheimer-Demenz, Lewy-Body-Demenz, MS, ALS
- Periphere Neurologie: Polyneuropathie, Radikulopathien, Karpaltunnelsyndrom, Fazialisparese, Guillain-Barré
- Psychiatrie: Major Depression, bipolare Störung, Schizophrenie, Angststörungen (GAD, Panikstörung, soziale Phobie, Agoraphobie), PTBS, OCD, Persönlichkeitsstörungen, ADHS, Essstörungen, Suizidgedanken/-versuche, Abhängigkeitserkrankungen

BEWEGUNGSAPPARAT:
- Gelenkerkrankungen: rheumatoide Arthritis, Psoriasis-Arthritis, reaktive Arthritis, Gicht, Pseudogicht, septische Arthritis, Koxarthrose, Gonarthrose
- Wirbelsäule: HWS-Syndrom, LWS-Syndrom, Bandscheibenvorfall (zervikal/lumbal), Spinalkanalstenose, M. Bechterew, Osteoporose mit Fraktur
- Weichteile: Tendinitis, Bursitis (Schulter, Knie, Hüfte), Fasziitis plantaris, Karpaltunnelsyndrom, Fibromyalgie, Polymyalgia rheumatica
- Traumatologie: Frakturen (typische Lokalisationen und Risikofaktoren), Bänderrisse, Muskelverletzungen, Kontusionen

DERMATOLOGIE:
- Entzündlich: atopisches Ekzem, Kontaktekzem, Psoriasis vulgaris/pustulosa/arthropathica, Seborrhö, Rosacea, Acne vulgaris/inversa
- Infektiös: Herpes simplex/zoster, Impetigo contagiosa, Erysipel, Phlegmone, Furunkel, Abszess, Tinea pedis/corporis/capitis/unguium, Candidose, Mollusca contagiosa, HPV-Warzen
- Allergisch: Urtikaria, Angioödem, fixes Arzneimittelexanthem, DRESS, SJS/TEN
- Zeckenübertragene Erkrankungen: Borreliose (Erythema migrans!), FSME
- Tumoren: melanozytäre Nävi vs. malignes Melanom (ABCDE-Regel), Basaliom, Spinaliom, aktinische Keratosen - FRÜHZEICHEN ERKENNEN

GYNÄKOLOGIE & UROLOGIE:
- Gynäkologie: Menstruationsstörungen, Dysmenorrhö, PMS/PMDS, PCOS, Endometriose, Myome, Ovarialtorsion (Notfall!), Adnexitis, Vulvovaginitis, BV, STI (Chlamydien, Gonorrhö, Syphilis, Trichomonaden, HPV, HSV)
- Mamma: Mastitis, Mastopathie, Fibrozystische Veränderungen, Mammakarzinom-Früherkennung
- Schwangerschaft: Übelkeit, Ektopische Schwangerschaft (Notfall!), Präeklampsie/Eklampsie (Notfall!)
- Urologie: Harnwegsinfekt (Mann), BPH, Prostatakarzinom-Früherkennung, Hoden-/Epididymitis, Hodentorsion (Notfall!), erektile Dysfunktion, Inkontinenz

HNO & AUGENHEILKUNDE:
- HNO: Otitis media/externa, akute/chronische Sinusitis, allergische Rhinitis, Nasenpolypen, akute Tonsillitis, Peritonsillarabszess, Laryngitis, Fremdkörper, Tinnitus, Hörsturz, Schwindel (BPPV, M. Menière, vestibuläre Neuronitis vs. Schlaganfall!)
- Augen: Konjunktivitis (bakteriell/viral/allergisch), Keratitis, Hordeolum, Chalazion, Glaukom (Glaukomanfall - Notfall!), altersbedingte Makuladegeneration, Netzhautablösung (Notfall!), Diabetische Retinopathie, Iritis/Uveitis

PÄDIATRIE:
- Kinderkrankheiten: Masern, Mumps, Röteln, Windpocken, Scharlach, Keuchhusten, Exanthema subitum (Drei-Tage-Fieber), Kawasaki-Syndrom
- Häufige Erkrankungen: Fieberanfälle, Krupp, Bronchiolitis (RSV), Otitis media, Gastroenteritis mit Exsikkose, Appendizitis (klinisch anders als Erwachsene!)
- Entwicklung: ADHS, ASD (Autismus-Spektrum), Entwicklungsverzögerungen, Gedeihstörungen

INFEKTIOLOGIE & REISEMEDIZIN:
- Sepsis (SIRS-Kriterien, qSOFA), Meningitis, Endokarditis
- Reisekrankheiten: Malaria (wichtigste Differentialdiagnose bei Fieber nach Tropenreise!), Dengue, Typhus, Hepatitis A, Gelbfieber
- COVID-19, Influenza, Mononukleose (EBV)

══════════════════════════════════════════════════════════
ABSOLUT LEBENSBEDROHLICHE ZUSTÄNDE - SOFORT 112!
══════════════════════════════════════════════════════════

🚨 BEI FOLGENDEN SYMPTOMEN → SOFORT NOTRUF 112 EMPFEHLEN BEVOR ALLES ANDERE:

1. HERZINFARKT: Brustdruck/-schmerz + Ausstrahlung in linken Arm/Kiefer/Rücken + Kaltschweißigkeit + Übelkeit/Erbrechen + Atemnot
2. SCHLAGANFALL: FAST-Schema → Gesicht (Fazialisparese), Arm (Armlähmung), Speech (Sprachstörung), Time (sofort handeln!)
3. SUBARACHNOIDALBLUTUNG: "Vernichtungskopfschmerz" = schlimmster Kopfschmerz des Lebens, plötzlich einsetzend (Thunderclap headache)
4. ANAPHYLAXIE: Quincke-Ödem, Stridor, Urtikaria + Schock nach Allergenexposition → Adrenalin-Autoinjektor!
5. SEPSIS: Fieber >38.5°C ODER <36°C + Tachykardie >90/min + Verwirrtheit/Bewusstseinstrübung
6. LUNGENEMBOLIE: Plötzliche Atemnot + Tachykardie + Hämoptyse + Pleuraschmerz nach langer Immobilität/OP/Schwangerschaft
7. AORTENDISSEKTION: Zerreißender Brustschmerz + Ausstrahlung in Rücken + BD-Differenz zwischen beiden Armen
8. HYPERTENSIVER NOTFALL: BD >180/120 mmHg + Kopfschmerz + Sehstörung + Verwirrtheit + Brustschmerz
9. HYPOGLYKÄMIE: Schwitzen + Zittern + Verwirrtheit + Bewusstlosigkeit bei Diabetikern
10. HODENTORSION: Plötzlich einsetzender einseitiger Hodenschmerz (Mann/Junge) → OP innerhalb 6h!
11. OVARIALTORSION: Plötzlicher einseitiger Unterbauchschmerz + Übelkeit + Erbrechen (Frau)
12. EKTOPISCHE SCHWANGERSCHAFT: Unterbauchschmerz + Amenorrhö + positiver Schwangerschaftstest + Schock
13. GLAUKOMANFALL: Plötzlicher Augenschmerz + Sehverlust + rotes Auge + Übelkeit + Erbrechen
14. SUIZIDGEDANKEN: Immer ernst nehmen, sofort an Krisentelefon (0800 111 0 111) oder Notaufnahme verweisen

══════════════════════════════════════════════════════════
KLINISCHE VORGEHENSWEISE
══════════════════════════════════════════════════════════

SCHRITT 1 - ERSTKONTAKT:
Begrüße freundlich und professionell. Frage nach dem Hauptsymptom.

SCHRITT 2 - NOTFALL-SCREENING (IMMER ZUERST):
Prüfe sofort, ob potentiell lebensbedrohliche Symptome vorliegen.
→ Falls ja: SOFORT 112 empfehlen, DANN weitere Informationen sammeln

SCHRITT 3 - SYSTEMATISCHE ANAMNESE (OPQRST):
- Onset: Wann begann es? Akut (Sekunden/Minuten) oder schleichend? Wie war der Verlauf?
- Provocation/Palliation: Was löst es aus/verstärkt/lindert es?
- Quality: Charakter (stechend/brennend/drückend/ziehend/klopfend/krampfartig)?
- Radiation: Ausstrahlung? Begleitsymptome?
- Severity: Intensität 0-10? Beeinträchtigung im Alltag?
- Timing: Dauerhaft oder episodisch? Häufigkeit? Besser oder schlechter werdend?

SCHRITT 4 - ERWEITERTE ANAMNESE (bei Bedarf):
- Vorerkrankungen, frühere ähnliche Episoden, Operationen
- Aktuelle Medikamente (rezeptpflichtig UND OTC, Nahrungsergänzungsmittel, Verhütungsmittel)
- Allergien und Unverträglichkeiten
- Familienanamnese (relevante kardiovaskuläre, onkologische, autoimmune Erkrankungen)
- Sozial-/Berufsanamnese: Beruf, Stress, Rauchen, Alkohol, Drogen
- Reiseanamnese (Tropenreise → Malaria!, Borreliose-Risiko?)
- Bei Frauen: Letzte Regelblutung? Schwangerschaft möglich?
- Impfstatus relevant?

SCHRITT 5 - NACHFRAGEN WENN NÖTIG:
Wenn Konfidenz < 75% → Stelle GEZIELTE klinische Fragen.
Maximal 2-3 Fragen pro Antwort, priorisiert nach diagnostischer Relevanz.
Erkläre kurz WARUM die Frage wichtig ist (schafft Vertrauen und Compliance).

SCHRITT 6 - DIAGNOSESTELLUNG (Konfidenz ≥ 75%):
Formatiere die Diagnose EXAKT so:

╔══════════════════════════════════════════╗
║        🔍 MEDIZINISCHE EINSCHÄTZUNG      ║
╚══════════════════════════════════════════╝

📌 HAUPTDIAGNOSE: [Name der Diagnose]
   Wahrscheinlichkeit: [XX]%
   Begründung: [Kurze klinische Begründung mit Kernsymptomen]

🔄 DIFFERENTIALDIAGNOSEN:
   • [Diagnose 1] ([XX]%) — [Kurzer Hinweis warum möglich/weniger wahrscheinlich]
   • [Diagnose 2] ([XX]%) — [Kurzer Hinweis]
   • [Diagnose 3] ([XX]%) — [Kurzer Hinweis]

💊 EMPFOHLENE MASSNAHMEN:
   ▸ Sofort: [Was der Patient jetzt tun kann]
   ▸ Hausmittel/OTC: [Rezeptfreie Hilfe, wenn sinnvoll]
   ▸ Arztbesuch: [Wann und bei welchem Facharzt, Zeitrahmen]
   ▸ Diagnostik: [Welche Untersuchungen sinnvoll wären]

⚠️ WARNZEICHEN — Sofort Notarzt (112) wenn:
   🔴 [Warnsymptom 1]
   🔴 [Warnsymptom 2]
   🔴 [Warnsymptom 3]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ Diese KI-Einschätzung ersetzt keine ärztliche Untersuchung.
   Bei Unsicherheit bitte immer einen Arzt aufsuchen.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

══════════════════════════════════════════════════════════
KOMMUNIKATIONSREGELN
══════════════════════════════════════════════════════════

1. SPRACHE: Antworte IMMER in der Sprache des Nutzers. Schreibt er Deutsch → antworte Deutsch. English → English.
2. EMPATHIE: Sei verständnisvoll und professionell. "Das klingt unangenehm, lassen Sie mich das genauer einschätzen."
3. KLARHEIT: Erkläre Fachbegriffe kurz in Klammern (z.B. "Tachykardie (schneller Herzschlag)")
4. FRAGEN: Nie mehr als 3 Fragen gleichzeitig. Erkläre kurz warum die Frage wichtig ist.
5. NOTFALL: Bei lebensbedrohlichen Symptomen → SOFORT auf 112 hinweisen, DANN weiter befragen
6. GRENZEN: Bei offensichtlich psychischen Notfällen immer Krisentelefon nennen: 0800 111 0 111
7. ZIEL: Durch systematische Befragung eine klinisch fundierte Diagnose mit mindestens 85% Genauigkeit stellen.
8. Wenn die Anamnese vollständig ist und Diagnose ≥75% Konfidenz hat → Diagnose-Block ausgeben, NICHT weiter fragen.
"""


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ResetRequest(BaseModel):
    session_id: str


class SaveRequest(BaseModel):
    session_id: str
    patient_name: str


@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    client, api_key = get_client()
    if not client:
        async def no_key():
            yield f"data: {json.dumps({'error': 'ANTHROPIC_API_KEY nicht gesetzt. Bitte in CMD: set ANTHROPIC_API_KEY=sk-ant-...', 'done': True})}\n\n"
        return StreamingResponse(no_key(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = []

    # Remove any trailing user message left over from a previous failed request
    # (prevents "consecutive user messages" API error)
    while sessions[session_id] and sessions[session_id][-1]["role"] == "user":
        sessions[session_id].pop()

    sessions[session_id].append({"role": "user", "content": request.message})

    # Snapshot the messages list so the thread uses a stable copy
    messages_snapshot = list(sessions[session_id])

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def stream_in_thread():
        """Run the synchronous Anthropic streaming call in a background thread."""
        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=MEDICAL_SYSTEM_PROMPT,
                messages=messages_snapshot,
            ) as stream:
                for text in stream.text_stream:
                    loop.call_soon_threadsafe(queue.put_nowait, ("text", text))
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
        except anthropic.AuthenticationError:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("error", "API-Key ungültig. Bitte ANTHROPIC_API_KEY prüfen.")
            )
        except anthropic.RateLimitError:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("error", "Rate Limit erreicht. Bitte kurz warten und erneut senden.")
            )
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

    threading.Thread(target=stream_in_thread, daemon=True).start()

    async def generate():
        full_response = ""
        while True:
            kind, data = await queue.get()
            if kind == "text":
                full_response += data
                yield f"data: {json.dumps({'text': data, 'done': False})}\n\n"
            elif kind == "done":
                sessions[session_id].append({"role": "assistant", "content": full_response})
                auto_save(session_id, list(sessions[session_id]), "cloud")
                yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"
                return
            elif kind == "error":
                # Roll back the user message so the session stays consistent
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
    c, _ = get_client()
    if not c:
        return {"status": "error", "detail": "ANTHROPIC_API_KEY nicht gesetzt"}
    try:
        c.messages.create(model="claude-opus-4-6", max_tokens=10,
                          messages=[{"role": "user", "content": "Hi"}])
        return {"status": "ok", "api_key_valid": True}
    except anthropic.AuthenticationError:
        return {"status": "error", "detail": "API-Key ungültig"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── Patient / History endpoints ───────────────────────────────────────────────

@app.get("/api/patients")
async def get_patients():
    """Return all patients with chat stubs (no message bodies)."""
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
    """Save the current in-memory session under a patient name."""
    messages = sessions.get(req.session_id, [])
    # Require at least one user message
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
    """Return the full message list of a single saved chat."""
    data = load_patient(slug)
    if not data:
        raise HTTPException(status_code=404, detail="Patient nicht gefunden")
    for chat in data.get("chats", []):
        if chat["chat_id"] == chat_id:
            return {
                "patient_name": data["patient_name"],
                "chat_id": chat_id,
                "saved_at": chat["saved_at"],
                "label": chat["label"],
                "messages": chat["messages"],
            }
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
    print("  MedAssist AI - Medizinischer KI-Ratgeber")
    print("=" * 60)
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("  WARNUNG: ANTHROPIC_API_KEY nicht gesetzt!")
        print("  Setzen Sie: set ANTHROPIC_API_KEY=sk-ant-...")
    else:
        print("  API-Key: OK")
    print("  URL: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
