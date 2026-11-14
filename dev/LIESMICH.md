# dev-orchestrator

lokal. nichts wird von hier gepusht.

## so startest du

1. doppelklick auf `bruecke\oeffnen.py` oder im terminal: `python bruecke\oeffnen.py`
2. die maske oeffnet sich unter http://127.0.0.1:17341
3. optional dauerhaft: `python dev\warteschlange.py loop` (sonst reicht `tick` nach auftraegen)

## starten

1. maske: `python bruecke\oeffnen.py` → http://127.0.0.1:17341
2. warteschlange (optional dauerhaft): `python dev\warteschlange.py loop`
3. oder einzeln: `python dev\warteschlange.py tick`

## maske leiste

- tabs: `projekte`, `dienste`, `alle` (gruppen mit ueberschrift)
- karten per griff (6 punkte) ziehen, reihenfolge + gruppe in `maske/anordnung.json`
- api: `GET/POST /maske/anordnung` (nur ids, keine pfade)
- auftraege nur noch ueber die karten-buttons oder die api (keine befehlszeile)

## auftrag geben

per api:

```text
POST http://127.0.0.1:17341/dev/auftrag
{"projekt":"beispiel-anleitung","auftrag":"pflege beispiel-anleitung","modus":"vorschlagen"}
```

oder direkt:

```powershell
.\dev\starte.ps1 -Projekt beispiel-anleitung -Auftrag "pflege" -Modus vorschlagen
python dev\warteschlange.py einreihen --projekt beispiel-anleitung --auftrag "pflege" --modus vorschlagen
python dev\warteschlange.py tick
```

## modi

- **vorschlagen**: nur lesen, report, `.dev/protokoll.md`. agent mit `--mode plan`
- **selber**: lokal auf einem arbeit-branch aendern und testen. **kein push, kein pr, kein merge**. oeffentlich wird erst nach freigabe in der zentralen (maske oder handy).

## stand

- `dev/status.json` — pro projekt zustand, pid, log, pr-link
- `dev/queue.json` — warteschlange
- `.dev/uebersicht.md` — hub-uebersicht
- maske liest `/dev/status` alle 3s

## anhalten

nur per pid:

```text
POST /dev/anhalten {"projekt":"beispiel-anleitung"}
python dev\warteschlange.py anhalten --projekt beispiel-anleitung
```

## agents.md verteilen

```powershell
.\dev\verteilen.ps1
```

vorhandene `AGENTS.md` werden nicht ueberschrieben. fehlende abschnitte landen in `.dev/agents-vorschlag.md`.

## gitleaks

```powershell
.\dev\gitleaks-pruefen.ps1
```

install nur mit `-Installieren` und nach deinem ok. siehe hinweis im skript.

## routine / kosten

- `dev/routine.ps1` + `dev/aufgabenplanung.md` (nicht selbst eintragen)
- limit: `dev/einstellungen.json` → `max_laeufe_pro_tag`, `max_gleichzeitig`, `timeout_minuten`

## grenzen

- auth: `agent login` oder env `CURSOR_API_KEY` (nie in dateien)
- kein force-push, keine secrets, keine repos loeschen
- timeout kill nur `taskkill /PID … /T`

## zentrale

projekte, die in der bruecke bleiben sollen, stehen in `projekte/register.json` (nicht in `liste.yaml`).
api unter `http://127.0.0.1:17341/zentrale/...` (nur localhost).
agenten committen nur lokal als `agent-cli` / `agent-fenster`. push nur nach freigabe.
