# auftrag: maske nachbessern + check (nur lokal, nichts pushen)

lies vorher auftraege\maske-neu.md, dev\LIESMICH.md, AGENTS.md, .cursor\rules\, regeln\ und die coding-regeln in beispiel-anleitung\ (nur lesen). bestehende endpunkte/ports/dev\* muessen weiter gehen.

ACHTUNG: in beispiel-web laeuft evtl. gerade ein dev-lauf (siehe dev\status.json). den NICHT anhalten, nichts in beispiel-web anfassen. server (bruecke\server.py) laeuft gerade, pid ueber port 17341 finden; zum neustart nur DIESE pid beenden und mit `python bruecke\oeffnen.py` neu starten.

## 1. befehlszeile unten weg
die kommentar-/befehlszeile "kuemmere dich um …" komplett raus (html, css, js). wir steuern das spaeter aus cursor. graph soll den platz nach unten nutzen.

## 2. rechts
dev-panel rechts bleibt wie es ist, nicht umbauen.

## 3. leiste links interaktiv
- bug: klick auf tab "dienste" zeigt projekte und dienste durcheinander. fixen: tab "projekte" zeigt nur projekte, tab "dienste" nur dienste. zusaetzlich ein dritter tab "alle", der beide gruppen untereinander zeigt (mit kleiner ueberschrift je gruppe)
- drag & drop mit der maus: jede karte (projekt und dienst) per ziehen verschieben und neu anordnen. auch zwischen den gruppen rueberziehen koennen (z.b. dienst in die projektgruppe), wohin ich es brauche. ziehgriff links an der karte (6 punkte), beim ziehen platzhalter-linie, weiche animation. buttons in der karte duerfen nicht das ziehen ausloesen
- reihenfolge + gruppenzuordnung speichern: im server POST /maske/anordnung und GET /maske/anordnung, datei maske\anordnung.json (nur namen/ids, keine pfade oder geheimnisse). beim laden anwenden, neue eintraege hinten anhaengen
- native html5 drag&drop oder pointer events, keine externe lib, alles lokal
- suche filtert weiterhin

## 4. security + coding check (alles im hub-code: bruecke\, maske\, dev\)
- server nur auf 127.0.0.1, eingaben pruefen (projektname nur aus liste.yaml, keine pfad-tricks, .. verbieten), dateien nur aus erlaubten ordnern ausliefern, json-groesse begrenzen, keine shell=True, keine secrets in logs/status/anordnung
- POST-endpunkte gegen fremde seiten absichern (origin/host-check auf 127.0.0.1:17341, sonst 403) damit keine webseite im browser auftraege einreihen kann
- xss: in der maske keine unescapten strings per innerHTML (protokoll/log texte escapen)
- subprocess ueberall ohne konsolenfenster (_OHNE_FENSTER ist schon drin, nicht kaputt machen)
- coding-regeln aus beispiel-anleitung/AGENTS.md anwenden wo sinnvoll (kleine funktionen, klare namen, kommentare kurz)
- .bak dateien (bruecke\server.py.bak, dev\warteschlange.py.bak) nach erfolgreichem test loeschen
- kurz liste: was gefunden, was gefixt

## 5. testen live
- tests in dev\ gruen, node --check auf js
- server neu starten (nur eigene pid), alle endpunkte testen inkl. /maske/anordnung und 403 bei fremdem origin
- pruefen dass beim pollen keine fenster aufgehen (conhost-anzahl vorher/nachher gleich)
- screenshot nach maske\vorschau.png (edge headless), einmal tab projekte, einmal tab alle (vorschau-alle.png)
- server am ende LAUFEN LASSEN (der chef nutzt ihn), nur neu gestartet
- protokoll protokolle\2026-11-14_maske-leiste.txt, dev\LIESMICH.md kurz ergaenzen

## nicht machen
nichts pushen, keine prs, nichts oeffentlich. keine agenten in projekten starten. keine secrets/.env/profil\kontakt.txt lesen. prozesse nur per pid.

am ende stdout: was geaendert, security-befunde + fixes, testergebnis, offen.
