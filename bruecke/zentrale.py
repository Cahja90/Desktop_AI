#zentrale: register, stand, agenten, git-freigabe, protokoll
#kein push ohne ja, lane einhalten, secrets nicht lesen
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import datei_lokal

WURZEL = Path(__file__).resolve().parent.parent
REGISTER = WURZEL / "projekte" / "register.json"
PROTO_DIR = WURZEL / "protokolle" / "zentrale"
LAEUFE = PROTO_DIR / "laeufe.json"
FREIGABEN = PROTO_DIR / "freigaben.json"
JSONL = PROTO_DIR / "zentrale.jsonl"
PROTO_MD = PROTO_DIR / "zentrale.md"
ANORDNUNG = WURZEL / "maske" / "anordnung.json"

VERBOTENE_TEILE = (
    "desk_token",
    "tunnel_token",
    ".certs",
    "chats.json",
)
_EXTRA = WURZEL / "regeln" / "verboten.lokal.txt"
if _EXTRA.exists():
    VERBOTENE_TEILE = VERBOTENE_TEILE + tuple(
        z.strip().lower() for z in _EXTRA.read_text(encoding="utf-8-sig").splitlines() if z.strip()
    )
VERBOTENE_NAMEN = {".env", "kontakt.txt", ".desk_token", ".tunnel_token", "chats.json"}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
AUFTRAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")

_OHNE_FENSTER = {}
if sys.platform == "win32":
    _OHNE_FENSTER = {"creationflags": subprocess.CREATE_NO_WINDOW}

_lock = threading.Lock()
_GIT_TIMEOUT = 12


def jetzt():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def sichere_id(wert):
    name = str(wert or "").strip()
    if not ID_RE.match(name):
        return ""
    if ".." in name or "/" in name or "\\" in name:
        return ""
    return name


def sichere_auftrag(wert):
    name = str(wert or "").strip()
    if not AUFTRAG_RE.match(name):
        return ""
    return name


def _schreib_json(pfad, daten):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(pfad.suffix + ".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, pfad)


def _lies_json(pfad, fallback):
    if not pfad.exists():
        return fallback
    try:
        return json.loads(pfad.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return fallback


def leeres_register():
    return {"projekte": []}


def register_pfad():
    return datei_lokal.aktiv(REGISTER)


def anordnung_pfad():
    return datei_lokal.aktiv(ANORDNUNG)


def grenzen_pfad():
    return datei_lokal.aktiv(WURZEL / "regeln" / "grenzen.yaml")


def verbotene_ordner():
    #namen aus regeln/grenzen.yaml, lokale datei hat vorrang
    pfad = grenzen_pfad()
    namen = []
    if not pfad.is_file():
        return namen
    for zeile in pfad.read_text(encoding="utf-8-sig").splitlines():
        zeile = zeile.strip()
        if zeile.startswith("- "):
            namen.append(zeile[2:].strip().lower())
    return namen


def standard_ausschluss():
    for ein in lese_register().get("projekte") or []:
        if str(ein.get("art") or "") == "hub":
            return list(ein.get("lane_ausschluss") or [])
    return []


def lese_register():
    roh = _lies_json(register_pfad(), leeres_register())
    if not isinstance(roh, dict):
        return leeres_register()
    liste = roh.get("projekte") or []
    if not isinstance(liste, list):
        return leeres_register()
    sauber = []
    gesehen = set()
    for ein in liste:
        if not isinstance(ein, dict):
            continue
        pid = sichere_id(ein.get("id"))
        if not pid or pid in gesehen:
            continue
        pfad = str(ein.get("pfad") or "").strip()
        if not pfad:
            continue
        gesehen.add(pid)
        ausschluss = ein.get("lane_ausschluss") or []
        if not isinstance(ausschluss, list):
            ausschluss = []
        sauber.append(
            {
                "id": pid,
                "name": str(ein.get("name") or pid)[:80],
                "pfad": pfad,
                "aktiv": bool(ein.get("aktiv", True)),
                "art": str(ein.get("art") or "extern")[:40],
                "eingefuegt": str(ein.get("eingefuegt") or ""),
                "lane_ausschluss": [str(x)[:80] for x in ausschluss if str(x).strip()],
            }
        )
    return {"projekte": sauber}


def schreibe_register(daten):
    _schreib_json(register_pfad(), daten)
    return lese_register()


def projekt_von(pid):
    pid = sichere_id(pid)
    if not pid:
        return None
    for ein in lese_register().get("projekte") or []:
        if ein["id"] == pid:
            return ein
    return None


def pfad_verboten(pfad):
    try:
        voll = Path(pfad).resolve()
    except (OSError, RuntimeError):
        return True
    text = str(voll).lower()
    if any(teil in text for teil in VERBOTENE_TEILE):
        return True
    if voll.name.lower() in VERBOTENE_NAMEN:
        return True
    teile = [p.lower() for p in voll.parts]
    for name in verbotene_ordner():
        if name and name in teile:
            return True
    return False


def lane_pfad(ein):
    try:
        voll = Path(ein["pfad"]).resolve()
    except (OSError, RuntimeError):
        return None
    if not voll.is_dir():
        return None
    if pfad_verboten(voll):
        return None
    return voll


def in_lane(datei, lane, ausschluss):
    try:
        datei = Path(datei).resolve()
        lane = Path(lane).resolve()
    except (OSError, RuntimeError):
        return False
    if datei != lane and lane not in datei.parents:
        return False
    try:
        rel = datei.relative_to(lane)
    except ValueError:
        return False
    teile = rel.parts
    if teile and teile[0] in set(ausschluss or []):
        return False
    if datei.name.lower() in VERBOTENE_NAMEN:
        return False
    return True


def git_lauf(ordner, args, env=None, timeout=_GIT_TIMEOUT):
    if not ordner or not Path(ordner).is_dir():
        return "", 1
    umgebung = os.environ.copy()
    if env:
        umgebung.update(env)
    try:
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=["git", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ordner),
            timeout=timeout,
            env=umgebung,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", 1
    return (fertig.stdout or "") + (fertig.stderr or ""), fertig.returncode


def git_ok(ordner, args, env=None):
    out, code = git_lauf(ordner, args, env=env)
    return out if code == 0 else ""


def hat_remote(ordner):
    out = git_ok(ordner, ["remote"])
    return bool(out.strip())


def aktueller_branch(ordner):
    out = git_ok(ordner, ["branch", "--show-current"])
    return (out or "").strip()


def git_stand(ordner, ausschluss=None):
    if not ordner or not Path(ordner).is_dir() or not (Path(ordner) / ".git").exists():
        return {
            "branch": "",
            "remote": False,
            "upstream": "",
            "ahead": 0,
            "behind": 0,
            "commits": [],
            "uncommittet": [],
        }
    commits = []
    roh = git_ok(ordner, ["log", "-8", "--format=%h|%ad|%an|%s", "--date=format:%Y-%m-%d %H:%M"])
    for zeile in roh.splitlines():
        teile = zeile.split("|", 3)
        if len(teile) < 4:
            continue
        betreff = teile[3].strip()
        autor = teile[2].strip()
        agent = ""
        if autor.startswith("agent-"):
            agent = autor
        commits.append(
            {
                "hash": teile[0].strip(),
                "datum": teile[1].strip(),
                "autor": autor,
                "betreff": betreff,
                "agent": agent,
            }
        )
    uncommittet = []
    for zeile in git_ok(ordner, ["status", "--porcelain", "-uall"]).splitlines():
        if len(zeile) < 4:
            continue
        name = zeile[3:].strip()
        if " -> " in name:
            name = name.split(" -> ", 1)[1].strip()
        name = name.strip().strip('"')
        if not name:
            continue
        if Path(name).name.lower() in VERBOTENE_NAMEN:
            continue
        if (ausschluss or []) and name.split("/")[0].split("\\")[0] in set(ausschluss):
            continue
        uncommittet.append(name)
    ahead = 0
    behind = 0
    upstream = ""
    branch = aktueller_branch(ordner)
    kurz = git_ok(ordner, ["status", "-sb"]).splitlines()
    if kurz:
        kopf = kurz[0].strip()
        if kopf.startswith("## "):
            rest = kopf[3:]
            if "..." in rest:
                links, rechts = rest.split("...", 1)
                branch = branch or links.strip()
                upstream = rechts.split(" ", 1)[0].strip()
            elif not branch:
                branch = rest.split(" ", 1)[0].strip()
            m = re.search(r"\[ahead (\d+)(?:, behind (\d+))?\]", rest)
            if m:
                ahead = int(m.group(1) or 0)
                behind = int(m.group(2) or 0)
            else:
                m2 = re.search(r"\[behind (\d+)\]", rest)
                if m2:
                    behind = int(m2.group(1) or 0)
    return {
        "branch": branch,
        "remote": hat_remote(ordner),
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "commits": commits,
        "uncommittet": uncommittet[:40],
    }


def proto_event(art, projekt, kurz, **extra):
    ein = {
        "zeit": jetzt(),
        "projekt": projekt or "",
        "art": art,
        "kurz": str(kurz or "")[:400],
    }
    ein.update(extra)
    PROTO_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        with JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ein, ensure_ascii=False) + "\n")
        zeile = "- %s · %s · %s · %s\n" % (ein["zeit"], ein["projekt"], art, ein["kurz"])
        if not PROTO_MD.exists():
            PROTO_MD.write_text("# zentrales protokoll\n\n" + zeile, encoding="utf-8")
        else:
            with PROTO_MD.open("a", encoding="utf-8") as f:
                f.write(zeile)
    return ein


def lese_protokoll(limit=80):
    if not JSONL.exists():
        return {"ereignisse": []}
    zeilen = JSONL.read_text(encoding="utf-8-sig").splitlines()
    ereignisse = []
    for zeile in zeilen[-limit:]:
        try:
            ereignisse.append(json.loads(zeile))
        except json.JSONDecodeError:
            continue
    ereignisse.reverse()
    return {"ereignisse": ereignisse, "datei": str(JSONL)}


def lese_laeufe():
    roh = _lies_json(LAEUFE, {"laeufe": []})
    if not isinstance(roh, dict):
        return {"laeufe": []}
    liste = roh.get("laeufe") or []
    if not isinstance(liste, list):
        return {"laeufe": []}
    return {"laeufe": liste}


def schreibe_laeufe(daten):
    _schreib_json(LAEUFE, daten)
    return lese_laeufe()


def lese_freigaben():
    roh = _lies_json(FREIGABEN, {"anfragen": []})
    if not isinstance(roh, dict):
        return {"anfragen": []}
    liste = roh.get("anfragen") or []
    if not isinstance(liste, list):
        return {"anfragen": []}
    return {"anfragen": liste}


def schreibe_freigaben(daten):
    _schreib_json(FREIGABEN, daten)
    return lese_freigaben()


def pid_lebt(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            fertig = subprocess.run(
                **_OHNE_FENSTER,
                args=["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                timeout=8,
            )
            text = (fertig.stdout or "").strip()
            if not text or "no tasks" in text.lower() or "keine aufgabe" in text.lower() or "information:" in text.lower():
                return False
            return (",%d," % pid) in text.replace('"', ",") or text.endswith(",%d" % pid)
        fertig = subprocess.run(
            args=["ps", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
        return fertig.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def kill_pid(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if not pid_lebt(pid):
        return True
    try:
        if sys.platform == "win32":
            subprocess.run(
                **_OHNE_FENSTER,
                args=["taskkill", "/PID", str(pid), "/T"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return not pid_lebt(pid)


def arbeit_branch(auftrag_id):
    return "arbeit/%s" % auftrag_id


def git_branch_namen(ordner):
    out = git_ok(ordner, ["branch", "--format=%(refname:short)"])
    return [z.strip() for z in (out or "").splitlines() if z.strip()]


def git_basis_name(ordner, bevorzugt=None):
    branches = set(git_branch_namen(ordner))
    if bevorzugt and bevorzugt in branches and not str(bevorzugt).startswith("arbeit/"):
        return bevorzugt
    for name in ("main", "master"):
        if name in branches:
            return name
    aktuell = aktueller_branch(ordner)
    if aktuell and not aktuell.startswith("arbeit/"):
        return aktuell
    return aktuell


def branch_anlegen(ordner, name, basis=None):
    #neuen arbeit-branch von main/basis, nicht von einem anderen arbeit/* erben
    aktuell = aktueller_branch(ordner)
    if aktuell == name:
        return True, "schon auf %s" % name
    existiert = git_lauf(ordner, ["rev-parse", "--verify", name])[1] == 0
    if existiert:
        out, code = git_lauf(ordner, ["checkout", name])
        if code != 0:
            return False, (out or "checkout fehlgeschlagen").strip()[:300]
        return True, "branch %s" % name
    basis = git_basis_name(ordner, basis)
    if not basis:
        return False, "keine basis-branch gefunden (main/master)"
    if aktuell != basis:
        out, code = git_lauf(ordner, ["checkout", basis])
        if code != 0:
            return False, ("checkout basis %s: " % basis + (out or ""))[:300]
    out, code = git_lauf(ordner, ["checkout", "-b", name])
    if code != 0:
        return False, (out or "checkout -b fehlgeschlagen").strip()[:300]
    return True, "angelegt von %s" % basis


def finde_agent_exe():
    lokal = Path(os.environ.get("LOCALAPPDATA") or "") / "cursor-agent" / "agent.cmd"
    if lokal.is_file():
        return str(lokal)
    for name in ("agent.cmd", "agent"):
        gefunden = _which(name)
        if gefunden:
            return gefunden
    return ""


def _which(name):
    try:
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=["where", name] if sys.platform == "win32" else ["which", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    zeile = (fertig.stdout or "").splitlines()
    return zeile[0].strip() if zeile and fertig.returncode == 0 else ""


def finde_tipper():
    kandidat = Path("D:/grok-cursor-bruecke/tipper.py")
    if kandidat.is_file():
        return kandidat
    return None


def finde_loop():
    tip = finde_tipper()
    if tip:
        kand = tip.parent / "loop.py"
        if kand.is_file():
            return kand
    return None


def py_fuer(datei):
    venv = datei.parent / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return str(venv)
    return sys.executable


def laufender_in(projekt_id):
    sync_laeufe()
    treffer = []
    for lauf in lese_laeufe().get("laeufe") or []:
        if lauf.get("projekt") == projekt_id and lauf.get("stand") == "laeuft":
            treffer.append(lauf)
    return treffer


def sync_laeufe():
    wartend = []
    with _lock:
        daten = lese_laeufe()
        geaendert = False
        for lauf in daten.get("laeufe") or []:
            if lauf.get("stand") != "laeuft":
                continue
            pid = lauf.get("pid")
            if pid and pid_lebt(pid):
                continue
            lauf["stand"] = "endet"
            lauf["ende"] = jetzt()
            geaendert = True
        for lauf in daten.get("laeufe") or []:
            if lauf.get("stand") == "endet" and not lauf.get("abgeschlossen") and not lauf.get("abschluss_laeuft"):
                lauf["abschluss_laeuft"] = True
                wartend.append(dict(lauf))
                geaendert = True
        if geaendert:
            schreibe_laeufe(daten)
    for lauf in wartend:
        _abschluss_lauf(lauf)


def _abschluss_lauf(lauf):
    projekt_id = lauf.get("projekt")
    auftrag_id = lauf.get("auftrag")
    ein = projekt_von(projekt_id)
    if not ein:
        _mark_lauf(lauf.get("id"), stand="fehler", kurz="projekt weg")
        return
    lane = lane_pfad(ein)
    if not lane:
        _mark_lauf(lauf.get("id"), stand="fehler", kurz="lane ungueltig")
        return
    if (lauf.get("art") or "") == "loop":
        #der loop committet selbst pro aufgabe, hier nur den lauf schliessen
        status_pfad = lane / ".loop" / "status.json"
        kurz = "loop beendet"
        try:
            if status_pfad.is_file():
                st = json.loads(status_pfad.read_text(encoding="utf-8-sig"))
                kurz = "loop %s aktuell=%s" % (st.get("phase") or "ende", st.get("aktuell") or "-")
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        _mark_lauf(lauf.get("id"), stand="fertig", kurz=kurz)
        proto_event("ende", projekt_id, kurz, agent="loop", auftrag=auftrag_id)
        return
    ok, kurz, hash_ = agent_commit(
        lane,
        ein.get("lane_ausschluss") or [],
        auftrag_id,
        "cli" if (lauf.get("art") or "cli") == "cli" else "fenster",
        projekt_id,
        lauf.get("ziel") or ("auftrag " + str(auftrag_id)),
    )
    stand = "fertig" if ok else "fehler"
    _mark_lauf(lauf.get("id"), stand=stand, kurz=kurz, commit=hash_)
    proto_event(
        "commit" if ok and hash_ else "fehler",
        projekt_id,
        kurz,
        agent=lauf.get("art") or "cli",
        auftrag=auftrag_id,
        hash=hash_ or "",
    )


def _mark_lauf(lauf_id, **felder):
    with _lock:
        daten = lese_laeufe()
        for lauf in daten.get("laeufe") or []:
            if lauf.get("id") == lauf_id:
                lauf.update(felder)
                lauf["abgeschlossen"] = True
                if "ende" not in lauf or not lauf.get("ende"):
                    lauf["ende"] = jetzt()
        schreibe_laeufe(daten)


def geaenderte_dateien(ordner, ausschluss):
    roh = git_ok(ordner, ["status", "--porcelain", "-uall"])
    dateien = []
    for zeile in roh.splitlines():
        if len(zeile) < 4:
            continue
        name = zeile[3:].strip()
        if " -> " in name:
            name = name.split(" -> ", 1)[1].strip()
        name = name.strip().strip('"')
        if not name:
            continue
        voll = Path(ordner) / name
        if not in_lane(voll, ordner, ausschluss):
            dateien.append(("draussen", name))
        elif Path(name).name.lower() in VERBOTENE_NAMEN:
            dateien.append(("geheim", name))
        else:
            dateien.append(("ok", name))
    return dateien


def agent_commit(ordner, ausschluss, auftrag_id, art, projekt_id, ziel):
    #committet nur dateien in der lane, als agent-cli / agent-fenster, kein push
    aenderungen = geaenderte_dateien(ordner, ausschluss)
    draussen = [n for k, n in aenderungen if k == "draussen"]
    if draussen:
        return False, "lane-verstoss: " + ", ".join(draussen[:8]), ""
    ok_dateien = [n for k, n in aenderungen if k == "ok"]
    #loop- und log-dateien nicht mit committen
    commit_dateien = []
    for name in ok_dateien:
        norm = name.replace("\\", "/")
        if norm.startswith(".loop/") or norm.startswith(".dev/laeufe/") or norm.endswith(".log"):
            continue
        commit_dateien.append(name)
    if not commit_dateien:
        return True, "nichts zu committen", ""
    autor = "agent-cli" if art == "cli" else "agent-fenster"
    env = {
        "GIT_AUTHOR_NAME": autor,
        "GIT_AUTHOR_EMAIL": autor + "@local",
        "GIT_COMMITTER_NAME": autor,
        "GIT_COMMITTER_EMAIL": autor + "@local",
    }
    for name in commit_dateien:
        out, code = git_lauf(ordner, ["add", "--", name], env=env)
        if code != 0:
            return False, "git add fehlgeschlagen: %s %s" % (name, (out or "")[:120]), ""
    message = "%s\n\nAgent: %s\nAuftrag: %s\nProjekt: %s\n" % (
        (ziel or ("auftrag " + auftrag_id)).strip()[:120],
        "cli" if art == "cli" else "fenster",
        auftrag_id,
        projekt_id,
    )
    out, code = git_lauf(ordner, ["commit", "-m", message], env=env)
    if code != 0:
        if "nothing to commit" in (out or "").lower():
            return True, "nichts zu committen", ""
        return False, "commit fehlgeschlagen: " + (out or "")[:200], ""
    hash_ = (git_ok(ordner, ["rev-parse", "--short", "HEAD"]) or "").strip()
    return True, "commit %s (%s)" % (hash_, ", ".join(commit_dateien[:6])), hash_


def anordnung_ergaenze(projekt_id):
    pid = sichere_id(projekt_id)
    if not pid:
        return
    roh = _lies_json(anordnung_pfad(), {"eintraege": []})
    eintraege = roh.get("eintraege") if isinstance(roh, dict) else []
    if not isinstance(eintraege, list):
        eintraege = []
    for e in eintraege:
        if isinstance(e, dict) and e.get("id") == pid:
            return
    eintraege.append({"id": pid, "typ": "projekt", "gruppe": "projekte"})
    _schreib_json(anordnung_pfad(), {"eintraege": eintraege})


def anordnung_entferne(projekt_id):
    pid = sichere_id(projekt_id)
    roh = _lies_json(anordnung_pfad(), {"eintraege": []})
    eintraege = roh.get("eintraege") if isinstance(roh, dict) else []
    if not isinstance(eintraege, list):
        return
    neu = [e for e in eintraege if not (isinstance(e, dict) and e.get("id") == pid)]
    _schreib_json(anordnung_pfad(), {"eintraege": neu})


def projekt_einfuegen(body):
    pid = sichere_id(body.get("id") or body.get("name"))
    name = str(body.get("name") or pid).strip()[:80]
    pfad_roh = str(body.get("pfad") or "").strip()
    art = str(body.get("art") or "extern").strip()[:40] or "extern"
    if not pid:
        return {"fehler": "id ungueltig"}, 400
    if not pfad_roh:
        return {"fehler": "pfad fehlt"}, 400
    if pfad_verboten(pfad_roh):
        return {"fehler": "pfad nicht erlaubt"}, 400
    try:
        voll = Path(pfad_roh).resolve()
    except (OSError, RuntimeError):
        return {"fehler": "pfad ungueltig"}, 400
    if not voll.is_dir():
        return {"fehler": "ordner existiert nicht"}, 400
    if projekt_von(pid):
        return {"fehler": "id schon vergeben"}, 400
    #gleichen pfad nicht doppelt
    for ein in lese_register().get("projekte") or []:
        try:
            if Path(ein["pfad"]).resolve() == voll:
                return {"fehler": "pfad schon eingetragen als " + ein["id"]}, 400
        except (OSError, RuntimeError):
            continue
    ausschluss = body.get("lane_ausschluss")
    if ausschluss is None and voll.resolve() == WURZEL.resolve():
        ausschluss = standard_ausschluss()
        art = art if art != "extern" else "hub"
    if not isinstance(ausschluss, list):
        ausschluss = []
    ein = {
        "id": pid,
        "name": name or pid,
        "pfad": str(voll),
        "aktiv": True,
        "art": art,
        "eingefuegt": jetzt(),
        "lane_ausschluss": [str(x)[:80] for x in ausschluss if str(x).strip()],
    }
    daten = lese_register()
    daten["projekte"].append(ein)
    schreibe_register(daten)
    anordnung_ergaenze(pid)
    proto_event("register", pid, "eingefuegt: " + str(voll))
    return {"ok": True, "projekt": ein}, 200


def projekt_raus(body):
    pid = sichere_id(body.get("id") or body.get("projekt") or body.get("name"))
    if not pid or not projekt_von(pid):
        return {"fehler": "projekt nicht im register"}, 400
    if laufender_in(pid):
        return {"fehler": "agent laeuft noch, erst stoppen"}, 400
    daten = lese_register()
    daten["projekte"] = [e for e in daten["projekte"] if e["id"] != pid]
    schreibe_register(daten)
    anordnung_entferne(pid)
    proto_event("register", pid, "aus der liste genommen, ordner unangetastet")
    return {"ok": True, "entfernt": pid}, 200


def loop_stand(lane):
    plan_pfad = Path(lane) / ".loop" / "plan.json"
    fragen_pfad = Path(lane) / ".loop" / "fragen.md"
    aufgaben = []
    fragen = []
    modus = ""
    if plan_pfad.is_file():
        try:
            plan = json.loads(plan_pfad.read_text(encoding="utf-8-sig"))
            modus = str(plan.get("modus") or "")
            for aufg in plan.get("aufgaben") or []:
                if not isinstance(aufg, dict):
                    continue
                aufgaben.append(
                    {
                        "id": aufg.get("id") or "",
                        "ziel": aufg.get("ziel") or "",
                        "status": aufg.get("status") or "",
                        "versuche": aufg.get("versuche") or 0,
                        "fenster_hwnd": aufg.get("fenster_hwnd") or aufg.get("fenster") or "",
                    }
                )
        except (OSError, json.JSONDecodeError):
            pass
    if fragen_pfad.is_file():
        try:
            text = fragen_pfad.read_text(encoding="utf-8-sig")
            if "(noch keine)" not in text:
                for zeile in text.splitlines():
                    if zeile.strip() and not zeile.startswith("#"):
                        fragen.append(zeile.strip()[:200])
        except OSError:
            pass
    status = {}
    status_pfad = Path(lane) / ".loop" / "status.json"
    if status_pfad.is_file():
        try:
            roh = json.loads(status_pfad.read_text(encoding="utf-8-sig"))
            if isinstance(roh, dict):
                status = roh
        except (OSError, json.JSONDecodeError):
            status = {}
    return {
        "modus": status.get("modus") or modus,
        "aufgaben": aufgaben,
        "fragen": fragen[:20],
        "status": {
            "aktuell": status.get("aktuell"),
            "fertig": status.get("fertig") or [a["id"] for a in aufgaben if a.get("status") == "fertig"],
            "offen": status.get("offen") or [a["id"] for a in aufgaben if a.get("status") in ("offen", "korrektur", "laeuft")],
            "fragen": status.get("fragen") or [a["id"] for a in aufgaben if a.get("status") in ("frage", "blockiert")],
            "letzter_fehler": status.get("letzter_fehler") or "",
            "zeit": status.get("zeit") or "",
            "phase": status.get("phase") or "",
        },
    }


def stand_projekt(pid):
    sync_laeufe()
    ein = projekt_von(pid)
    if not ein:
        return None
    lane = lane_pfad(ein)
    git = git_stand(lane, ein.get("lane_ausschluss") or []) if lane else git_stand(None)
    agenten = []
    for lauf in lese_laeufe().get("laeufe") or []:
        if lauf.get("projekt") == ein["id"]:
            agenten.append(
                {
                    "id": lauf.get("id") or "",
                    "art": lauf.get("art") or "",
                    "stand": lauf.get("stand") or "",
                    "pid": lauf.get("pid"),
                    "auftrag": lauf.get("auftrag") or "",
                    "ziel": lauf.get("ziel") or "",
                    "start": lauf.get("start") or "",
                    "ende": lauf.get("ende") or "",
                    "commit": lauf.get("commit") or "",
                    "hwnd": lauf.get("hwnd") or "",
                    "kurz": lauf.get("kurz") or "",
                }
            )
    agenten = list(reversed(agenten[-8:]))
    freigaben = [f for f in lese_freigaben().get("anfragen") or [] if f.get("projekt") == ein["id"]]
    loop = loop_stand(lane) if lane else {"modus": "", "aufgaben": [], "fragen": []}
    zustand = "leer"
    loop_phase = (loop.get("status") or {}).get("phase") or ""
    if any(a.get("stand") == "laeuft" for a in agenten) or loop_phase in ("lauf", "laeuft", "warte_nach_haenger", "gesendet"):
        zustand = "laeuft"
    elif any(f.get("stand") == "wartet" for f in freigaben):
        zustand = "wartet"
    elif any(a.get("stand") == "fehler" for a in agenten[:1]):
        zustand = "fehler"
    elif agenten:
        zustand = agenten[0].get("stand") or "fertig"
    elif git.get("branch"):
        zustand = "bereit"
    letzter = agenten[0]["ziel"] if agenten else ""
    satz_teile = [zustand]
    if git.get("branch"):
        satz_teile.append("branch " + git["branch"])
    if git.get("commits"):
        c = git["commits"][0]
        autor = c.get("autor") or ""
        satz_teile.append((autor + " · " if autor else "") + (c.get("betreff") or c.get("hash") or ""))
    if any(f.get("stand") == "wartet" for f in freigaben):
        satz_teile.append("push wartet auf freigabe")
    return {
        "id": ein["id"],
        "name": ein["name"],
        "pfad": ein["pfad"],
        "aktiv": ein["aktiv"],
        "art": ein["art"],
        "lane_ausschluss": ein.get("lane_ausschluss") or [],
        "zustand": zustand,
        "letzter_auftrag": letzter,
        "stand_jetzt": {
            "text": " · ".join(satz_teile),
            "zustand": zustand,
            "zuletzt": (agenten[0].get("ende") or agenten[0].get("start") or "") if agenten else "",
        },
        "letzte_aenderungen": git,
        "agenten": agenten,
        "aufgaben": loop.get("aufgaben") or [],
        "fragen": loop.get("fragen") or [],
        "freigaben": freigaben[-8:],
        "loop_modus": loop.get("modus") or "",
        "loop_status": loop.get("status") or {},
        "naechster_schritt": _naechster(zustand, freigaben, git, loop),
        "zuletzt_gemacht": [
            {"was": a.get("kurz") or a.get("ziel") or a.get("auftrag"), "warum": "agent " + (a.get("art") or "")}
            for a in agenten[:4]
        ],
    }


def _naechster(zustand, freigaben, git, loop):
    if zustand == "laeuft":
        aktuell = (loop.get("status") or {}).get("aktuell") or ""
        return "loop laeuft%s, dann stand pruefen." % ((" bei " + aktuell) if aktuell else "")
    if any(f.get("stand") == "wartet" for f in freigaben):
        return "freigabe steht aus: push/pr/merge nur mit deinem ja."
    if loop.get("fragen"):
        return "offene frage im loop, bitte in der maske oder vom handy beantworten."
    offen = [a for a in (loop.get("aufgaben") or []) if a.get("status") in ("offen", "korrektur", "frage")]
    if offen:
        return "naechste aufgabe: " + (offen[0].get("ziel") or offen[0].get("id") or "")
    if git.get("uncommittet"):
        return "es gibt uncommittete dateien."
    if git.get("branch", "").startswith("arbeit/") and not git.get("remote"):
        return "arbeit ist lokal. ohne remote gibt es nichts zu pushen."
    return "kein offener schritt, stand halten."


def liste_mit_stand():
    sync_laeufe()
    projekte = []
    for ein in lese_register().get("projekte") or []:
        if not ein.get("aktiv", True):
            continue
        stand = stand_projekt(ein["id"])
        if stand:
            projekte.append(stand)
    return {"projekte": projekte}


def bericht_von_stand(stand):
    if not stand:
        return None
    gemacht = list(stand.get("zuletzt_gemacht") or [])
    todos = []
    for frage in stand.get("fragen") or []:
        todos.append({"text": frage, "warum": "offene frage", "art": "frage"})
    for fr in stand.get("freigaben") or []:
        if fr.get("stand") == "wartet":
            todos.append(
                {
                    "text": "freigabe %s auf %s" % (fr.get("aktion"), fr.get("branch") or ""),
                    "warum": "wartet auf dein ja",
                    "art": "freigabe",
                }
            )
    return {
        "projekt": stand["id"],
        "stand_jetzt": stand.get("stand_jetzt") or {},
        "zuletzt_gemacht": gemacht,
        "letzte_aenderungen": stand.get("letzte_aenderungen") or {},
        "was_muss_gemacht_werden": todos,
        "naechster_schritt": stand.get("naechster_schritt") or "",
        "agenten": stand.get("agenten") or [],
        "aufgaben": stand.get("aufgaben") or [],
        "fragen": stand.get("fragen") or [],
        "freigaben": stand.get("freigaben") or [],
        "loop_status": stand.get("loop_status") or {},
        "loop_modus": stand.get("loop_modus") or "",
        "pfad": stand.get("pfad") or "",
        "zustand": stand.get("zustand") or "",
    }


def neue_lauf_id():
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(int(time.time() * 1000) % 10000)


def agent_start(body):
    pid_proj = sichere_id(body.get("projekt") or body.get("id"))
    art = str(body.get("art") or "cli").strip().lower()
    auftrag_id = sichere_auftrag(body.get("auftrag") or body.get("auftrag_id") or "t1")
    ziel = str(body.get("ziel") or body.get("text") or "").strip()
    modus = str(body.get("modus") or "schrittweise").strip().lower()
    if modus not in ("schrittweise", "autonom", "vorschlagen"):
        modus = "schrittweise"
    if not pid_proj:
        return {"fehler": "projekt ungueltig"}, 400
    if art not in ("cli", "fenster"):
        return {"fehler": "art muss cli oder fenster sein"}, 400
    if not auftrag_id:
        return {"fehler": "auftrag id ungueltig"}, 400
    if not ziel or len(ziel) > 2000:
        return {"fehler": "ziel / auftragstext fehlt"}, 400
    ein = projekt_von(pid_proj)
    if not ein:
        return {"fehler": "projekt nicht im register"}, 400
    lane = lane_pfad(ein)
    if not lane:
        return {"fehler": "lane ungueltig oder nicht erlaubt"}, 400
    if laufender_in(pid_proj):
        return {"fehler": "in diesem projekt laeuft schon ein agent"}, 400
    ok, msg = branch_anlegen(lane, arbeit_branch(auftrag_id))
    if not ok:
        return {"fehler": "branch: " + msg}, 400
    #auftrag-datei
    loop_root = lane / ".loop"
    (loop_root / "auftrag").mkdir(parents=True, exist_ok=True)
    (loop_root / "antwort").mkdir(parents=True, exist_ok=True)
    auftrag = {
        "id": auftrag_id,
        "art": "auftrag",
        "ziel": ziel,
        "dateien": list(body.get("dateien") or []),
        "fertig_wenn": str(body.get("fertig_wenn") or "datei liegt vor, nichts sonst geaendert"),
        "verboten": [
            "nichts ausserhalb der lane",
            "kein git commit",
            "kein git push",
            "kein deploy",
            "nichts oeffentliches",
        ],
        "hinweis": "nur in diesem projektordner. nicht committen, nicht pushen. am ende .loop/antwort/%s.json schreiben." % auftrag_id,
    }
    (loop_root / "auftrag" / ("%s.json" % auftrag_id)).write_text(
        json.dumps(auftrag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lauf = {
        "id": neue_lauf_id(),
        "projekt": pid_proj,
        "art": art,
        "auftrag": auftrag_id,
        "ziel": ziel,
        "stand": "laeuft",
        "start": jetzt(),
        "ende": "",
        "pid": None,
        "hwnd": "",
        "commit": "",
        "kurz": "",
        "abgeschlossen": False,
        "log": str(lane / ".dev" / "laeufe" / ("%s.log" % auftrag_id)),
    }
    if art == "fenster":
        return _start_fenster(ein, lane, lauf, auftrag)
    return _start_cli(ein, lane, lauf, auftrag)


def _start_cli(ein, lane, lauf, auftrag):
    exe = finde_agent_exe()
    if not exe:
        return {"fehler": "cursor agent nicht gefunden (agent login?)"}, 500
    log_dir = lane / ".dev" / "laeufe"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_pfad = Path(lauf["log"])
    prompt = (
        "lies die datei .loop/auftrag/%s.json und fuehre genau diesen auftrag aus. "
        "nur in diesem ordner arbeiten. keine dateien ausserhalb anfassen. "
        "nicht git committen, nicht git pushen, kein remote, kein deploy. "
        "am ende .loop/antwort/%s.json schreiben (status, geaenderte_dateien, kurz). "
        "ziel: %s"
    ) % (lauf["auftrag"], lauf["auftrag"], auftrag.get("ziel") or "")
    args = ["-p", "--force", "--trust", "--workspace", str(lane), "--output-format", "text", prompt]
    try:
        with open(log_pfad, "w", encoding="utf-8") as logf:
            proc = subprocess.Popen(
                **_OHNE_FENSTER,
                args=[exe] + args,
                cwd=str(lane),
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
    except OSError as e:
        return {"fehler": "agent startet nicht: %s" % e}, 500
    lauf["pid"] = proc.pid
    with _lock:
        daten = lese_laeufe()
        daten["laeufe"].append(lauf)
        schreibe_laeufe(daten)
    proto_event("start", ein["id"], "cli pid=%s auftrag=%s" % (proc.pid, lauf["auftrag"]), agent="cli", auftrag=lauf["auftrag"])
    t = threading.Thread(target=_warte_prozess, args=(proc, lauf["id"]), daemon=True)
    t.start()
    return {"ok": True, "lauf": _oeffentliche_lauf(lauf)}, 200


def _warte_prozess(proc, lauf_id):
    try:
        proc.wait()
    except OSError:
        pass
    #sync erkennt den toten pid und macht den commit
    time.sleep(0.2)
    sync_laeufe()


def _start_fenster(ein, lane, lauf, auftrag):
    tipper = finde_tipper()
    if not tipper:
        return {"fehler": "tipper.py nicht gefunden"}, 500
    py = py_fuer(tipper)
    try:
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=[py, str(tipper), "oeffnen", "--ordner", str(lane)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            cwd=str(tipper.parent),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"fehler": "fenster oeffnen fehlgeschlagen: %s" % e}, 500
    text = (fertig.stdout or "") + (fertig.stderr or "")
    hwnd = ""
    pid = None
    m = re.search(r"hwnd=(\d+)", text)
    if m:
        hwnd = m.group(1)
    m2 = re.search(r"pid=(\d+)", text)
    if m2:
        try:
            pid = int(m2.group(1))
        except ValueError:
            pid = None
    if fertig.returncode != 0 or not hwnd:
        return {"fehler": "kein neues fenster: " + text.strip()[:300]}, 500
    lauf["pid"] = pid
    lauf["hwnd"] = hwnd
    lauf["stand"] = "fenster_offen"
    lauf["kurz"] = "fenster hwnd=%s, nicht gesendet" % hwnd
    #bewusst nichts ins fenster tippen oder senden
    with _lock:
        daten = lese_laeufe()
        daten["laeufe"].append(lauf)
        schreibe_laeufe(daten)
    proto_event(
        "start",
        ein["id"],
        "fenster hwnd=%s (kein senden)" % hwnd,
        agent="fenster",
        auftrag=lauf["auftrag"],
        hwnd=hwnd,
    )
    return {"ok": True, "lauf": _oeffentliche_lauf(lauf), "hinweis": "fenster offen, nichts gesendet"}, 200


def _oeffentliche_lauf(lauf):
    return {
        "id": lauf.get("id"),
        "projekt": lauf.get("projekt"),
        "art": lauf.get("art"),
        "auftrag": lauf.get("auftrag"),
        "ziel": lauf.get("ziel"),
        "stand": lauf.get("stand"),
        "pid": lauf.get("pid"),
        "hwnd": lauf.get("hwnd") or "",
        "start": lauf.get("start"),
        "commit": lauf.get("commit") or "",
        "kurz": lauf.get("kurz") or "",
    }


def agent_stopp(body):
    pid_proj = sichere_id(body.get("projekt") or body.get("id"))
    if not pid_proj:
        return {"fehler": "projekt ungueltig"}, 400
    laeufe = laufender_in(pid_proj)
    #auch fenster_offen
    if not laeufe:
        for lauf in lese_laeufe().get("laeufe") or []:
            if lauf.get("projekt") == pid_proj and lauf.get("stand") in ("laeuft", "fenster_offen"):
                laeufe.append(lauf)
    if not laeufe:
        return {"fehler": "kein laufender agent"}, 400
    ergebnisse = []
    for lauf in laeufe:
        pid = lauf.get("pid")
        ok = True
        if pid:
            ok = kill_pid(pid)
        _mark_lauf(lauf.get("id"), stand="angehalten", kurz="per pid gestoppt" if pid else "ohne pid markiert")
        proto_event("stopp", pid_proj, "pid=%s ok=%s" % (pid, ok), auftrag=lauf.get("auftrag"))
        ergebnisse.append({"id": lauf.get("id"), "pid": pid, "ok": ok})
    return {"ok": True, "gestoppt": ergebnisse}, 200


def git_freigabe(body):
    pid_proj = sichere_id(body.get("projekt") or body.get("id"))
    aktion = str(body.get("aktion") or "push").strip().lower()
    ja = body.get("ja") is True
    ablehnen = str(body.get("aktion") or "").strip().lower() == "ablehnen" or body.get("ablehnen") is True
    if body.get("ablehnen") is True:
        ablehnen = True
    if not pid_proj:
        return {"fehler": "projekt ungueltig"}, 400
    if aktion not in ("push", "pr", "merge", "ablehnen"):
        return {"fehler": "aktion muss push, pr, merge oder ablehnen sein"}, 400
    ein = projekt_von(pid_proj)
    if not ein:
        return {"fehler": "projekt nicht im register"}, 400
    lane = lane_pfad(ein)
    if not lane:
        return {"fehler": "lane ungueltig"}, 400
    branch = aktueller_branch(lane)
    #bestehende anfrage suchen
    daten = lese_freigaben()
    offen = None
    for an in daten.get("anfragen") or []:
        if an.get("projekt") == pid_proj and an.get("stand") == "wartet":
            offen = an
            break
    if ablehnen or aktion == "ablehnen":
        if not offen:
            return {"fehler": "keine offene anfrage"}, 400
        offen["stand"] = "abgelehnt"
        offen["ende"] = jetzt()
        schreibe_freigaben(daten)
        proto_event("ablehnung", pid_proj, "freigabe %s abgelehnt" % offen.get("aktion"), branch=offen.get("branch"))
        return {"ok": True, "anfrage": offen}, 200
    if not ja:
        if offen and offen.get("aktion") == aktion:
            return {"ok": True, "anfrage": offen, "hinweis": "wartet schon auf freigabe, nichts ausgefuehrt"}, 200
        an = {
            "id": neue_lauf_id(),
            "projekt": pid_proj,
            "aktion": aktion,
            "stand": "wartet",
            "branch": branch,
            "zeit": jetzt(),
            "remote": hat_remote(lane),
        }
        daten["anfragen"].append(an)
        schreibe_freigaben(daten)
        proto_event("freigabe", pid_proj, "%s angefragt auf %s, wartet" % (aktion, branch), branch=branch)
        return {"ok": True, "anfrage": an, "ausgefuehrt": False}, 200
    #ja=true: nur ausfuehren wenn eine offene anfrage existiert (oder jetzt erstellt und sofort)
    if not offen:
        offen = {
            "id": neue_lauf_id(),
            "projekt": pid_proj,
            "aktion": aktion,
            "stand": "wartet",
            "branch": branch,
            "zeit": jetzt(),
            "remote": hat_remote(lane),
        }
        daten["anfragen"].append(offen)
        schreibe_freigaben(daten)
    if not hat_remote(lane):
        offen["stand"] = "abgelehnt"
        offen["ende"] = jetzt()
        offen["grund"] = "kein remote, push nicht moeglich"
        schreibe_freigaben(daten)
        proto_event("ablehnung", pid_proj, "kein remote, %s nicht ausgefuehrt" % aktion, branch=branch)
        return {"ok": False, "fehler": "kein remote, nichts gepusht", "anfrage": offen, "ausgefuehrt": False}, 400
    #es gibt ein remote: trotzdem nur den einen schritt, nie force
    if aktion == "push":
        out, code = git_lauf(lane, ["push", "-u", "origin", branch], timeout=40)
        if code != 0:
            offen["stand"] = "fehler"
            offen["ende"] = jetzt()
            offen["grund"] = (out or "push fehlgeschlagen")[:300]
            schreibe_freigaben(daten)
            proto_event("fehler", pid_proj, "push fehlgeschlagen", branch=branch)
            return {"ok": False, "fehler": offen["grund"], "ausgefuehrt": False, "anfrage": offen}, 500
        offen["stand"] = "ausgefuehrt"
        offen["ende"] = jetzt()
        schreibe_freigaben(daten)
        proto_event("freigabe", pid_proj, "push ausgefuehrt auf " + branch, branch=branch)
        return {"ok": True, "ausgefuehrt": True, "anfrage": offen}, 200
    #pr / merge: nicht still, nur vermerken dass es ein ja gab aber der schritt hier noch nicht gebaut ist
    offen["stand"] = "wartet"
    offen["grund"] = "pr/merge ist noch nicht automatisch, nur push ist verdrahtet"
    schreibe_freigaben(daten)
    return {"ok": False, "fehler": "pr/merge noch nicht automatisch, anfrage bleibt offen", "anfrage": offen, "ausgefuehrt": False}, 400


def fragen_antwort(body):
    pid_proj = sichere_id(body.get("projekt") or body.get("id"))
    text = str(body.get("antwort") or body.get("text") or "").strip()
    if not pid_proj or not projekt_von(pid_proj):
        return {"fehler": "projekt ungueltig"}, 400
    if not text or len(text) > 2000:
        return {"fehler": "antwort fehlt"}, 400
    ein = projekt_von(pid_proj)
    lane = lane_pfad(ein)
    if not lane:
        return {"fehler": "lane ungueltig"}, 400
    fragen = lane / ".loop" / "fragen.md"
    fragen.parent.mkdir(parents=True, exist_ok=True)
    with fragen.open("a", encoding="utf-8") as f:
        f.write("\n## antwort %s\n\n%s\n" % (jetzt(), text))
    proto_event("frage", pid_proj, "antwort: " + text[:160])
    return {"ok": True}, 200


def loop_start(body):
    pid_proj = sichere_id(body.get("projekt") or body.get("id"))
    modus = str(body.get("modus") or "").strip().lower()
    ja = body.get("ja") is True
    ein = projekt_von(pid_proj) if pid_proj else None
    if not ein:
        return {"fehler": "projekt ungueltig"}, 400
    lane = lane_pfad(ein)
    if not lane:
        return {"fehler": "lane ungueltig"}, 400
    loop_py = finde_loop()
    if not loop_py or not loop_py.is_file():
        return {"fehler": "loop.py nicht gefunden"}, 500
    py = py_fuer(loop_py)
    plan_pfad = lane / ".loop" / "plan.json"
    plan_modus = ""
    if plan_pfad.is_file():
        try:
            plan_modus = str((json.loads(plan_pfad.read_text(encoding="utf-8-sig")) or {}).get("modus") or "")
        except (OSError, json.JSONDecodeError):
            plan_modus = ""
    if modus not in ("schrittweise", "autonom"):
        modus = plan_modus or "schrittweise"
    if modus not in ("schrittweise", "autonom"):
        return {"fehler": "modus muss schrittweise oder autonom sein"}, 400
    if modus == "autonom" and not ja:
        return {"fehler": "autonom startet nur mit ja=true (einmalige freigabe, nur lokal)"}, 400
    if not plan_pfad.is_file():
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=[py, str(loop_py), "init", "--lane", str(lane), "--modus", modus],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(loop_py.parent),
        )
        if fertig.returncode != 0:
            return {"fehler": "loop init: " + ((fertig.stdout or "") + (fertig.stderr or ""))[:300]}, 500
    elif plan_modus and plan_modus != modus:
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=[py, str(loop_py), "modus", "--lane", str(lane), "--modus", modus],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(loop_py.parent),
        )
        if fertig.returncode != 0:
            return {"fehler": "modus setzen: " + ((fertig.stdout or "") + (fertig.stderr or ""))[:300]}, 500
    #schon laufender loop?
    for lauf in laufender_in(pid_proj):
        if lauf.get("art") == "loop":
            return {"ok": True, "hinweis": "loop laeuft schon", "lauf": _oeffentliche_lauf(lauf)}, 200
    log_dir = lane / ".loop"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_pfad = log_dir / "lauf.log"
    cmd = [py, str(loop_py), "lauf", "--lane", str(lane)]
    if modus == "autonom" and ja:
        cmd.append("--ja")
    try:
        max_min = int(body.get("max_min") or 0)
    except (TypeError, ValueError):
        max_min = 0
    if 1 <= max_min <= 240:
        cmd.extend(["--max-min", str(max_min)])
    lauf = {
        "id": neue_lauf_id(),
        "projekt": pid_proj,
        "art": "loop",
        "auftrag": "lauf",
        "ziel": "loop %s" % modus,
        "stand": "laeuft",
        "start": jetzt(),
        "log": str(log_pfad),
        "pid": None,
        "hwnd": "",
        "commit": "",
        "kurz": "loop gestartet modus=" + modus,
    }
    try:
        with open(log_pfad, "a", encoding="utf-8") as logf:
            logf.write("\n# start %s %s\n" % (jetzt(), " ".join(cmd)))
            proc = subprocess.Popen(
                **_OHNE_FENSTER,
                args=cmd,
                cwd=str(loop_py.parent),
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
    except OSError as e:
        return {"fehler": "loop startet nicht: %s" % e}, 500
    lauf["pid"] = proc.pid
    with _lock:
        daten = lese_laeufe()
        daten.setdefault("laeufe", []).append(lauf)
        schreibe_laeufe(daten)
    proto_event("start", pid_proj, "loop pid=%s modus=%s" % (proc.pid, modus), agent="loop")
    t = threading.Thread(target=_warte_prozess, args=(proc, lauf["id"]), daemon=True)
    t.start()
    return {"ok": True, "modus": modus, "lane": str(lane), "lauf": _oeffentliche_lauf(lauf)}, 200


def handle_get(handler, pfad, frage):
    def q(name):
        return (frage.get(name) or [""])[0]

    if pfad == "/zentrale/projekte":
        handler.sende_json(liste_mit_stand())
        return True
    if pfad == "/zentrale/stand":
        stand = stand_projekt(q("projekt"))
        if not stand:
            handler.sende_json({"fehler": "projekt nicht im register"}, 400)
            return True
        handler.sende_json(bericht_von_stand(stand))
        return True
    if pfad == "/zentrale/protokoll":
        handler.sende_json(lese_protokoll())
        return True
    if pfad == "/zentrale/fragen":
        stand = stand_projekt(q("projekt"))
        if not stand:
            handler.sende_json({"fehler": "projekt nicht im register"}, 400)
            return True
        handler.sende_json({"projekt": stand["id"], "fragen": stand.get("fragen") or []})
        return True
    if pfad == "/zentrale/loop/stand":
        stand = stand_projekt(q("projekt"))
        if not stand:
            handler.sende_json({"fehler": "projekt nicht im register"}, 400)
            return True
        handler.sende_json(
            {
                "projekt": stand["id"],
                "modus": stand.get("loop_modus") or "",
                "aufgaben": stand.get("aufgaben") or [],
                "fragen": stand.get("fragen") or [],
                "status": stand.get("loop_status") or {},
            }
        )
        return True
    if pfad == "/zentrale/loop/status":
        pid = q("projekt")
        if pid:
            stand = stand_projekt(pid)
            if not stand:
                handler.sende_json({"fehler": "projekt nicht im register"}, 400)
                return True
            handler.sende_json({"zeit": jetzt(), "projekte": [{
                "id": stand["id"],
                "name": stand.get("name") or stand["id"],
                "pfad": stand.get("pfad") or "",
                **(stand.get("loop_status") or {}),
                "modus": stand.get("loop_modus") or (stand.get("loop_status") or {}).get("modus") or "",
            }]})
            return True
        projekte = []
        for ein in liste_mit_stand().get("projekte") or []:
            st = ein.get("loop_status") or {}
            projekte.append({
                "id": ein["id"],
                "name": ein.get("name") or ein["id"],
                "pfad": ein.get("pfad") or "",
                "aktuell": st.get("aktuell"),
                "fertig": st.get("fertig") or [],
                "offen": st.get("offen") or [],
                "fragen": st.get("fragen") or [],
                "letzter_fehler": st.get("letzter_fehler") or "",
                "zeit": st.get("zeit") or "",
                "modus": ein.get("loop_modus") or st.get("modus") or "",
                "phase": st.get("phase") or "",
            })
        handler.sende_json({"zeit": jetzt(), "projekte": projekte})
        return True
    if pfad == "/zentrale/freigaben":
        alle = lese_freigaben().get("anfragen") or []
        nur = q("stand") or "wartet"
        if nur == "alle":
            liste = alle
        else:
            liste = [a for a in alle if a.get("stand") == nur]
        handler.sende_json({"anfragen": liste, "stand": nur})
        return True
    return False


def handle_post(handler, pfad, body):
    if not isinstance(body, dict):
        handler.sende_json({"fehler": "ungueltig"}, 400)
        return True
    routing = {
        "/zentrale/projekte": projekt_einfuegen,
        "/zentrale/projekte/raus": projekt_raus,
        "/zentrale/agent/start": agent_start,
        "/zentrale/agent/stopp": agent_stopp,
        "/zentrale/git/freigabe": git_freigabe,
        "/zentrale/fragen/antwort": fragen_antwort,
        "/zentrale/loop/start": loop_start,
        "/zentrale/loop/stopp": agent_stopp,
    }
    fn = routing.get(pfad)
    if not fn:
        return False
    daten, code = fn(body)
    handler.sende_json(daten, code)
    return True
