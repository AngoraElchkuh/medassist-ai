# auto_history.py — Automatische Verlaufsspeicherung (letzte 10 Sitzungen)
import json, uuid
from datetime import datetime
from pathlib import Path

AUTO_HISTORY_FILE = Path(__file__).parent / "auto_history.json"
MAX_ENTRIES = 10


def _load() -> dict:
    if AUTO_HISTORY_FILE.exists():
        try:
            return json.loads(AUTO_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": []}


def _save_file(history: dict):
    try:
        AUTO_HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def auto_save(session_id: str, messages: list, model: str = "cloud") -> None:
    """Nach jeder abgeschlossenen Antwort aufrufen. Aktualisiert bestehende Session."""
    if not any(m["role"] == "user" for m in messages):
        return
    if not any(m["role"] == "assistant" for m in messages):
        return

    first_user = next((m["content"] for m in messages if m["role"] == "user"), "")
    label = first_user[:80] + ("…" if len(first_user) > 80 else "")

    history = _load()
    entries = history.get("entries", [])

    # Bestehenden Eintrag mit gleicher session_id aktualisieren
    entries = [e for e in entries if e.get("session_id") != session_id]

    entries.insert(0, {
        "id": session_id,
        "session_id": session_id,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "model": model,
        "messages": list(messages),
    })
    history["entries"] = entries[:MAX_ENTRIES]
    _save_file(history)


def get_history() -> list:
    return _load().get("entries", [])


def get_entry(entry_id: str) -> dict | None:
    for e in get_history():
        if e["id"] == entry_id:
            return e
    return None


def delete_entry(entry_id: str) -> None:
    history = _load()
    history["entries"] = [e for e in history.get("entries", []) if e["id"] != entry_id]
    _save_file(history)
