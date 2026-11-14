#warteschlange fuer cursor-cli agenten, max gleichzeitig, lock pro projekt
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bruecke"))
import datei_lokal

#keine konsolenfenster aufpoppen lassen (windows)
_OHNE_FENSTER = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}

HUB_DEFAULT = Path(__file__).resolve().parent.parent
DEV_DIR = Path(__file__).resolve().parent
QUEUE_NAME = "queue.json"
STATUS_NAME = "status.json"
EINSTELLUNGEN_NAME = "einstellungen.json"
STARTE_NAME = "starte.ps1"
TOAST_NAME = "toast.ps1"
UEBERSICHT_REL = Path(".dev") / "uebersicht.md"
ZUSTAENDE = ("leer", "wartet", "laeuft", "fertig", "fehler", "pr-offen", "fehlt")


def jetzt() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def heute() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def hub_pfade(hub: Path) -> dict:
    #alle pfade am hub
    hub = hub.resolve()
    dev = hub / "dev"
    return {
        "hub": hub,
        "dev": dev,
        "queue": datei_lokal.aktiv(dev / QUEUE_NAME),
        "status": datei_lokal.aktiv(dev / STATUS_NAME),
        "einstellungen": dev / EINSTELLUNGEN_NAME,
        "starte": dev / STARTE_NAME,
        "toast": dev / TOAST_NAME,
        "liste": datei_lokal.aktiv(hub / "projekte" / "liste.yaml"),
        "uebersicht": hub / UEBERSICHT_REL,
    }


def lies_json(pfad: Path, fallback):
    if not pfad.exists():
        return json.loads(json.dumps(fallback))
    roh = pfad.read_text(encoding="utf-8").strip()
    if not roh:
        return json.loads(json.dumps(fallback))
    return json.loads(roh)


def schreib_json(pfad: Path, daten) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lies_einstellungen(pfad: Path) -> dict:
    basis = {
        "max_gleichzeitig": 2,
        "timeout_minuten": 45,
        "max_laeufe_pro_tag": 20,
        "toast_an": True,
    }
    geladen = lies_json(pfad, basis)
    basis.update(geladen or {})
    return basis


def parse_liste_namen(liste_pfad: Path) -> list[str]:
    #minimale yaml-lesung fuer - name:
    if not liste_pfad.exists():
        return []
    namen = []
    for zeile in liste_pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile.startswith("- name:"):
            name = zeile.split(":", 1)[1].strip().strip('"').strip("'")
            if name:
                namen.append(name)
    return namen


def leerer_eintrag(name: str, pfad: str) -> dict:
    return {
        "name": name,
        "pfad": pfad,
        "zustand": "leer",
        "modus": "",
        "pid": None,
        "start": "",
        "ende": "",
        "letzter_auftrag": "",
        "log_pfad": "",
        "protokoll_pfad": "",
        "pr_link": "",
        "exitcode": None,
        "queue_id": "",
    }


def sichere_status(status: dict, tag: str | None = None) -> dict:
    if tag is None:
        tag = heute()
    if status.get("tag") != tag:
        status["tag"] = tag
        status["laeufe_heute"] = 0
    if "projekte" not in status or not isinstance(status["projekte"], dict):
        status["projekte"] = {}
    return status


def projekt_eintrag(status: dict, name: str, pfad: str) -> dict:
    projekte = status.setdefault("projekte", {})
    if name not in projekte:
        projekte[name] = leerer_eintrag(name, pfad)
    else:
        projekte[name]["name"] = name
        projekte[name]["pfad"] = pfad
    return projekte[name]


def sync_liste_status(pfade: dict, status: dict) -> dict:
    #alle namen aus liste.yaml in status halten; fehlt wenn ordner weg
    status = sichere_status(status)
    hub = pfade["hub"]
    for name in parse_liste_namen(pfade["liste"]):
        ordner = hub / name
        eintrag = projekt_eintrag(status, name, str(ordner))
        if not eintrag.get("protokoll_pfad"):
            eintrag["protokoll_pfad"] = str(ordner / ".dev" / "protokoll.md")
        if not ordner.is_dir():
            if eintrag.get("zustand") in ("", "leer", "fehlt", None):
                eintrag["zustand"] = "fehlt"
        elif eintrag.get("zustand") == "fehlt":
            eintrag["zustand"] = "leer"
    return status


def zaehle_laufend(status: dict) -> int:
    n = 0
    for eintrag in status.get("projekte", {}).values():
        if eintrag.get("zustand") == "laeuft":
            n += 1
    return n


def projekt_gesperrt(status: dict, name: str) -> bool:
    eintrag = status.get("projekte", {}).get(name) or {}
    return eintrag.get("zustand") in ("laeuft", "wartet") and bool(eintrag.get("pid") or eintrag.get("zustand") == "laeuft")


def pid_lebt(pid) -> bool:
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if sys.platform == "win32":
        fertig = subprocess.run(**_OHNE_FENSTER, args=
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (fertig.stdout or "") + (fertig.stderr or "")
        return str(pid) in out and "No tasks" not in out and "Keine Aufgaben" not in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_pid(pid) -> bool:
    #nur diese pid und kinder, nie pauschal python/node
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if sys.platform == "win32":
        fertig = subprocess.run(**_OHNE_FENSTER, args=
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return fertig.returncode == 0
    try:
        os.kill(pid, 9)
        return True
    except OSError:
        return False


def parse_zeit(wert: str):
    if not wert:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(wert, fmt)
        except ValueError:
            continue
    return None


def timeout_faellig(eintrag: dict, timeout_minuten: int, jetzt_dt: datetime | None = None) -> bool:
    if eintrag.get("zustand") != "laeuft":
        return False
    start = parse_zeit(eintrag.get("start") or "")
    if not start:
        return False
    if jetzt_dt is None:
        jetzt_dt = datetime.now()
    return (jetzt_dt - start).total_seconds() >= timeout_minuten * 60


def aktualisiere_uebersicht(pfade: dict, status: dict) -> None:
    zeilen = ["# uebersicht", "", f"stand: {jetzt()}", ""]
    for name, eintrag in sorted(status.get("projekte", {}).items()):
        zeilen.append(
            f"- {name}: {eintrag.get('zustand')} · {eintrag.get('modus')} · {eintrag.get('letzter_auftrag')}"
        )
        if eintrag.get("pr_link"):
            zeilen.append(f"  pr: {eintrag['pr_link']}")
        if eintrag.get("log_pfad"):
            zeilen.append(f"  log: {eintrag['log_pfad']}")
    pfade["uebersicht"].parent.mkdir(parents=True, exist_ok=True)
    pfade["uebersicht"].write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def toast(pfade: dict, titel: str, text: str, an: bool) -> None:
    if not an:
        return
    skript = pfade["toast"]
    if not skript.exists():
        return
    subprocess.run(**_OHNE_FENSTER, args=
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(skript),
            "-Titel",
            titel,
            "-Text",
            text,
        ],
        check=False,
        capture_output=True,
    )


def neuer_auftrag(projekt: str, auftrag: str, modus: str) -> dict:
    if modus not in ("vorschlagen", "selber"):
        raise ValueError("modus muss vorschlagen oder selber sein")
    return {
        "id": uuid.uuid4().hex[:12],
        "projekt": projekt,
        "auftrag": auftrag,
        "modus": modus,
        "eingereiht": jetzt(),
        "stand": "wartet",
    }


def einreihen(pfade: dict, projekt: str, auftrag: str, modus: str) -> list[dict]:
    queue = lies_json(pfade["queue"], {"auftraege": []})
    status = sichere_status(lies_json(pfade["status"], {"tag": "", "laeufe_heute": 0, "projekte": {}}))
    namen = parse_liste_namen(pfade["liste"])
    if projekt == "alles":
        ziele = namen
    else:
        if projekt not in namen and not (pfade["hub"] / projekt).is_dir():
            raise ValueError(f"unbekanntes projekt: {projekt}")
        ziele = [projekt]
    neu = []
    for name in ziele:
        job = neuer_auftrag(name, auftrag, modus)
        queue.setdefault("auftraege", []).append(job)
        pfad = str(pfade["hub"] / name)
        eintrag = projekt_eintrag(status, name, pfad)
        if eintrag.get("zustand") != "laeuft":
            eintrag["zustand"] = "wartet"
            eintrag["modus"] = modus
            eintrag["letzter_auftrag"] = auftrag
            eintrag["queue_id"] = job["id"]
        neu.append(job)
    schreib_json(pfade["queue"], queue)
    schreib_json(pfade["status"], status)
    aktualisiere_uebersicht(pfade, status)
    return neu


def naechste_jobs(queue: dict, status: dict, max_gleichzeitig: int) -> list[dict]:
    frei = max_gleichzeitig - zaehle_laufend(status)
    if frei <= 0:
        return []
    gewaehlt = []
    belegt = {
        name
        for name, eintrag in status.get("projekte", {}).items()
        if eintrag.get("zustand") == "laeuft"
    }
    for job in queue.get("auftraege", []):
        if job.get("stand") != "wartet":
            continue
        name = job.get("projekt")
        if name in belegt:
            continue
        gewaehlt.append(job)
        belegt.add(name)
        if len(gewaehlt) >= frei:
            break
    return gewaehlt


def markiere_job(queue: dict, job_id: str, stand: str) -> None:
    for job in queue.get("auftraege", []):
        if job.get("id") == job_id:
            job["stand"] = stand
            return


def starte_job(pfade: dict, job: dict, status: dict, einstellungen: dict) -> dict:
    name = job["projekt"]
    projekt_pfad = pfade["hub"] / name
    if not projekt_pfad.is_dir():
        eintrag = projekt_eintrag(status, name, str(projekt_pfad))
        eintrag["zustand"] = "fehler"
        eintrag["ende"] = jetzt()
        eintrag["letzter_auftrag"] = job.get("auftrag", "")
        return {"ok": False, "fehler": "ordner fehlt", "projekt": name}

    if status.get("laeufe_heute", 0) >= int(einstellungen.get("max_laeufe_pro_tag", 20)):
        return {"ok": False, "fehler": "tageslimit", "projekt": name}

    eintrag = projekt_eintrag(status, name, str(projekt_pfad))
    if eintrag.get("zustand") == "laeuft" and pid_lebt(eintrag.get("pid")):
        return {"ok": False, "fehler": "lock", "projekt": name}

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(pfade["starte"]),
        "-Projekt",
        name,
        "-Auftrag",
        job.get("auftrag", ""),
        "-Modus",
        job.get("modus", "vorschlagen"),
        "-Hub",
        str(pfade["hub"]),
    ]
    #unter windows eigener prozess, pid merken
    kwargs = {
        "cwd": str(pfade["hub"]),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(cmd, **kwargs)
    eintrag["zustand"] = "laeuft"
    eintrag["modus"] = job.get("modus", "vorschlagen")
    eintrag["pid"] = proc.pid
    eintrag["start"] = jetzt()
    eintrag["ende"] = ""
    eintrag["letzter_auftrag"] = job.get("auftrag", "")
    eintrag["protokoll_pfad"] = str(projekt_pfad / ".dev" / "protokoll.md")
    eintrag["queue_id"] = job.get("id", "")
    eintrag["exitcode"] = None
    status["laeufe_heute"] = int(status.get("laeufe_heute", 0)) + 1
    return {"ok": True, "projekt": name, "pid": proc.pid, "id": job.get("id")}


def pruefe_timeouts(pfade: dict, status: dict, timeout_minuten: int, toast_an: bool) -> list[str]:
    getroffen = []
    for name, eintrag in list(status.get("projekte", {}).items()):
        if not timeout_faellig(eintrag, timeout_minuten):
            continue
        pid = eintrag.get("pid")
        if pid_lebt(pid):
            kill_pid(pid)
        eintrag["zustand"] = "fehler"
        eintrag["ende"] = jetzt()
        eintrag["pid"] = None
        getroffen.append(name)
        toast(pfade, "dev lauf timeout", f"{name} nach {timeout_minuten} min beendet", toast_an)
    return getroffen


def sync_laufende(status: dict) -> None:
    #wenn starte.ps1 fertig ist, pid tot -> zustand aus datei belassen oder fertig setzen
    for eintrag in status.get("projekte", {}).values():
        if eintrag.get("zustand") != "laeuft":
            continue
        pid = eintrag.get("pid")
        if pid and not pid_lebt(pid):
            #starte.ps1 schreibt finalen zustand; kurz warten und neu lesen aussen
            if not eintrag.get("ende"):
                eintrag["ende"] = jetzt()
                if eintrag.get("zustand") == "laeuft":
                    eintrag["zustand"] = "fertig"
            eintrag["pid"] = None


def tick(pfade: dict) -> dict:
    einstellungen = lies_einstellungen(pfade["einstellungen"])
    queue = lies_json(pfade["queue"], {"auftraege": []})
    status = sync_liste_status(
        pfade,
        sichere_status(lies_json(pfade["status"], {"tag": "", "laeufe_heute": 0, "projekte": {}})),
    )

    timeouts = pruefe_timeouts(
        pfade,
        status,
        int(einstellungen.get("timeout_minuten", 45)),
        bool(einstellungen.get("toast_an", True)),
    )
    #status nach starte.ps1 neu laden falls parallel geschrieben
    status = sichere_status(lies_json(pfade["status"], status))
    sync_laufende(status)

    gestartet = []
    fehler = []
    for job in naechste_jobs(queue, status, int(einstellungen.get("max_gleichzeitig", 2))):
        ergebnis = starte_job(pfade, job, status, einstellungen)
        if ergebnis.get("ok"):
            markiere_job(queue, job["id"], "gestartet")
            gestartet.append(ergebnis)
        else:
            if ergebnis.get("fehler") == "tageslimit":
                fehler.append(ergebnis)
                break
            markiere_job(queue, job["id"], "fehler")
            fehler.append(ergebnis)

    schreib_json(pfade["queue"], queue)
    schreib_json(pfade["status"], status)
    aktualisiere_uebersicht(pfade, status)
    return {
        "gestartet": gestartet,
        "fehler": fehler,
        "timeouts": timeouts,
        "laufend": zaehle_laufend(status),
        "wartend": sum(1 for j in queue.get("auftraege", []) if j.get("stand") == "wartet"),
    }


def anhalten(pfade: dict, projekt: str) -> dict:
    status = sichere_status(lies_json(pfade["status"], {"tag": "", "laeufe_heute": 0, "projekte": {}}))
    eintrag = status.get("projekte", {}).get(projekt)
    if not eintrag:
        return {"ok": False, "fehler": "unbekannt"}
    pid = eintrag.get("pid")
    ok = False
    if pid_lebt(pid):
        ok = kill_pid(pid)
    eintrag["zustand"] = "fehler"
    eintrag["ende"] = jetzt()
    eintrag["pid"] = None
    schreib_json(pfade["status"], status)
    aktualisiere_uebersicht(pfade, status)
    toast(pfade, "dev lauf angehalten", projekt, True)
    return {"ok": True, "projekt": projekt, "kill": ok, "pid": pid}


def status_lesen(pfade: dict) -> dict:
    status = sync_liste_status(
        pfade,
        sichere_status(lies_json(pfade["status"], {"tag": "", "laeufe_heute": 0, "projekte": {}})),
    )
    schreib_json(pfade["status"], status)
    return status


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dev warteschlange")
    parser.add_argument("--hub", default=str(HUB_DEFAULT))
    unter = parser.add_subparsers(dest="befehl", required=True)

    p_ein = unter.add_parser("einreihen")
    p_ein.add_argument("--projekt", required=True)
    p_ein.add_argument("--auftrag", required=True)
    p_ein.add_argument("--modus", default="vorschlagen", choices=["vorschlagen", "selber"])

    unter.add_parser("tick")
    unter.add_parser("status")
    unter.add_parser("loop")

    p_halt = unter.add_parser("anhalten")
    p_halt.add_argument("--projekt", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = baue_parser()
    args = parser.parse_args(argv)
    pfade = hub_pfade(Path(args.hub))
    if args.befehl == "einreihen":
        jobs = einreihen(pfade, args.projekt, args.auftrag, args.modus)
        print(json.dumps({"eingereiht": jobs}, ensure_ascii=False, indent=2))
        return 0
    if args.befehl == "tick":
        print(json.dumps(tick(pfade), ensure_ascii=False, indent=2))
        return 0
    if args.befehl == "status":
        print(json.dumps(status_lesen(pfade), ensure_ascii=False, indent=2))
        return 0
    if args.befehl == "anhalten":
        print(json.dumps(anhalten(pfade, args.projekt), ensure_ascii=False, indent=2))
        return 0
    if args.befehl == "loop":
        while True:
            print(json.dumps(tick(pfade), ensure_ascii=False))
            time.sleep(5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
