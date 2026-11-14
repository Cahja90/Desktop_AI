# auftrag: maske neu + rest fertig (nur lokal, nichts pushen)

lies vorher auftraege\dev-orchestrator.md, dev\LIESMICH.md, bruecke\, maske\. alles bestehende (endpunkte, ports, dev\*) muss weiter gehen.

## 1. rest fertig
- projekte\liste.yaml: beispiel-bridge und beispiel-web eintragen (gleiches format wie die anderen, ordner liegen schon in hub). dev\status.json soll alle zeigen
- beispiel-seite: ordner fehlt. wenn `gh repo view Cahja90/beispiel-seite` geht, nach hub\beispiel-seite klonen (nur clone, sonst nichts). wenn nicht: in liste lassen, zustand "fehlt" anzeigen
- gitleaks per dev\gitleaks-pruefen.ps1 / winget installieren (ok vom chef ist da), pruefen dass `gitleaks version` geht
- dev\verteilen.ps1 einmal laufen lassen (nur fehlende AGENTS.md / vorschlaege, nichts ueberschreiben)
- aufgabenplanung NICHT eintragen

## 2. maske neu (sieht zu alt aus)
stil: dunkel modern wie linear/raycast. hintergrund #0b0d12, feines raster, weicher glow, schrift inter (lokal in maske\schrift wenn da, sonst system-ui), viel luft, runde ecken 12-16px, 1px raender rgba(255,255,255,.08), leichtes glas (backdrop-filter). akzente teal #2dd4bf, violett #8b5cf6, blau #3b82f6. keine externen cdns, alles lokal.

aufbau:
- links (ca 300px): interaktive projektliste aus /dev/status, immer sichtbar. pro projekt: status-punkt (gruen fertig, blau laeuft (pulsiert), gelb wartet/pr-offen, rot fehler, grau leer/fehlt), name, ein satz stand, zeit letzter lauf. klick = auswaehlen + im graph hervorheben. hover zeigt pfad. kleine pill-buttons: "pflegen" (vorschlagen), "selber", "anhalten". oben titel "bruecke", zaehler-chips "x laufen · y fertig", suchfeld
- mitte: graph der projekte als leuchtende kugeln (radiale verlaeufe teal/violett/blau), duenne gebogene linien zum zentrum "profil", labels als kleine pills. ausgewaehltes projekt groesser mit ring. canvas oder svg, fluessig, keine lib noetig
- rechts (ca 340px): dev-panel zum ausgewaehlten projekt: zustand, modus, letzter auftrag, dann protokoll (.dev\protokoll.md, neueste eintraege oben, markdown simpel rendern), wege/vorschlaege mit nummern, button "freigeben" der den gewaehlten weg als auftrag im modus selber einreiht, live-log-ende vom laufenden lauf. dafuer im server einen endpunkt GET /dev/protokoll?projekt=x und GET /dev/log?projekt=x (nur dateien aus dem projekt\.dev\, pfad pruefen, nichts anderes ausliefern)
- unten: befehlszeile "kuemmere dich um …" -> versteht "pflege <projekt>", "pflege <projekt> selber", "pflege alles", "stopp <projekt>" und ruft POST /dev/auftrag bzw /dev/anhalten
- polling alle 3 s auf /dev/status
- die alten bereiche (laufende dienste wie beispiel seite, handy bruecke, cockpit mit anhalten/weiter aus lage.json) nicht wegwerfen: als zweiter tab "dienste" in der linken leiste

## 3. pruefen
- server starten, alle endpunkte mit curl/Invoke-WebRequest testen, maske laden, keine js-fehler (wenn moeglich headless pruefen, sonst html/js lint)
- screenshot der maske nach hub\maske\vorschau.png (z.b. mit edge headless --screenshot) wenn moeglich
- tests in dev\ weiter gruen
- dev\LIESMICH.md: kurzer abschnitt "so startest du" (bruecke\oeffnen.py doppelklick / befehl) ergaenzen
- protokoll protokolle\2026-11-14_maske-neu.txt
- server am ende wieder per pid beenden, wenn du ihn gestartet hast (nicht fremde prozesse)

## nicht machen
nichts pushen, keine prs, keine agenten in projekten starten (ausser es ist fuer den test noetig, dann nur modus vorschlagen in beispiel-anleitung). keine secrets/.env/profil\kontakt.txt lesen. prozesse nur per pid.

am ende auf stdout: was gebaut, was getestet, wie starten, was offen.
