# aufgabenplanung (windows)

dieses skript traegt die routine **nicht** selbst ein. du machst das einmalig in der aufgabenplanung.

## was laeuft

`dev\routine.ps1` reiht `pflege alles` im modus `vorschlagen` ein und startet einen tick der warteschlange.

## eintrag anlegen

1. aufgabenplanung oeffnen (`taskschd.msc`)
2. aktion: basisfunktion erstellen
3. trigger: woechentlich, z.b. montag 09:00
4. aktion: programm starten
   - programm: `powershell.exe`
   - argumente:

```text
-NoProfile -ExecutionPolicy Bypass -File "hub\dev\routine.ps1"
```

5. bedingungen: nur wenn netz vorhanden (optional)
6. speichern

## hinweis

- nicht unbeaufsichtigt im modus `selber` laufen lassen
- kostenlimit steht in `dev\einstellungen.json` (`max_laeufe_pro_tag`)
