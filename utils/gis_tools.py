"""Locate and execute the GIS utilities independently of Cinema 4D's environment."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

TOOLS = ("gdal_translate", "gdalbuildvrt", "gdalwarp", "ogr2ogr")


def bin_directories(root):
    root = Path(root).expanduser()
    yield root
    for suffix in ("bin", "Contents/MacOS/bin", "Contents/MacOS",
                   "Contents/Resources/bin", "Contents/Frameworks/GDAL.framework/Programs",
                   "Contents/Frameworks/GDAL.framework/Versions/Current/Programs"):
        yield root / suffix


def installations(parent):
    try:
        entries = [p for p in Path(parent).expanduser().iterdir()
                   if p.is_dir() and "qgis" in p.name.lower()]
        return sorted(entries, key=lambda p: tuple(map(int, re.findall(r"\d+", p.name))), reverse=True)
    except OSError:
        return []


def candidates(root=None):
    explicit = root or os.environ.get("SWISSTOPO_QGIS_PATH")
    if explicit:
        yield from bin_directories(explicit)
        for folder in installations(explicit):
            yield from bin_directories(folder)
        return
    parents = ([os.environ.get("ProgramFiles", "C:/Program Files")]
               if sys.platform == "win32" else ["/Applications", Path.home() / "Applications"])
    for parent in parents:
        for folder in installations(parent):
            yield from bin_directories(folder)
    found = shutil.which("gdal_translate")
    if found:
        yield Path(found).parent
    if sys.platform == "darwin":
        for folder in ("/opt/homebrew/opt/gdal/bin", "/usr/local/opt/gdal/bin",
                       "/opt/homebrew/bin", "/usr/local/bin",
                       "/Library/Frameworks/GDAL.framework/Programs"):
            yield Path(folder)


def executable(folder, name):
    if not folder:
        return None
    path = Path(folder) / (name + ".exe" if sys.platform == "win32" else name)
    return str(path) if path.is_file() and os.access(path, os.X_OK) else None


def getPathToQGISbin(path_to_QGIS=None):
    folders = list(dict.fromkeys(candidates(path_to_QGIS)))
    for folder in folders:
        if all(executable(folder, tool) for tool in TOOLS):
            return str(folder)
    # Raster-only installs remain usable; the missing tool is reported when needed.
    return next((str(p) for p in folders if executable(p, "gdal_translate")), None)


def gdalBIN_OK(path_to_QGIS_bin, exe="gdal_translate"):
    path = executable(path_to_QGIS_bin, exe)
    if path:
        return path
    raise RuntimeError(f"Outil GIS introuvable ou non exécutable : {exe}\n"
                       f"Dossier détecté : {path_to_QGIS_bin or 'aucun'}\n"
                       "Réinstallez QGIS ou renseignez SWISSTOPO_QGIS_PATH "
                       "avec le chemin de QGIS.app ou du dossier bin.")


def environment(exe):
    env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(key, None)
    folder = Path(exe).parent
    env["PATH"] = os.pathsep.join([str(folder), env.get("PATH", ""),
                                  "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    contents = next((p for p in folder.parents if p.name == "Contents"), None)
    if contents:
        resources = contents / "Resources"
        data_roots = [resources, contents / "MacOS/share"]
        # Do not inherit PROJ/GDAL settings from another installation.
        for key in ("GDAL_DATA", "GDAL_DRIVER_PATH", "PROJ_LIB", "PROJ_DATA"):
            env.pop(key, None)
        for root in data_roots:
            if (root / "gdal").is_dir():
                env.setdefault("GDAL_DATA", str(root / "gdal"))
            if (root / "proj/proj.db").is_file():
                env.setdefault("PROJ_DATA", str(root / "proj"))
                env.setdefault("PROJ_LIB", str(root / "proj"))
    return env


def run(args, check=True):
    args = list(map(str, args))
    try:
        result = subprocess.run(args, env=environment(args[0]), capture_output=True,
                                text=True, errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as error:
        raise RuntimeError(f"Impossible de lancer {args[0]}\n{error}\n"
                           "Vérifiez les droits d’exécution et la compatibilité "
                           "de QGIS avec votre système (notamment Intel / Apple Silicon sur Mac).") from error
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{Path(args[0]).name} a échoué (code {result.returncode}).\n"
                           f"Exécutable : {args[0]}\n{detail[-5000:]}")
    return result
