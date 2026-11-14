# auftrag: dev-orchestrator bauen (nur lokal, nichts pushen)

hey, du baust jetzt hier in hub das system fertig, mit dem der dev alle meine projekte autonom pflegt. lies vorher AGENTS.md, plan.md, .cursor/rules/, projekte/liste.yaml, regeln/, pipeline/, bruecke/ und maske/. das bestehende nicht kaputt machen, nur erweitern.

## ziel
ich oeffne die bruecke (bruecke\oeffnen.py), links sehe ich meine projekte. ich sag "pflege <projekt>" oder "pflege <projekt> selber" oder "pflege alles". der dev startet dann pro projekt einen cursor-cli agenten DIREKT im projektordner, als ob ich das projekt selbst oeffne. der agent sieht nur das projekt, haelt sich an dessen AGENTS.md, arbeitet mit venv, testet, raeumt auf, sichert ab, protokolliert. der dev beobachtet das und zeigt den stand in der maske. prs und aenderungen pruefe ich, der rest laeuft von allein.

## bauen (muss)
1. `dev\starte.ps1 -Projekt <name> -Auftrag <text> [-Modus vorschlagen|selber]`
   - Set-Location in den projektordner, dann `agent -p --force --trust --workspace <ordner> --output-format stream-json` (oder text wenn stream-json zickt)
   - prompt: kurzer rahmen + auftrag + "halte dich an AGENTS.md hier, schreib .dev\protokoll.md"
   - stdout/stderr nach `<projekt>\.dev\laeufe\<zeitstempel>.log`
   - pid, start, ende, exitcode in den status schreiben
   - auth ueber vorhandenes `agent login` oder env CURSOR_API_KEY, den key nie in dateien schreiben
2. `dev\vorlage\AGENTS.md` fuer die projekte + `dev\verteilen.ps1`, das sie in jedes projekt aus projekte/liste.yaml legt, wenn dort noch keine ist (vorhandene AGENTS.md nicht ueberschreiben, nur fehlende abschnitte als vorschlag in .dev\agents-vorschlag.md). inhalt der vorlage:
   - nur in diesem ordner arbeiten, nichts ausserhalb lesen/schreiben
   - python: venv in .venv anlegen/benutzen, deps nur da rein, tests nur im venv; node: npm ci lokal
   - analyse: git status, lokal vs github, letzte commits/prs, readme, lizenz, .gitignore, tests/ci, deps, dependabot, issues, topics, releases
   - pflege-standard aus regeln/ und plan.md (readme aufbau, saas: code privat, lizenz, topics, ci+badge, releases, deps pinnen)
   - modus vorschlagen: report max 10 zeilen + 2-3 wege nummeriert mit aufwand, nichts aendern
   - modus selber: eigener branch dev/<datum>-<thema>, aendern, tests, gitleaks, commit (noreply-mail), push des branches, pr per gh, dann STOPP. nicht mergen, kein release, das mach ich nach review
   - nie .env, keys, tokens, *.pem, data\ anfassen oder ausgeben; kein force-push, keine history umschreiben, keine repos loeschen, keine visibility/einstellungen aendern, nichts bezahlen
   - protokoll .dev\protokoll.md: datum, uhrzeit, angeschaut, gefunden, gemacht, offen, links
3. `dev\warteschlange.py` (python, stdlib): auftraege aus `dev\queue.json`, max 2 agenten gleichzeitig (einstellbar), lock pro projekt (nie zwei agenten im selben repo), timeout (default 45 min) dann kill NUR per pid (taskkill /PID <pid> /T), schreibt `dev\status.json`
4. `dev\status.json` format: pro projekt name, pfad, zustand (leer/wartet/laeuft/fertig/fehler/pr-offen), modus, pid, start, ende, letzter auftrag, log-pfad, protokoll-pfad, pr-link. die maske/bruecke liest das.
5. hub-uebersicht `.dev\uebersicht.md` hier im hub, wird nach jedem lauf aktualisiert
6. gitleaks: pruefen ob installiert; wenn nicht, `dev\gitleaks-pruefen.ps1` das per winget installieren kann (nur nach meinem ok, also nur skript + hinweis, nicht selbst installieren)
7. bruecke\server.py erweitern: endpunkte zum auftrag einreihen (`POST /dev/auftrag` mit projekt, auftrag, modus), status lesen, lauf anhalten (per pid). bestehende endpunkte und ports lassen. nur 127.0.0.1.

## sollte (wenn zeit)
- `dev\routine.ps1` + anleitung wie man es in der windows-aufgabenplanung eintraegt ("pflege alles" im modus vorschlagen, woechentlich). NICHT selbst eintragen, nur skript + doku
- kostenlimit: max laeufe pro tag in dev\einstellungen.json
- windows-toast wenn pr bereit / lauf fehler

## nicht machen
- nichts pushen, nichts auf github, keine prs, kein merge. dieser bau bleibt komplett lokal
- in den projektordnern nichts ausser .dev\ anlegen und ggf. AGENTS.md wenn keine da ist. keinen agenten wirklich in einem projekt starten ausser EINEN testlauf im modus vorschlagen in beispiel-anleitung (nur lesen, report), um zu zeigen dass es geht
- profil/kontakt.txt, .env, secrets nicht lesen oder ausgeben
- prozesse nur per pid beenden, nie alle python/node abschiessen
- die maske-optik ist spaeter dran, nur die daten anbinden (status.json) damit die liste links echten stand zeigt

## am ende
- tests fuer warteschlange.py (pytest oder unittest), laufen lassen
- `dev\LIESMICH.md` kurz auf deutsch: wie starten, wie auftrag geben, modi, grenzen
- protokoll unter protokolle\2026-11-14_dev-orchestrator.txt
- lokal committen ist hier nicht moeglich (hub ist kein git-repo), also einfach dateien liegen lassen
- zum schluss auf stdout: was gebaut, was getestet, was offen, ergebnis vom testlauf
