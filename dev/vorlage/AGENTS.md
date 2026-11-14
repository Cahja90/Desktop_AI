# agents

du arbeitest nur in diesem ordner. nichts ausserhalb lesen oder schreiben.

## umgebung

- python: venv in `.venv` anlegen oder benutzen. deps nur da rein. tests nur im venv.
- node: `npm ci` lokal im projekt.

## analyse

schau an: git status, lokal vs github, letzte commits und prs, readme, lizenz, `.gitignore`, tests/ci, deps, dependabot, issues, topics, releases.

## pflege-standard

halte dich an die hub-regeln unter `regeln/` und `plan.md` (wenn der chef sie mitgibt, sonst nur was hier im repo steht):

- readme-mindeststand: satz oben, problem, ablauf, live/screenshot, was privat bleibt, how-to-run, topics
- saas: code privat, lizenz, topics, ci+badge, releases, deps pinnen
- kein klarname, keine keys, keine mails, keine tokens in git

## modus vorschlagen

- nichts aendern
- report maximal 10 zeilen
- 2-3 wege nummeriert mit aufwand
- schreib `.dev/protokoll.md`

## modus selber

- branch `dev/<datum>-<thema>`
- aendern, tests, gitleaks
- commit mit noreply-mail
- kein git push, keinen pull request, kein merge. oeffentlich erst nach freigabe in der zentralen
- dann STOPP
- nicht mergen, kein release

## hart verboten

- nie `.env`, keys, tokens, `*.pem`, `data\` anfassen oder ausgeben
- kein force-push, keine history umschreiben
- keine repos loeschen, keine visibility/einstellungen aendern
- nichts bezahlen

## protokoll

schreib `.dev/protokoll.md` mit:

```
datum:
uhrzeit:
angeschaut:
gefunden:
gemacht:
offen:
links:
```
