#serviert die ansicht und die bruecke, nur lokal
import json
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import datei_lokal

#keine konsolenfenster aufpoppen lassen (windows)
def _subprocess_kwargs():
    if sys.platform != "win32":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": info,
    }


_OHNE_FENSTER = _subprocess_kwargs()

WURZEL = Path(__file__).resolve().parent.parent
MASKE = WURZEL / "maske"
LAGE = WURZEL / "bruecke" / "lage.json"
EINGRIFF = WURZEL / "bruecke" / "eingriff.json"
ANORDNUNG = WURZEL / "maske" / "anordnung.json"
LISTE_YAML = WURZEL / "projekte" / "liste.yaml"
DEV_STATUS = WURZEL / "dev" / "status.json"
DEV_QUEUE = WURZEL / "dev" / "warteschlange.py"
HOST = "127.0.0.1"
PORT = 17341
ERLAUBTE_HOSTS = {"127.0.0.1:17341", "localhost:17341"}
sys.path.insert(0, str(Path(__file__).resolve().parent))
import zentrale
MAX_BODY = 50000
MAX_ANORDNUNG = 200
GIT_TIMEOUT = 8
_STATUS_CACHE = {"zeit": 0.0, "daten": None}
_STATUS_TTL = 1.5
_BERICHT_CACHE = {}
_BERICHT_TTL = 10.0
_DIENST_CACHE = {"zeit": 0.0, "daten": {}}
_DIENST_TTL = 10.0
#geheimnisse nie lesen oder ausgeben
GEHEIM_NAMEN = {
    ".env",
    "kontakt.txt",
    ".desk_token",
    ".tunnel_token",
    "chats.json",
}
GEHEIM_TEILE = (".certs",)
MAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
TOKEN_RE = re.compile(
    r"(?i)(ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|sk-|xox[baprs]-|Bearer\s+)[A-Za-z0-9_\-.=]{8,}"
)

ARTEN = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
    ".png": "image/png",
}


def lese_lage():
    #leere liste, wenn die datei fehlt. lokale datei hat vorrang
    pfad = datei_lokal.aktiv(LAGE)
    if not pfad.exists():
        return {"agenten": []}
    return json.loads(pfad.read_text(encoding="utf-8"))


def schreibe_lage(daten):
    datei_lokal.aktiv(LAGE).write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_liste_namen():
    #minimale yaml-lesung fuer - name:
    liste = datei_lokal.aktiv(LISTE_YAML)
    if not liste.exists():
        return []
    namen = []
    for zeile in liste.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile.startswith("- name:"):
            name = zeile.split(":", 1)[1].strip().strip('"').strip("'")
            if name:
                namen.append(name)
    return namen


def sicheres_projekt(name):
    #nur ein ordnername, kein pfad
    if not name or len(name) > 80:
        return ""
    if ".." in name or "/" in name or "\\" in name:
        return ""
    if name.startswith(".") or name.startswith("-"):
        return ""
    erlaubt = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    for zeichen in name:
        if zeichen not in erlaubt:
            return ""
    return name


def projekt_aus_liste(name):
    #projektname muss in liste.yaml stehen (oder alles)
    sauber = sicheres_projekt(name)
    if not sauber:
        return ""
    if sauber == "alles":
        return sauber
    if sauber not in parse_liste_namen():
        return ""
    return sauber


def sichere_id(wert):
    #id fuer anordnung: projekt oder dienst
    return sicheres_projekt(str(wert or ""))


def leere_anordnung():
    return {"eintraege": []}


def lese_anordnung():
    pfad = datei_lokal.aktiv(ANORDNUNG)
    if not pfad.exists():
        return leere_anordnung()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return leere_anordnung()
    return bereinige_anordnung(roh)


def bereinige_anordnung(roh):
    #nur namen/ids, keine pfade oder geheimnisse
    eintraege = []
    gesehen = set()
    quelle = []
    if isinstance(roh, dict):
        quelle = roh.get("eintraege") or []
    if not isinstance(quelle, list):
        return leere_anordnung()
    for roh_eintrag in quelle[:MAX_ANORDNUNG]:
        if not isinstance(roh_eintrag, dict):
            continue
        eid = sichere_id(roh_eintrag.get("id"))
        typ = str(roh_eintrag.get("typ") or "").strip().lower()
        gruppe = str(roh_eintrag.get("gruppe") or "").strip().lower()
        if not eid or eid in gesehen:
            continue
        if typ not in ("projekt", "dienst"):
            continue
        if gruppe not in ("projekte", "dienste"):
            continue
        gesehen.add(eid)
        eintraege.append({"id": eid, "typ": typ, "gruppe": gruppe})
    return {"eintraege": eintraege}


def schreibe_anordnung(daten):
    sauber = bereinige_anordnung(daten)
    datei_lokal.aktiv(ANORDNUNG).write_text(
        json.dumps(sauber, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sauber


def lese_dev_protokoll(projekt):
    name = sicheres_projekt(projekt)
    erwartet = (name + "/.dev/protokoll.md") if name else ".dev/protokoll.md"
    if not name:
        return {"text": "", "erwartet": erwartet}
    datei = (WURZEL / name / ".dev" / "protokoll.md").resolve()
    if not datei.is_relative_to(WURZEL.resolve()) or not datei.is_file():
        return {"text": "", "erwartet": erwartet}
    return {"text": datei.read_text(encoding="utf-8")[:20000], "erwartet": erwartet}


def lese_dev_log(projekt):
    #nur dateien unter <projekt>/.dev/, nichts anderes
    name = sicheres_projekt(projekt)
    erwartet = (name + "/.dev/laeufe/") if name else ".dev/laeufe/"
    if not name:
        return {"text": "", "pfad": "", "erwartet": erwartet}
    root = (WURZEL / name / ".dev").resolve()
    hub = WURZEL.resolve()
    if not root.is_relative_to(hub) or not root.is_dir():
        return {"text": "", "pfad": "", "erwartet": erwartet}
    status = lese_dev_status()
    eintrag = (status.get("projekte") or {}).get(name) or {}
    kandidaten = []
    log_pfad = eintrag.get("log_pfad") or ""
    if log_pfad:
        kandidaten.append(Path(log_pfad))
    laeufe = root / "laeufe"
    if laeufe.is_dir():
        kandidaten.extend(sorted(laeufe.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True))
    for kandidat in kandidaten:
        try:
            datei = kandidat.resolve()
        except OSError:
            continue
        if not datei.is_file():
            continue
        if not datei.is_relative_to(root):
            continue
        roh = datei.read_text(encoding="utf-8", errors="replace")
        return {"text": roh[-12000:], "pfad": str(datei), "erwartet": erwartet}
    return {"text": "", "pfad": "", "erwartet": erwartet}


def lese_dev_status():
    #status aus warteschlange, kurz cachen damit pollen keine fenster spawnt
    jetzt = time.monotonic()
    if _STATUS_CACHE["daten"] is not None and (jetzt - _STATUS_CACHE["zeit"]) < _STATUS_TTL:
        return _STATUS_CACHE["daten"]
    daten = None
    if DEV_QUEUE.exists():
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=[sys.executable, str(DEV_QUEUE), "--hub", str(WURZEL), "status"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(WURZEL),
        )
        if fertig.returncode == 0 and fertig.stdout.strip():
            try:
                daten = json.loads(fertig.stdout)
            except json.JSONDecodeError:
                daten = None
    if daten is None:
        status_pfad = datei_lokal.aktiv(DEV_STATUS)
        if not status_pfad.exists():
            daten = {"tag": "", "laeufe_heute": 0, "projekte": {}}
        else:
            daten = json.loads(status_pfad.read_text(encoding="utf-8"))
    _STATUS_CACHE["zeit"] = jetzt
    _STATUS_CACHE["daten"] = daten
    return daten


def lauf_warteschlange(args):
    #warteschlange nur lokal ueber python
    if not DEV_QUEUE.exists():
        return {"fehler": "warteschlange fehlt"}, 500
    fertig = subprocess.run(
        **_OHNE_FENSTER,
        args=[sys.executable, str(DEV_QUEUE), "--hub", str(WURZEL), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(WURZEL),
    )
    if fertig.returncode != 0:
        text = (fertig.stderr or fertig.stdout or "fehler").strip()
        return {"fehler": text[:2000]}, 500
    try:
        return json.loads(fertig.stdout or "{}"), 200
    except json.JSONDecodeError:
        return {"roh": (fertig.stdout or "")[:2000]}, 200


def host_erlaubt(wert):
    if not wert:
        return False
    return wert.strip().lower() in ERLAUBTE_HOSTS


def origin_erlaubt(wert):
    if not wert:
        return False
    try:
        geparst = urlparse(wert.strip())
    except ValueError:
        return False
    if geparst.scheme not in ("http", "https"):
        return False
    host = geparst.netloc.lower()
    return host in ERLAUBTE_HOSTS


def maskiere_geheim(text):
    #mails und tokens in betrefs/meldungen ausblenden
    roh = str(text or "")
    roh = MAIL_RE.sub("[mail]", roh)
    roh = TOKEN_RE.sub("[secret]", roh)
    return roh


def ist_geheim_datei(name):
    basis = Path(str(name or "")).name.lower()
    if basis in GEHEIM_NAMEN:
        return True
    niedrig = str(name or "").replace("\\", "/").lower()
    for teil in GEHEIM_TEILE:
        if teil in niedrig:
            return True
    return False


def lese_sichere_textdatei(datei, limit=20000):
    #nur normale textdateien unter dem hub, keine secrets
    try:
        ziel = datei.resolve()
    except OSError:
        return ""
    if not ziel.is_file():
        return ""
    if not ziel.is_relative_to(WURZEL.resolve()):
        return ""
    if ist_geheim_datei(ziel.name) or ist_geheim_datei(str(ziel)):
        return ""
    try:
        return ziel.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def git_lauf(ordner, args):
    #git nur lokal, kein fetch, timeout, ohne fenster
    if not ordner.is_dir():
        return ""
    try:
        fertig = subprocess.run(
            **_OHNE_FENSTER,
            args=["git", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ordner),
            timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if fertig.returncode != 0:
        return ""
    return fertig.stdout or ""


def parse_protokoll_felder(text):
    #einfache schluessel:wert zeilen aus .dev/protokoll.md
    felder = {
        "datum": "",
        "uhrzeit": "",
        "gefunden": "",
        "gemacht": "",
        "offen": "",
        "warum": "",
        "angeschaut": "",
    }
    for zeile in str(text or "").splitlines():
        if ":" not in zeile:
            continue
        schluessel, wert = zeile.split(":", 1)
        key = schluessel.strip().lower()
        if key in felder and not felder[key]:
            felder[key] = wert.strip()
    return felder


def parse_wege_texte(text):
    #nummerierte wege / bullets aus protokoll und vorschlag
    fund = []
    for zeile in str(text or "").splitlines():
        m = re.match(r"^\s*(?:[-*]|\d+[.)])\s*(.+)$", zeile)
        if not m:
            continue
        inhalt = m.group(1).strip()
        if not inhalt:
            continue
        if re.search(r"weg|aufwand|vorschl|option|variante|offen|todo|fehlt", zeile, re.I) or re.match(
            r"^\s*\d+[.)]", zeile
        ):
            fund.append(inhalt)
    return fund


def funde_aus_text(text):
    #bekannte funde aus gefunden/offen-zeilen
    liste = []
    niedrig = str(text or "").lower()
    muster = [
        ("ci badge fehlt", "ci-badge", "ci aktiv ohne badge"),
        ("falsches topic", "topic", "topic typescript ohne ts"),
        (".dev nicht in .gitignore", ".dev", ".dev/ nicht in ignore"),
        (".dev nicht in ignore", ".dev", ".dev/ nicht in ignore"),
    ]
    for text_out, _, nadel in muster:
        if nadel in niedrig or text_out in niedrig:
            liste.append(text_out)
    return liste


def stand_satz(eintrag, felder):
    #ein satz klartext zum stand
    zustand = (eintrag or {}).get("zustand") or "leer"
    ende = (eintrag or {}).get("ende") or ""
    start = (eintrag or {}).get("start") or ""
    zuletzt = ende or start or ""
    if not zuletzt and felder.get("datum"):
        zuletzt = (felder.get("datum") + " " + (felder.get("uhrzeit") or "")).strip()
    if zustand in ("laeuft", "wartet"):
        label = "laeuft" if zustand == "laeuft" else "wartet auf freigabe"
    elif zustand in ("fertig", "pr-offen"):
        label = "fertig"
    elif zustand == "fehler":
        label = "problem"
    elif zustand == "fehlt":
        label = "ordner fehlt"
    elif zuletzt or felder.get("gemacht"):
        label = "fertig" if felder.get("gemacht") else "noch nie gelaufen"
        if felder.get("offen") and "chef" in felder.get("offen", "").lower():
            label = "wartet auf freigabe"
        elif felder.get("gemacht") and "nur gelesen" in felder.get("gemacht", "").lower():
            label = "wartet auf freigabe"
    else:
        label = "noch nie gelaufen"
    if zuletzt:
        return f"{label} · zuletzt {zuletzt}", label, zuletzt
    return f"{label} · noch kein zeitstempel", label, ""


def git_bericht(ordner):
    commits = []
    roh = git_lauf(ordner, ["log", "-5", "--format=%h|%ad|%an|%s", "--date=format:%Y-%m-%d %H:%M"])
    for zeile in roh.splitlines():
        teile = zeile.split("|", 3)
        if len(teile) < 4:
            continue
        commits.append(
            {
                "hash": teile[0].strip(),
                "datum": teile[1].strip(),
                "autor": maskiere_geheim(teile[2].strip()),
                "betreff": maskiere_geheim(teile[3].strip()),
            }
        )
    uncommittet = []
    for zeile in git_lauf(ordner, ["status", "--porcelain"]).splitlines():
        if len(zeile) < 4:
            continue
        name = zeile[3:].strip()
        if " -> " in name:
            name = name.split(" -> ", 1)[1].strip()
        if ist_geheim_datei(name):
            continue
        if name:
            uncommittet.append(name)
    ahead = 0
    behind = 0
    upstream = ""
    kurz = git_lauf(ordner, ["status", "-sb"]).splitlines()
    if kurz:
        kopf = kurz[0].strip()
        if kopf.startswith("## "):
            rest = kopf[3:]
            if "..." in rest:
                links, rechts = rest.split("...", 1)
                upstream = rechts.split(" ", 1)[0].strip()
            else:
                upstream = ""
            m = re.search(r"\[ahead (\d+)(?:, behind (\d+))?\]", rest)
            if m:
                ahead = int(m.group(1) or 0)
                behind = int(m.group(2) or 0)
            else:
                m2 = re.search(r"\[behind (\d+)\]", rest)
                if m2:
                    behind = int(m2.group(1) or 0)
    branch = (git_lauf(ordner, ["branch", "--show-current"]) or "").strip()
    return {
        "commits": commits,
        "uncommittet": uncommittet[:40],
        "ahead": ahead,
        "behind": behind,
        "upstream": upstream,
        "branch": branch,
        "remote": bool((git_lauf(ordner, ["remote"]) or "").strip()),
    }


def baue_todos(protokoll, vorschlag):
    todos = []
    gesehen = set()
    felder = parse_protokoll_felder(protokoll)
    for fund in funde_aus_text(protokoll + "\n" + felder.get("gefunden", "") + "\n" + felder.get("offen", "")):
        key = fund.lower()
        if key in gesehen:
            continue
        gesehen.add(key)
        todos.append(
            {
                "text": fund,
                "warum": "aus .dev/protokoll.md gefunden/offen",
                "art": "vorschlag",
            }
        )
    for weg in parse_wege_texte(protokoll):
        key = weg.lower()
        if key in gesehen:
            continue
        gesehen.add(key)
        todos.append(
            {
                "text": maskiere_geheim(weg),
                "warum": "weg aus .dev/protokoll.md",
                "art": "vorschlag",
            }
        )
    if vorschlag.strip():
        for weg in parse_wege_texte(vorschlag)[:4]:
            key = weg.lower()
            if key in gesehen:
                continue
            gesehen.add(key)
            todos.append(
                {
                    "text": maskiere_geheim(weg),
                    "warum": "aus .dev/agents-vorschlag.md",
                    "art": "vorschlag",
                }
            )
        if not parse_wege_texte(vorschlag):
            todos.append(
                {
                    "text": "fehlende AGENTS-abschnitte pruefen",
                    "warum": ".dev/agents-vorschlag.md vorhanden",
                    "art": "vorschlag",
                }
            )
    return todos[:12]


def naechster_schritt_text(todos, felder, zustand):
    if zustand == "laeuft":
        return "lauf abwarten, dann protokoll lesen."
    if zustand == "wartet":
        return "wege im panel abhaken und freigeben."
    if todos:
        return "als naechstes: " + todos[0]["text"]
    if felder.get("offen"):
        return "offen klaeren: " + maskiere_geheim(felder["offen"])
    return "kein offener schritt, stand halten."


def baue_bericht(projekt):
    name = projekt_aus_liste(projekt)
    if not name or name == "alles":
        return None
    jetzt = time.monotonic()
    cache = _BERICHT_CACHE.get(name)
    if cache and (jetzt - cache["zeit"]) < _BERICHT_TTL:
        return cache["daten"]
    status = lese_dev_status()
    eintrag = (status.get("projekte") or {}).get(name) or {}
    ordner = WURZEL / name
    proto = lese_sichere_textdatei(ordner / ".dev" / "protokoll.md")
    vorschlag = lese_sichere_textdatei(ordner / ".dev" / "agents-vorschlag.md")
    log = lese_dev_log(name).get("text") or ""
    felder = parse_protokoll_felder(proto)
    satz, label, zuletzt = stand_satz(eintrag, felder)
    gemacht = []
    if felder.get("gemacht"):
        gemacht.append(
            {
                "was": maskiere_geheim(felder["gemacht"]),
                "warum": maskiere_geheim(felder.get("gefunden") or felder.get("warum") or "aus letztem protokoll"),
            }
        )
    if eintrag.get("letzter_auftrag"):
        gemacht.append(
            {
                "was": maskiere_geheim(eintrag["letzter_auftrag"]),
                "warum": "letzter auftrag aus status",
            }
        )
    if log.strip() and not gemacht:
        letzte_zeilen = [z for z in log.strip().splitlines() if z.strip()][-3:]
        for zeile in letzte_zeilen:
            gemacht.append({"was": maskiere_geheim(zeile), "warum": "aus letztem lauf-log"})
    if not gemacht:
        gemacht.append({"was": "noch kein agent-lauf", "warum": "kein protokoll/log"})
    todos = baue_todos(proto, vorschlag)
    daten = {
        "projekt": name,
        "stand_jetzt": {
            "text": satz,
            "zustand": label,
            "zuletzt": zuletzt,
        },
        "zuletzt_gemacht": gemacht[:6],
        "letzte_aenderungen": git_bericht(ordner) if ordner.is_dir() else {
            "commits": [],
            "uncommittet": [],
            "ahead": 0,
            "behind": 0,
            "upstream": "",
            "branch": "",
            "remote": False,
        },
        "was_muss_gemacht_werden": todos,
        "naechster_schritt": naechster_schritt_text(todos, felder, (eintrag or {}).get("zustand") or ""),
    }
    _BERICHT_CACHE[name] = {"zeit": jetzt, "daten": daten}
    return daten


def agent_bekannt(agent_id):
    sauber = sichere_id(agent_id)
    if not sauber:
        return None
    for agent in lese_lage().get("agenten") or []:
        if agent.get("id") == sauber:
            return agent
    return None


def lese_eingriff():
    if not EINGRIFF.exists():
        return {"befehle": []}
    try:
        return json.loads(EINGRIFF.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"befehle": []}


def baue_dienst_bericht(agent_id):
    agent = agent_bekannt(agent_id)
    if not agent:
        return None
    jetzt = time.monotonic()
    cache = _DIENST_CACHE["daten"].get(agent["id"])
    if cache and (jetzt - _DIENST_CACHE["zeit"]) < _DIENST_TTL:
        return cache
    verlauf = []
    #lage speichert keine historie; eingriff-befehle als kurze spur
    for befehl in lese_eingriff().get("befehle") or []:
        if befehl.get("id") != agent["id"]:
            continue
        verlauf.append(
            {
                "text": maskiere_geheim(f"eingriff: {befehl.get('aktion', '')}"),
                "quelle": "eingriff.json",
            }
        )
    meldung = maskiere_geheim(agent.get("tun") or "")
    if agent.get("wie"):
        meldung = (meldung + " · " + maskiere_geheim(agent.get("wie"))).strip(" ·")
    daten = {
        "id": agent.get("id") or "",
        "name": maskiere_geheim(agent.get("name") or agent.get("id") or ""),
        "status": agent.get("stand") or "leer",
        "seit": maskiere_geheim(agent.get("seit") or agent.get("start") or ""),
        "letzte_meldung": meldung,
        "verlauf": verlauf[-20:],
        "naechstes": maskiere_geheim(agent.get("offen") or "stand halten"),
        "ort": maskiere_geheim(agent.get("ort") or ""),
        "projekt": maskiere_geheim(agent.get("projekt") or ""),
    }
    _DIENST_CACHE["zeit"] = jetzt
    _DIENST_CACHE["daten"][agent["id"]] = daten
    return daten


class Bruecke(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        #kein extra log
        return

    def sende_json(self, daten, code=200):
        roh = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(roh)

    def lokal_post_ok(self):
        #fremde seiten duerfen keine auftraege einreihen
        host = self.headers.get("Host", "")
        if not host_erlaubt(host):
            return False
        origin = self.headers.get("Origin")
        if origin:
            return origin_erlaubt(origin)
        referer = self.headers.get("Referer")
        if referer:
            return origin_erlaubt(referer)
        #gleiche maschine ohne origin (curl/lokal) nur mit erlaubtem host
        return True

    def lies_body(self):
        laenge = int(self.headers.get("Content-Length", "0") or "0")
        if laenge < 0 or laenge > MAX_BODY:
            return None
        if laenge == 0:
            return {}
        return json.loads(self.rfile.read(laenge).decode("utf-8"))

    def do_GET(self):
        pfad = self.path.split("?", 1)[0]
        if ".." in pfad:
            self.send_error(404)
            return
        if pfad == "/bruecke/lage.json":
            self.sende_json(lese_lage())
            return
        if pfad == "/dev/status" or pfad == "/dev/status.json":
            self.sende_json(lese_dev_status())
            return
        if pfad == "/dev/protokoll":
            frage = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            name = (frage.get("projekt") or [""])[0]
            self.sende_json(lese_dev_protokoll(name))
            return
        if pfad == "/dev/log":
            frage = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            name = (frage.get("projekt") or [""])[0]
            self.sende_json(lese_dev_log(name))
            return
        if pfad == "/dev/bericht":
            frage = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            name = (frage.get("projekt") or [""])[0]
            daten = baue_bericht(name)
            if not daten:
                self.sende_json({"fehler": "projekt ungueltig"}, 400)
                return
            self.sende_json(daten)
            return
        if pfad == "/dev/dienst":
            frage = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            did = (frage.get("id") or [""])[0]
            daten = baue_dienst_bericht(did)
            if not daten:
                self.sende_json({"fehler": "dienst ungueltig"}, 400)
                return
            self.sende_json(daten)
            return
        if pfad == "/maske/anordnung":
            self.sende_json(lese_anordnung())
            return
        if pfad.startswith("/zentrale/"):
            frage = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
            if zentrale.handle_get(self, pfad, frage):
                return
            self.sende_json({"fehler": "unbekannt"}, 404)
            return
        if pfad == "/":
            pfad = "/index.html"
        rel = pfad.lstrip("/")
        if ".." in rel or rel.startswith("/") or "\\" in rel:
            self.send_error(404)
            return
        datei = (MASKE / rel).resolve()
        if not datei.is_relative_to(MASKE.resolve()):
            self.send_error(404)
            return
        if not datei.is_file():
            self.send_error(404)
            return
        roh = datei.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ARTEN.get(datei.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(roh)

    def do_POST(self):
        pfad = self.path.split("?", 1)[0]
        if ".." in pfad:
            self.send_error(404)
            return
        if not self.lokal_post_ok():
            self.sende_json({"fehler": "forbidden"}, 403)
            return
        try:
            body = self.lies_body()
        except json.JSONDecodeError:
            self.sende_json({"fehler": "ungueltig"}, 400)
            return
        if body is None:
            self.sende_json({"fehler": "zu gross"}, 400)
            return
        if pfad == "/bruecke/lage":
            agenten = body.get("agenten", [])
            if not isinstance(agenten, list):
                self.sende_json({"fehler": "ungueltig"}, 400)
                return
            schreibe_lage({"agenten": agenten})
            self.sende_json(lese_lage())
            return
        if pfad == "/bruecke/eingriff":
            lage = lese_lage()
            ziel = sichere_id(body.get("id", ""))
            aktion = str(body.get("aktion", "")).strip().lower()
            if not ziel or aktion not in ("anhalten", "weiter"):
                self.sende_json({"fehler": "ungueltig"}, 400)
                return
            befehle = []
            if EINGRIFF.exists():
                befehle = json.loads(EINGRIFF.read_text(encoding="utf-8")).get("befehle", [])
            befehle.append({"id": ziel, "aktion": aktion})
            EINGRIFF.write_text(json.dumps({"befehle": befehle}, ensure_ascii=False, indent=2), encoding="utf-8")
            for agent in lage.get("agenten", []):
                if agent.get("id") == ziel:
                    agent["stand"] = "angehalten" if aktion == "anhalten" else "laeuft"
            schreibe_lage(lage)
            self.sende_json(lage)
            return
        if pfad == "/maske/anordnung":
            if not isinstance(body, dict):
                self.sende_json({"fehler": "ungueltig"}, 400)
                return
            self.sende_json(schreibe_anordnung(body))
            return
        if pfad == "/dev/auftrag":
            projekt = projekt_aus_liste(str(body.get("projekt", "")))
            auftrag = str(body.get("auftrag", "")).strip()
            modus = str(body.get("modus", "vorschlagen")).strip().lower()
            if not projekt:
                self.sende_json({"fehler": "projekt ungueltig"}, 400)
                return
            if not auftrag or len(auftrag) > 2000:
                self.sende_json({"fehler": "auftrag fehlt"}, 400)
                return
            if modus not in ("vorschlagen", "selber"):
                self.sende_json({"fehler": "modus ungueltig"}, 400)
                return
            daten, code = lauf_warteschlange(
                ["einreihen", "--projekt", projekt, "--auftrag", auftrag, "--modus", modus]
            )
            if code == 200:
                tick, _ = lauf_warteschlange(["tick"])
                daten = {"eingereiht": daten, "tick": tick}
            self.sende_json(daten, code)
            return
        if pfad == "/dev/anhalten":
            projekt = projekt_aus_liste(str(body.get("projekt", "")))
            if not projekt or projekt == "alles":
                self.sende_json({"fehler": "projekt ungueltig"}, 400)
                return
            daten, code = lauf_warteschlange(["anhalten", "--projekt", projekt])
            self.sende_json(daten, code)
            return
        if pfad.startswith("/zentrale/"):
            if zentrale.handle_post(self, pfad, body):
                return
            self.sende_json({"fehler": "unbekannt"}, 404)
            return
        self.send_error(404)


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Bruecke).serve_forever()
