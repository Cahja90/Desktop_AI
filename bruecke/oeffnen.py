#startet den server, wenn er fehlt, und oeffnet die maske
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 17341
ADRESSE = "http://%s:%s" % (HOST, PORT)
SERVER = WURZEL / "bruecke" / "server.py"


def maske_laeuft():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        return sock.connect_ex((HOST, PORT)) == 0
    finally:
        sock.close()


def server_starten():
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=str(WURZEL),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return
    subprocess.Popen(
        [sys.executable, str(SERVER)],
        cwd=str(WURZEL),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def warten():
    for _ in range(25):
        if maske_laeuft():
            return True
        time.sleep(0.2)
    return False


def seite_da():
    try:
        with urllib.request.urlopen(ADRESSE + "/", timeout=2) as antwort:
            return antwort.status == 200
    except OSError:
        return False


def main():
    if not maske_laeuft():
        server_starten()
        if not warten():
            print("maske nicht erreichbar")
            return 1
    if not seite_da():
        print("maske antwortet nicht")
        return 1
    webbrowser.open(ADRESSE)
    print(ADRESSE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
