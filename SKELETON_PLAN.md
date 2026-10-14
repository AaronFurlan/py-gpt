# Plan: PyGPT als lauffähiges, leeres Agent-Harness

Stand: 14.10.2026, Basis Fork `AaronFurlan/py-gpt` auf Upstream 2.9.1 plus lokale Sicherheitsänderungen (Bestätigungssperre, HTML-Escaping, TLS-Default, Profil-Export ohne Schlüssel).

## 1. Anforderungen

1. Das leere Gerüst ist jederzeit startbar und chatfähig: Modell wählen, Nachricht senden, Antwort erhalten. Nur ohne Tools und ohne Agenten.
2. Nichts wird gelöscht. Alle vorhandenen Tools, Anbieter und Agenten bleiben im Repository und lassen sich einzeln wieder zuschalten.
3. Neues anbinden bleibt einfach, bevorzugt über MCP-Server ohne Code im Harness.

Daraus folgt: Der Umbau ist ein Umbau der **Registrierung**, nicht des Codes. Was heute fest in `app.py` steht, wird zu einer Liste in einer Profildatei. Physisches Entfernen ist kein Bestandteil dieses Plans.

## 2. Begriffe, die in PyGPT doppelt belegt sind

| Begriff im Code | Bedeutung | Für das Gerüst |
|---|---|---|
| **Plugin** (`plugin/`, 37 Stück) | Werkzeuge, die das **Modell** aufrufen kann: Shell, Dateien, Web, MCP, Maus, Slack, GitHub | Das sind die "Tools" im Sinn dieses Plans. Im Gerüst: keine aktiv. |
| **Tool** (`tools/`, 16 Stück) | **Oberflächen**-Werkzeuge für den Nutzer: Notizblock, Dateibrowser, Painter, Kalender, Terminal | Keine KI-Fähigkeit. Können im Gerüst bleiben, kosten nur Menüeinträge. |
| **Agent** (`provider/agents`, 21 Stück) | Agenten-Typen für den Agenten-Modus: Planner, Supervisor, Experts, auf Basis OpenAI Agents SDK oder llama-index | Im Gerüst: keine aktiv. |
| **LLM** (`provider/llms`, 20 Stück) | Anbieter-Anbindungen | Im Gerüst: wenige aktiv, mindestens einer nötig. |
| **Loader, Vector Store, Audio** | Chat mit Dateien, Sprache | Im Gerüst: keine aktiv. |

## 3. Zielbild des Gerüsts

Aktiv beim Start:

- Chat-Schleife, Kontext-Datenbank, Presets, Einstellungen, Profile
- Tool-Dispatcher mit Bestätigungssperre und Sicherheits-Policy, auch wenn kein Tool registriert ist
- LLM-Anbieter: `openai`, `anthropic`, `ollama`, `custom` (OpenAI-kompatible Endpunkte)
- Plugin `mcp`, aber ohne eingetragene Server. Damit ist das Anbinden eines MCP-Servers ein reiner Konfigurationsschritt.
- Oberflächen-Werkzeuge nach Wunsch, Vorschlag: Notizblock und Dateibrowser bleiben, der Rest aus.

Inaktiv, aber im Repo: alle anderen Plugins, alle Agenten, alle Loader und Vektorspeicher, Audio, Realtime, Vision.

Zuschalten eines vorhandenen Tools heißt: eine Zeile im Startprofil aktivieren, App neu starten, danach wie gewohnt in den Plugin-Einstellungen einschalten.

## 4. Stufen

### Stufe 0: Baseline sichern (eine Stunde)

- Sicherheitsänderungen committen, Tag `skeleton-base`.
- Testreferenz festhalten: 62 bekannte Windows-Fehler, keine echten Defekte.
- `.claude/` in `.gitignore`.

### Stufe 1: Registry und Startprofil (zwei bis drei Tage)

Ziel: Was geladen wird, steht in einer Datei.

- Die rund 160 `launcher.add_*`-Aufrufe aus `app.py` in `bootstrap/registry.py` überführen. Pro Art eine Tabelle `id -> Importpfad`: plugins, llms, agents, tools, loaders, vector_stores, audio_input, audio_output, web.
- Startprofil `skeleton.json` im Konfigurationsverzeichnis: pro Art eine Liste aktiver IDs. Fehlt die Datei, gilt das Vollprofil, also das heutige Verhalten. So bleibt der Fork mit Upstream kompatibel.
- Importe erfolgen nur für aktive IDs. Ein inaktiver Eintrag wird weder importiert noch instanziiert. Fehlende Abhängigkeiten inaktiver Einträge stören den Start nicht.
- Zwei Profile ausliefern: `full` (alles, wie heute) und `skeleton` (siehe Zielbild). Umschalten über Startparameter oder Einstellung.

### Stufe 2: Kern gegen fehlende Registrierungen härten (ein bis zwei Tage)

Der Kern setzt heute an einigen Stellen voraus, dass bestimmte Plugins und Oberflächen-Werkzeuge existieren. Ohne diese Härtung stürzt das leere Gerüst ab. Gefundene Stellen:

| Stelle | Erwartet | Problem |
|---|---|---|
| `controller/chat/common.py`, `controller/chat/input.py`, `controller/access/*.py`, `controller/audio/audio.py` | Plugin `audio_input` | Wird im Sende- und Stopp-Pfad ohne Prüfung aufgerufen. Ohne das Plugin bricht der Chat. |
| `controller/ctx/extra.py`, `controller/tools/tools.py` | Plugin `filesystem` | "Code ausführen" aus der Chat-Ansicht, Sandbox neu bauen. |
| `controller/access/control.py` und weitere, rund 190 Aufrufe | Oberflächen-Werkzeuge `files`, `notepad`, `painter`, `interpreter`, `editor`, `indexer`, `calendar`, `web_browser` | `tools.get()` liefert bei Unbekanntem `None`, die Aufrufer prüfen das nicht. |
| Agenten-Modus | mindestens ein Agent | Verhalten bei leerer Liste prüfen. |

Vorgehen: Zugriffe über kleine Hilfsfunktionen leiten, die bei fehlender Registrierung still nichts tun oder den Menüeintrag ausblenden. Abnahmekriterium: Start mit leerem Profil, Chat über `custom` gegen einen lokalen Endpunkt, Tool-Aufruf im Modelltext ohne registriertes Tool erzeugt eine saubere Meldung statt eines Fehlers.

Übergangslösung, falls Stufe 2 später kommen soll: `audio_input` im Gerüst-Profil aktiv lassen. Es ist kein KI-Tool, sondern Spracheingabe, und beseitigt den größten Teil der Abstürze sofort.

### Stufe 3: Erweiterungs-API festziehen (zwei bis drei Tage)

- **MCP zuerst.** Server in der MCP-Verwaltung eintragen, Tools werden entdeckt und erscheinen als `<server>_<tool>`. Ergänzung: Beim Aktivieren eines Servers kommt `<server>_*` automatisch in die Bestätigungsliste, abschaltbar pro Server.
- **Vorhandenes Tool zuschalten.** ID im Startprofil aktivieren. Dokumentierte Liste aller IDs mit Einzeiler, was das Tool kann und welche Abhängigkeiten es braucht.
- **Neues Plugin.** Vorlage `plugin/_template` mit `config.py`, `plugin.py`, `worker.py`. Auto-Discovery: ein Ordner unter `plugin/` mit `manifest.json` registriert sich selbst, ohne Eintrag in der Registry.
- **Neuer LLM-Anbieter.** Für OpenAI-kompatible Endpunkte reicht `custom`. Sonst Vorlage auf Basis `provider/llms/base.py`.
- **Neuer Agent.** Vorlage auf Basis `provider/agents/base.py`. Vorhandene Agenten werden einzeln über das Profil zugeschaltet. Es müssen nicht beide Frameworks gleichzeitig aktiv sein.
- Entwickler-Doku `EXTENDING.md`: Profilformat, die Vorlagen, Sicherheitsregeln.

### Stufe 4: Sicherheitsstandard des Gerüsts (ein Tag)

- Werkzeuge global aus, Bestätigungssperre an, Prompt-Injection-Hinweis an. Das ist bereits Standard.
- Standard-Sandbox für Code-Ausführung auf `docker` statt `builtin`, mit klarer Meldung, wenn Docker fehlt.
- MCP-Server nur aus Profil und Einstellungen, kein automatisches Verbinden auf Zuruf des Modells.

### Optional, später: Abhängigkeiten entschlacken

Weil Code nicht entfernt wird, bleiben die 387 Abhängigkeiten in `requirements.txt`. Möglich ist eine Aufteilung in `requirements-core.txt` und optionale Gruppen (`audio`, `files`, `vision`, `integrations`). Das Gerüst-Profil läuft dann mit der Core-Gruppe, und ein zugeschaltetes Tool nennt seine Gruppe. Das ist Aufräumarbeit ohne Einfluss auf die Funktion und kann jederzeit nachgeholt werden.

## 5. Risiken

- **Upstream-Merges.** Solange nichts gelöscht wird und das Vollprofil das heutige Verhalten liefert, bleiben Merges machbar. Konflikte entstehen vor allem in `app.py`, dort wo Upstream neue Registrierungen hinzufügt. Das ist beherrschbar, weil die Registry an einer Stelle liegt.
- **Versteckte Annahmen.** Die Liste in Stufe 2 stammt aus einer Suche nach direkten Zugriffen. Weitere Stellen tauchen beim Start mit leerem Profil auf, deshalb ist der Abnahmetest dort der Maßstab.
- **Config-Patches.** `provider/core/config/patches` verweisen auf Plugin-IDs. Da die Plugins im Repo bleiben, ändert sich hier nichts.

## 6. Nächster konkreter Schritt

Stufe 0 und Stufe 1: Registry-Modul, Startprofil, Profile `full` und `skeleton`, Start der App im Gerüst-Modus. Dabei wird die Liste aus Stufe 2 automatisch vollständig, weil jeder Absturz eine fehlende Absicherung markiert.
