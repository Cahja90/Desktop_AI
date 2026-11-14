#skript bleibt gesperrt
if __name__ == "__main__":
    print("gesperrt, schiffen ist nicht gestartet")
    raise SystemExit(2)


def darf_schiffen(auswahl_wert) -> bool:
    #nur hoch oder ohne code
    return auswahl_wert == "hoch" or auswahl_wert == "ohne_code"


def aktion(auswahl_wert) -> str:
    #naechster schritt zur auswahl
    if auswahl_wert == "hoch":
        return "live"
    if auswahl_wert == "ohne_code":
        return "ohne code"
    return "liegen lassen"
