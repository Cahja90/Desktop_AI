#skript bleibt gesperrt
if __name__ == "__main__":
    print("gesperrt, pruefen ist nicht gestartet")
    raise SystemExit(2)


def sammle_punkte(readme_text, beschreibung, topics, demo_ok, ist_saas, topic_vorrat) -> list[str]:
    #fehlende punkte auf deutsch
    punkte: list[str] = []
    text = readme_text or ""
    klein = text.lower()
    if beschreibung is None or str(beschreibung).strip() == "":
        punkte.append("beschreibung fehlt")
    if "problem" not in klein:
        punkte.append("problem fehlt")
    if "ablauf" not in klein and "mermaid" not in klein:
        punkte.append("ablauf fehlt")
    hat_screenshot = "screenshot" in klein
    hat_bild = any(endung in klein for endung in ("png", "jpg", "webp"))
    if not demo_ok and not hat_screenshot and not hat_bild:
        punkte.append("beispiel fehlt")
    if "privat" not in klein:
        punkte.append("satz was privat bleibt fehlt")
    if "how" not in klein and "start" not in klein:
        punkte.append("anleitung fehlt")
    vorrat = topic_vorrat or []
    gewaehlt = [thema for thema in (topics or []) if thema in vorrat]
    if not gewaehlt:
        punkte.append("topics fehlen")
    if ist_saas and "produktionscode" not in klein:
        punkte.append("saas-satz fehlt")
    return punkte


def pruefe_profil(hat_email, hat_readme, pins_ok, hat_klarname, hat_linkedin, hat_ort) -> list[str]:
    #profil pruefen
    meldungen: list[str] = []
    if not hat_email:
        meldungen.append("e-mail datei fehlt")
    if not hat_readme:
        meldungen.append("profil-readme fehlt")
    if not pins_ok:
        meldungen.append("pins weichen ab")
    if hat_klarname:
        meldungen.append("klarname steht drin")
    if hat_linkedin:
        meldungen.append("linkedin steht drin")
    if hat_ort:
        meldungen.append("ort steht drin")
    return meldungen
