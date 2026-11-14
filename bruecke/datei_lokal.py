#waehlt die lokale datei, wenn sie neben dem beispiel liegt
from pathlib import Path


def aktiv(pfad):
    #liste.yaml -> liste.lokal.yaml, sonst das beispiel
    pfad = Path(pfad)
    lokal = pfad.with_name(pfad.stem + ".lokal" + pfad.suffix)
    if lokal.is_file():
        return lokal
    return pfad
