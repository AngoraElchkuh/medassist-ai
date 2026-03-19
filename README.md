# 🏥 MedAssist AI — KI-Medizinberater / AI Medical Advisor

> **⚠️ Wichtiger Hinweis / Important Notice:**
> MedAssist AI ist ein KI-gestützter Ratgeber und ersetzt **keine** ärztliche Untersuchung.
> MedAssist AI is an AI-powered advisor and does **not** replace medical examination.
> Bei Notfällen sofort **112** anrufen / In emergencies call **112** immediately.

---

## 🇩🇪 Deutsch

### Was ist MedAssist AI?

MedAssist AI ist ein lokaler KI-Medizinberater, der auf dem Wissen eines erfahrenen Allgemeinmediziners basiert. Er hilft dabei, Symptome systematisch zu erfassen, Differentialdiagnosen zu erstellen und passende Maßnahmen zu empfehlen — vollständig privat auf deinem eigenen Rechner.

### ✨ Funktionen

- 🔍 **Systematische Anamnese** nach dem OPQRST-Schema
- 📋 **Strukturierte Diagnosen** mit Wahrscheinlichkeiten und Differentialdiagnosen
- 🚨 **Notfall-Erkennung** mit automatischem 112-Hinweis
- ☁️ **Cloud-Modus** — Claude Opus (Anthropic API)
- 💻 **Lokal-Modus** — Ollama (komplett offline, keine Daten verlassen den PC)
- ⚡ **Vergleichs-Modus** — Cloud & Lokal parallel nebeneinander
- 🕐 **Automatischer Verlauf** — letzte 10 Diagnosen automatisch gespeichert
- 💾 **Patientenakten** — Sitzungen manuell unter Patientennamen speichern
- 📍 **Länderspezifische Notfallnummern** — automatisch per Standort (🇩🇪🇦🇹🇨🇭)
- 🩺 **Hausarzt speichern** — mit Direktanruf und Google Maps Link
- 🔄 **Automatische Updates** — neue Versionen direkt aus dem Launcher installieren
- 🎤 **Spracheingabe** — Beschwerden per Mikrofon eingeben
- 🔊 **Sprachausgabe** — Antworten vorlesen lassen

### 🚀 Installation

1. **Python 3.11+** installieren: [python.org](https://python.org)
2. **Ollama** installieren (für Lokal-Modus): [ollama.com](https://ollama.com)
3. Setup-Datei `setup.pyw` ausführen — der Assistent führt durch die Installation
4. Nach der Installation: Launcher über die Desktop-Verknüpfung starten

### 📋 Voraussetzungen

| Modus | Voraussetzung |
|-------|--------------|
| ☁️ Cloud | Anthropic API-Key ([console.anthropic.com](https://console.anthropic.com)) |
| 💻 Lokal | Ollama + `ollama pull llama3.1:8b` |
| ⚡ Beide | API-Key + Ollama |

### 🗂️ Projektstruktur

```
medassist-ai/
├── app.py              # Cloud-Server (Anthropic)
├── app_local.py        # Lokal-Server (Ollama)
├── app_combined.py     # Kombinierter Server (Cloud + Lokal)
├── auto_history.py     # Automatischer Verlauf
├── launcher.pyw        # GUI-Starter
├── requirements.txt    # Python-Abhängigkeiten
├── version.txt         # Aktuelle Versionsnummer
├── update.json         # Update-Konfiguration
└── templates/
    └── index.html      # Web-Oberfläche
```

### 🔒 Datenschutz

- Im **Lokal-Modus** verlassen **keine Daten** den PC
- `config.json` (API-Key) und `patients/` (Patientendaten) werden **nicht** auf GitHub gespeichert
- Standortdaten für Notfallnummern werden nur lokal im Browser gecacht

---

## 🇬🇧 English

### What is MedAssist AI?

MedAssist AI is a local AI medical advisor based on the knowledge of an experienced general practitioner. It helps systematically record symptoms, create differential diagnoses and recommend appropriate measures — completely privately on your own computer.

### ✨ Features

- 🔍 **Systematic anamnesis** using the OPQRST schema
- 📋 **Structured diagnoses** with probabilities and differential diagnoses
- 🚨 **Emergency detection** with automatic emergency number alerts
- ☁️ **Cloud mode** — Claude Opus (Anthropic API)
- 💻 **Local mode** — Ollama (completely offline, no data leaves the PC)
- ⚡ **Compare mode** — Cloud & Local running side by side
- 🕐 **Auto history** — last 10 diagnoses saved automatically
- 💾 **Patient records** — manually save sessions under patient names
- 📍 **Country-specific emergency numbers** — auto-detected by location (🇩🇪🇦🇹🇨🇭)
- 🩺 **Save your GP** — with direct call link and Google Maps
- 🔄 **Automatic updates** — install new versions directly from the launcher
- 🎤 **Voice input** — describe symptoms via microphone
- 🔊 **Text-to-speech** — have responses read aloud

### 🚀 Installation

1. Install **Python 3.11+**: [python.org](https://python.org)
2. Install **Ollama** (for local mode): [ollama.com](https://ollama.com)
3. Run `setup.pyw` — the wizard guides you through installation
4. After installation: launch via the desktop shortcut

### 📋 Requirements

| Mode | Requirement |
|------|-------------|
| ☁️ Cloud | Anthropic API Key ([console.anthropic.com](https://console.anthropic.com)) |
| 💻 Local | Ollama + `ollama pull llama3.1:8b` |
| ⚡ Both | API Key + Ollama |

### 🔒 Privacy

- In **local mode**, **no data** leaves your PC
- `config.json` (API key) and `patients/` (patient data) are **not** stored on GitHub
- Location data for emergency numbers is only cached locally in the browser

---

## 📝 Changelog

### v1.2.0
- 🕐 Automatic session history (last 10 diagnoses)
- 📍 Country-specific emergency numbers with location detection (DE/AT/CH)
- 🩺 Save your GP with direct call & maps link
- 🔄 Automatic update system via GitHub
- ⚡ Ollama auto-start when using local mode
- 🐛 Fixed encoding error during model download
- 🐛 Fixed window resize when switching modes

### v1.0.0
- 🎉 Initial release
- ☁️ Cloud mode (Anthropic Claude)
- 💻 Local mode (Ollama)
- ⚡ Compare mode
- 💾 Patient records
- 🎤 Voice input / 🔊 Text-to-speech

---

*Built with ❤️ using FastAPI, Python & Tkinter*
