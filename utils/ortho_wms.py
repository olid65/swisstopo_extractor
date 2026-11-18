"""SWISSIMAGE texture grid and WMS GetMap request (LV95, square pixels)."""
import hashlib
import math
from pathlib import Path
from urllib.parse import urlencode

MAX_SIDE = 10000
MIN_CM = 10


def grid(bounds, requested_cm, min_cm=MIN_CM):
    west, south, east, north = bounds
    dx, dy = east-west, north-south
    if dx <= 0 or dy <= 0:
        raise ValueError("L’emprise doit avoir une largeur et une hauteur positives.")
    cm = max(min_cm, requested_cm, math.ceil(max(dx, dy) * 100 / MAX_SIDE))
    step = cm / 100
    width = max(1, min(MAX_SIDE, math.ceil(round(dx / step, 8))))
    height = max(1, min(MAX_SIDE, math.ceil(round(dy / step, 8))))
    return cm, width, height


def prepare(folder, bounds, requested_cm):
    cm, width, height = grid(bounds, requested_cm)
    west, _, _, north = bounds
    bbox = (west, north-height*cm/100, west+width*cm/100, north)
    directory = Path(folder) / "orthophoto_wms"
    directory.mkdir(parents=True, exist_ok=True)
    name = f"swissimage_{cm}cm_{round(west)}_{round(north)}_{width}x{height}"
    if west != round(west) or north != round(north):
        # Distinguish nearby extractions with identical rounded names.
        key = f"{float(west).hex()}_{float(north).hex()}".encode("ascii")
        name += "_" + hashlib.sha256(key).hexdigest()[:10]
    file = directory / (name + ".tif")
    params = dict(SERVICE="WMS", VERSION="1.3.0", REQUEST="GetMap",
                  LAYERS="ch.swisstopo.images-swissimage", STYLES="",
                  CRS="EPSG:2056", FORMAT="image/tiff", WIDTH=width, HEIGHT=height,
                  BBOX=",".join(map(str, bbox)))
    return "https://wms.geo.admin.ch/?" + urlencode(params), str(file)
