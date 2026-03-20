# MedAssist AI — Funktionsbeschreibung

> Letzte Aktualisierung: März 2026 | Version 1.2.0

---

## Übersicht

MedAssist AI ist ein lokaler KI-Gesundheitsassistent, der auf Anthropic Claude (Cloud) und Ollama (lokal) basiert. Die Anwendung läuft vollständig auf dem eigenen Rechner — keine Cloud-Pflicht, keine Datenweitergabe an Dritte.

---

## 1. KI-Diagnose-Modi

### ☁️ Cloud-Modus (Anthropic Claude)
- Verbindung zur Anthropic API mit wählbarem Modell (z. B. claude-opus-4-5, claude-3-5-sonnet)
- Antworten werden als Echtzeit-Stream dargestellt (Wörter erscheinen live)
- Erfordert einen gültigen Anthropic API-Schlüssel

### 💻 Lokal-Modus (Ollama)
- Verwendet ein lokal installiertes Modell über Ollama (z. B. llama3, mistral, gemma)
- Vollständig offline — keine Internetverbindung nötig
- Ollama wird beim Programmstart automatisch gestartet falls nicht aktiv

### ⚖️ Vergleichsmodus (Cloud + Lokal parallel)
- Beide Modelle werden gleichzeitig befragt
- Antworten werden nebeneinander angezeigt
- Ideal um Qualität und Unterschiede der Modelle zu vergleichen

---

## 2. Eingabe-Optionen

### ⌨️ Texteingabe
- Freitextfeld für Symptome, Fragen und Antworten
- Senden per Enter-Taste oder Senden-Button

### 🎤 Spracheingabe (Voice)
- Mikrofon-Button startet die Spracherkennung (Web Speech API)
- **Pause-Funktion**: Aufnahme pausieren ohne den bisher erkannten Text zu verlieren
- **Kein automatischer Abbruch**: Sprechpausen brechen die Aufnahme nicht mehr ab (Timeout stark erhöht)
- Aufnahme wird beim Senden automatisch gestoppt
- Eingabefeld wird nach dem Senden geleert

---

## 3. Sprachausgabe (Text-to-Speech)

### 🔊 Globaler TTS-Toggle
- Schalter in der oberen Leiste aktiviert automatisches Vorlesen jeder neuen Antwort

### 🔊 Nachrichten-Vorlesen (per Nachricht)
- Jede KI-Antwort hat einen eigenen Lautsprecher-Button (erscheint beim Hovern)
- Klick startet das Vorlesen der jeweiligen Nachricht
- Während des Vorlesens wird der Button zu ⏹ (Stopp)
- Zweiter Klick stoppt die Wiedergabe sofort
- Bevorzugt hochwertige "Natural"-Stimmen (z. B. Microsoft Conrad / Katja in Edge)

### 📊 TTS-Fortschrittsleiste
- Zeigt den aktuellen Vorlesefortschritt visuell an
- Klick in die Leiste springt zur gewünschten Textstelle (Seek)
- Passagen können so mehrfach vorgelesen werden

---

## 4. Notfallnummern

### 📍 Standortbasierte Anzeige
- Erkennt den Standort über die Browser-Geolocation-API
- Reverse Geocoding über OpenStreetMap Nominatim (kostenlos, kein API-Key nötig)
- Nummern werden **nur nach** Bestätigung oder Ablehnung der Standortfreigabe angezeigt

### 🆘 Länderspezifische Nummern
Unterstützte Länder mit vollständigen Notfallnummern:

| Land | Notruf | Ärztl. Notdienst | Polizei | Gift-Notruf |
|------|--------|------------------|---------|-------------|
| 🇩🇪 Deutschland | 112 | 116 117 | 110 | 030 19240 |
| 🇦🇹 Österreich | 144 | 141 | 133 | 01 406 43 43 |
| 🇨🇭 Schweiz | 144 | 0900 57 67 47 | 117 | 145 |

### 🗺️ Regionale Notdienstnummern
- **Deutschland**: Alle 16 Bundesländer mit lokalen KV-Notdienstnummern
- **Österreich**: Alle 9 Bundesländer mit regionalen Nummern
- **Schweiz**: 6 Kantone mit kantonalen Notdienstinfos
- Manuelle Standortauswahl möglich wenn Geolocation verweigert wird
- 24-Stunden-Cache im Browser (kein erneutes Abfragen nötig)

---

## 5. Hausarzt-Verwaltung

- Name, Fachrichtung, Telefonnummer und Adresse des eigenen Hausarztes speichern
- Direkter Anruf per `tel:`-Link (auf Mobilgeräten)
- Google Maps-Link zur Praxisadresse
- Daten werden lokal im Browser gespeichert (localStorage)
- Bearbeiten und Löschen jederzeit möglich

---

## 6. Sitzungs-Verwaltung

### 💾 Manuelles Speichern unter Patientenname
- Sitzung mit Name und optionalem Patientenkürzel speichern
- Mehrere Sitzungen pro Patient möglich
- Abrufbar über das Patienten-Archiv

### 🕐 Auto-Verlauf (letzte 10 Diagnosen)
- Die letzten 10 Diagnosesitzungen werden **automatisch** gespeichert
- Kein manuelles Speichern nötig
- Abrufbar über den "🕐 Letzte Diagnosen"-Button
- Gleiche Sitzung wird aktualisiert, keine Duplikate

### 📂 Archivierte Sitzungen fortführen
- Gespeicherte Sitzungen können im **Lese-Modus** geöffnet werden
- **"▶ Sitzung fortführen"**-Button: Lädt den gesamten bisherigen Gesprächsverlauf als Kontext in die KI
- Die KI kennt dann alle vorherigen Symptome und Antworten und kann tiefer analysieren
- Alternativ: "Neue Sitzung starten" für einen leeren Neustart

---

## 7. Symptom-Panel (Seitenleiste)

- Erkannte Symptome werden während des Gesprächs automatisch extrahiert und angezeigt
- Übersichtliche Liste in der rechten Seitenleiste
- Aktualisiert sich mit jeder Antwort der KI

---

## 8. Auto-Update-System

- Beim Programmstart wird automatisch nach einer neuen Version gesucht (GitHub)
- Gelbes Banner erscheint wenn eine neuere Version verfügbar ist
- Klick auf das Banner zeigt das Changelog der neuen Version
- Nach Bestätigung: automatischer Download, Extraktion und Neustart
- Benutzerdaten (config.json, auto_history.json, Patientenordner) bleiben erhalten
- Update-Quelle konfigurierbar über `update.json`

---

## 9. Technische Details

| Komponente | Technologie |
|-----------|-------------|
| Backend | Python · FastAPI · Server-Sent Events (SSE) |
| Frontend | HTML · CSS · Vanilla JavaScript |
| Cloud-KI | Anthropic Claude API |
| Lokal-KI | Ollama (llama3, mistral, gemma, …) |
| Launcher | Python Tkinter (.pyw) |
| Standort | Browser Geolocation + OpenStreetMap Nominatim |
| Spracherkennung | Web Speech API (SpeechRecognition) |
| Sprachausgabe | Web Speech API (SpeechSynthesis) |
| Datenspeicher | JSON-Dateien lokal · Browser localStorage |
| Updates | GitHub Releases / Raw-Content |

---

## 10. Datenschutz & Sicherheit

- **Lokal-Modus**: Vollständig offline, keine Daten verlassen den Rechner
- **Cloud-Modus**: Nur Gesprächsinhalte werden an Anthropic übertragen (gemäß deren Datenschutzrichtlinien)
- Standortdaten werden **nur lokal** im Browser gecacht, nicht an externe Server gesendet (außer für einmalige Reverse-Geocoding-Anfrage an OpenStreetMap)
- Keine Benutzerkonten, keine Registrierung, kein Tracking
- Alle Sitzungsdaten liegen als JSON-Dateien auf dem lokalen Rechner

---

## 11. Systemvoraussetzungen

| Anforderung | Minimum |
|------------|---------|
| Betriebssystem | Windows 10 / 11 |
| Python | 3.10+ |
| Browser | Chrome, Edge (empfohlen für bessere TTS-Stimmen), Firefox |
| Internet | Nur für Cloud-Modus und erstmalige Standortbestimmung |
| Ollama | Nur für Lokal-Modus (wird automatisch gestartet) |

---

## 12. Bekannte Einschränkungen

- TTS-Qualität im Chrome-Browser geringer als in Microsoft Edge (Edge hat Neural-Stimmen)
- Spracherkennung erfordert HTTPS oder localhost (funktioniert im lokalen Betrieb)
- Standortbestimmung funktioniert nur mit Internetzugang (Nominatim-API)
- MedAssist AI ist **kein Ersatz für medizinische Fachberatung** — dient nur zur Information

---

*MedAssist AI ist ein privates Hilfsprojekt. Alle medizinischen Inhalte sind KI-generiert und ersetzen keinen Arztbesuch.*
