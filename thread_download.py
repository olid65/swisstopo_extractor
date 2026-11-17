"""Téléchargement et publication des jeux de données dans le dossier de la maquette."""
import json
from pathlib import Path
import os
import shutil
import tempfile
import urllib.request
from zipfile import ZipFile

import c4d


def download(url, destination, on_extract=None):
    target = Path(destination)
    # Le cache ne doit jamais contenir un téléchargement ou une extraction partielle.
    with tempfile.TemporaryDirectory(dir=target.parent) as staging:
        payload = Path(staging) / "download"
        with urllib.request.urlopen(url, timeout=60) as response, payload.open("wb") as output:
            shutil.copyfileobj(response, output)
            length = response.headers.get("Content-Length")
            if length is not None and output.tell() != int(length):
                raise ValueError("Téléchargement incomplet.")
            if not output.tell():
                raise ValueError("Fichier vide.")

        if url.startswith("https://wms.geo.admin.ch/") and target.suffix.lower() == ".tif":
            with payload.open("rb") as stream:
                if stream.read(4) not in (b"II*\x00", b"MM\x00*"):
                    raise ValueError("Le service WMS n’a pas renvoyé une orthophoto TIFF.")

        if target.suffix.lower() == ".geojson":
            with payload.open(encoding="utf-8-sig") as stream:
                data = json.load(stream)
            if not isinstance(data, dict) or not isinstance(data.get("features"), list):
                raise ValueError("La réponse ne contient aucune collection GeoJSON.")
        if target.suffix.lower() != ".zip":
            os.replace(payload, target)
            return

        target = target.with_suffix("")
        if on_extract is not None:
            on_extract()
        with ZipFile(payload) as archive:
            files = [info for info in archive.infolist() if not info.is_dir()]
            if target.suffix.lower() != ".gdb":
                matches = [info for info in files if Path(info.filename).suffix.lower() == target.suffix.lower()]
                if len(matches) != 1:
                    raise ValueError(f"Archive ambiguë ou sans fichier {target.suffix}.")
                extracted = Path(staging) / "extracted"
                with archive.open(matches[0]) as src, extracted.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                # La géodatabase est un répertoire à publier en une seule opération.
                extracted = Path(staging) / "database"
                extracted.mkdir()
                roots = set()
                for info in files:
                    parts = Path(info.filename).parts
                    indexes = [i for i, part in enumerate(parts) if part.lower().endswith(".gdb")]
                    if not indexes:
                        continue
                    index = indexes[0]
                    roots.add(parts[:index + 1])
                    output = extracted.joinpath(*parts[index + 1:]).resolve()
                    if not output.is_relative_to(extracted.resolve()) or output == extracted.resolve():
                        raise ValueError("Chemin invalide dans la géodatabase.")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, output.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                if len(roots) != 1:
                    raise ValueError("Une seule géodatabase est attendue dans cette archive.")
        os.replace(extracted, target)


class ThreadDownload(c4d.threading.C4DThread):
    def __init__(self, jobs):
        self.jobs = tuple(jobs)
        self.progress = (1, self.jobs[0][1], "Téléchargement") if self.jobs else None
        self.completed = 0
        self.errors = []

    def Main(self):
        for index, (url, destination) in enumerate(self.jobs, start=1):
            # Un seul instantané pour que le compteur et le libellé restent synchronisés.
            self.progress = (index, destination, "Téléchargement")

            def extracting():
                self.progress = (index, destination, "Décompression")

            try:
                download(url, destination, on_extract=extracting)
            except Exception as error:
                self.errors.append((destination, f"{Path(destination).name} — {error}"))
            else:
                self.completed += 1
