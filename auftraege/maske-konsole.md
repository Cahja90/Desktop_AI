# auftrag: rechte konsole ausfuehrlich machen

kontext: hub hub, maske in maske\ (index.html, ansicht.css, ansicht.js), server bruecke\server.py auf 127.0.0.1:17341.
der chef will rechts in der konsole (#agent panel) bei jedem gewaehlten projekt/dienst genau sehen: was, wie, wieso, warum.

## was rein soll (pro projekt, oben nach unten)
1. **stand jetzt** – ein satz klartext: laeuft / fertig / wartet auf freigabe / noch nie gelaufen, plus wann zuletzt (uhrzeit, datum).
2. **zuletzt gemacht** – was der letzte agent-lauf gemacht hat, mit **warum** (begruendung aus .dev\protokoll.md bzw. letztem lauf-log). kurze liste.
3. **letzte aenderungen im code** – letzte 5 commits (`git log -5 --format=...` hash kurz, datum, betreff) plus uncommittete aenderungen (`git status --porcelain`, nur dateinamen). ahead/behind zu origin.
4. **was muss gemacht werden** – offene todos/wege aus .dev\protokoll.md, .dev\agents-vorschlag.md und funde (z.b. ci badge fehlt, falsches topic, .dev nicht in .gitignore). jeweils mit warum und ob vorschlag oder schon freigegeben.
5. **naechster schritt** – ein satz was der dev als naechstes vorschlaegt.
bei diensten (lage.json agenten): status, letzte meldung komplett (nicht abgeschnitten), seit wann, was als naechstes.

## technik
- neuer endpunkt `GET /dev/bericht?projekt=<name>` in bruecke\server.py, liefert json mit den feldern oben. nur lokal lesen, nichts schreiben, nichts pushen, kein netz (kein git fetch).
- projektname nur gegen liste.yaml/bekannte namen pruefen wie bei den anderen endpunkten, keine pfad-tricks. subprocess immer mit `**_OHNE_FENSTER`, timeout setzen. ergebnis 10s cachen.
- niemals inhalte aus .env, kontakt.txt, .desk_token, .tunnel_token, .certs, chats.json lesen oder ausgeben. secrets/mails in commit-betreffs nicht anzeigen falls drin (maskieren).
- in ansicht.js das panel um diese abschnitte erweitern (aufklappbar, ueberschriften klein, gut lesbar), nur `textContent`/escape, kein innerHTML mit rohdaten. bestehendes protokoll/log/wege bleibt erhalten, design dunkel wie jetzt.
- die liste links nicht anfassen (der fix `flex-shrink: 0` am ende von ansicht.css bleibt drin).

## test
- py_compile server.py, `node --check maske\ansicht.js`, in dev\ `python -m unittest test_warteschlange`.
- server per pid neu starten (nur die alte server-pid killen, nie alle python), dann /dev/bericht fuer beispiel-anleitung und beispiel-web pruefen, fremder origin bei post weiter 403.
- screenshot rechts mit gewaehltem beispiel-anleitung nach maske\vorschau-konsole.png und mit tab "alle" nach maske\vorschau-alle.png (checken dass sich links nichts ueberlagert).
- beispiel-web lauf nicht stoeren. **nichts pushen, nichts in github.** server am ende laufen lassen.
- kurzes protokoll nach protokolle\2026-11-14_maske-konsole.txt und am ende kurze zusammenfassung ausgeben.

## zusatz: dienste-details im extra fenster
- klick auf eine dienst-karte links oeffnet ein **eigenes detail-fenster** (overlay/modal ueber der maske, schliessen per x, esc und klick daneben; alternativ per knopf "in neuem tab" als eigene seite maske\dienst.html?id=<id>).
- inhalt: name, status, seit wann, letzte meldung komplett, verlauf der letzten meldungen falls in lage.json/eingriff.json vorhanden, was als naechstes, knoepfe anhalten/weiter wie bisher.
- id gegen bekannte dienste pruefen, nur textContent. drag & drop am griff darf das fenster nicht ausloesen.
