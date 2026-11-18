import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import c4d

ID_ORTHO = 1058393
ID_CN10 = 1058394
ID_CN25 = 1058396
ID_CN50 = 1058397

LYR_ORTHO = 'ch.swisstopo.images-swissimage'
LYR_CN10 =  'ch.swisstopo.landeskarte-farbe-10'
LYR_CN25 = 'ch.swisstopo.pixelkarte-farbe-pk25.noscale'
LYR_CN50 =  'ch.swisstopo.pixelkarte-farbe-pk50.noscale'


CONTAINER_ORIGIN =1026473

NOT_SAVED_TXT = "Le document doit être enregistré pour pouvoir copier les textures dans le dossier tex, vous pourrez le faire à la prochaine étape\nVoulez-vous continuer ?"
DOC_NOT_IN_METERS_TXT = "Les unités du document ne sont pas en mètres, si vous continuez les unités seront modifiées.\nVoulez-vous continuer ?"


O_DEFAUT = c4d.Vector(2500000.00,0.0,1120000.00)


LAYERS = {
    ID_ORTHO: ("Orthophoto", LYR_ORTHO),
    ID_CN10: ("Carte nationale 1:10 000", LYR_CN10),
    ID_CN25: ("Carte nationale 1:25 000", LYR_CN25),
    ID_CN50: ("Carte nationale 1:50 000", LYR_CN50),
}

executor = ThreadPoolExecutor(max_workers=1)
generated = set()
target = None
layer_id = 0
pending = None
last_view = None
settled_at = 0
requested = None


def selected(doc, bd):
    return layer_id if target and target[0].IsAlive() and target[1].IsAlive() and target == (doc, bd) else 0


TRANSPARENCY = 1801
TRANSPARENCY_FIELD = 1802
TRANSPARENCY_CONTROLS = (TRANSPARENCY, TRANSPARENCY_FIELD)


def add_transparency(dialog, align=c4d.BFH_RIGHT):
    dialog.GroupBegin(0, align, cols=3, rows=1)
    dialog.AddStaticText(0, c4d.BFH_LEFT, name="Transparence (%)")
    dialog.AddEditNumber(TRANSPARENCY_FIELD, c4d.BFH_LEFT, initw=30)
    dialog.AddSlider(TRANSPARENCY, c4d.BFH_LEFT, initw=240)
    dialog.GroupEnd()
    for control in TRANSPARENCY_CONTROLS:
        dialog.SetInt32(control, 0, 0, 100, 1)


def refresh_transparency(dialog, doc, bd):
    top = bd.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] == c4d.Ptop
    value = round(100 * bd[c4d.BASEDRAW_DATA_PICTURE_TRANSPARENCY]) if top else None
    for control in TRANSPARENCY_CONTROLS:
        dialog.Enable(control, top)
        if top and dialog.GetInt32(control) != value:
            dialog.SetInt32(control, value, 0, 100, 1)


def redraw_background(bd):
    bd.SetDirty(c4d.DIRTYFLAGS_DATA)
    bd.Message(c4d.MSG_UPDATE)
    c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_FORCEFULLREDRAW |
                  c4d.DRAWFLAGS_NO_THREAD | c4d.DRAWFLAGS_NO_ANIMATION)


def change_transparency(dialog, control):
    doc = c4d.documents.GetActiveDocument()
    bd = doc.GetActiveBaseDraw()
    if bd.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] == c4d.Ptop:
        bd[c4d.BASEDRAW_DATA_PICTURE_TRANSPARENCY] = dialog.GetInt32(control) / 100.0
        refresh_transparency(dialog, doc, bd)
        redraw_background(bd)


def toggle(layer):
    global target, layer_id, last_view, requested
    doc = c4d.documents.GetActiveDocument()
    bd = doc.GetActiveBaseDraw()
    if selected(doc, bd) != layer:
        return select(layer)
    target, layer_id = None, 0
    last_view = requested = None
    bd[c4d.BASEDRAW_DATA_SHOWPICTURE] = False
    redraw_background(bd)
    return True


def select(layer):
    global target, layer_id, last_view, requested
    doc = c4d.documents.GetActiveDocument()
    bd = doc.GetActiveBaseDraw()
    if bd.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] != c4d.Ptop:
        c4d.gui.MessageDialog("Activez une vue de haut pour afficher un fond swisstopo.")
        return False
    units = doc[c4d.DOCUMENT_DOCUNIT]
    scale, unit = units.GetUnitScale()
    if unit != c4d.DOCUMENT_UNIT_M:
        if not c4d.gui.QuestionDialog(DOC_NOT_IN_METERS_TXT):
            return False
        units.SetUnitScale(scale, c4d.DOCUMENT_UNIT_M)
        doc[c4d.DOCUMENT_DOCUNIT] = units
    if not doc.GetDocumentPath():
        if not c4d.gui.QuestionDialog(NOT_SAVED_TXT):
            return False
        c4d.CallCommand(12098)
        if not doc.GetDocumentPath():
            return False
    if doc[CONTAINER_ORIGIN] is None:
        doc[CONTAINER_ORIGIN] = O_DEFAUT
        c4d.EventAdd()
    target, layer_id = (doc, bd), layer
    last_view = requested = None
    return True


def fetch(key):
    layer, folder, bbox, width, height, origin = key
    service = layer if isinstance(layer, str) else LAYERS[layer][1]
    bounds = ",".join(map(str, bbox))
    url = (f"https://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
           f"&LAYERS={service}&STYLES=default&CRS=EPSG:2056&BBOX={bounds}"
           f"&WIDTH={width}&HEIGHT={height}&FORMAT=image/png")
    with urllib.request.urlopen(url, timeout=30) as response:
        image = response.read()
    if not image.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise ValueError("Le service WMS n’a pas renvoyé une image PNG.")
    return image


def tick():
    global pending, last_view, settled_at, requested
    doc = c4d.documents.GetActiveDocument()
    bd = doc.GetActiveBaseDraw()
    key = None
    if selected(doc, bd) and bd.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] == c4d.Ptop:
        origin = doc[CONTAINER_ORIGIN]
        frame = bd.GetFrame()
        w, h = frame["cr"] - frame["cl"], frame["cb"] - frame["ct"]
        if origin is not None and doc.GetDocumentPath() and w > 0 and h > 0:
            lo = bd.SW(c4d.Vector(0,h,0)) + origin
            hi = bd.SW(c4d.Vector(w,0,0)) + origin
            key = (layer_id, doc.GetDocumentPath(), (lo.x,lo.z,hi.x,hi.z), w,h,(origin.x,origin.z))
    if key != last_view:
        last_view, settled_at = key, time.monotonic()
    if pending and pending[0].done():
        job, job_key, job_target = pending
        pending = None
        if key == job_key and target is job_target:
            try:
                apply_image(bd, key, job.result())
            except (OSError, ValueError) as error:
                c4d.gui.MessageDialog(f"Image swisstopo indisponible : {error}")
        elif requested == job_key:
            requested = None
    if key and requested != key and pending is None and time.monotonic() - settled_at >= 0.45:
        requested = key
        pending = executor.submit(fetch, key), key, target


def apply_image(bd, key, image):
    _, path, (xmin,zmin,xmax,zmax), _, _, (ox,oz) = key
    folder = os.path.join(path, "tex", "__back_image")
    os.makedirs(folder, exist_ok=True)
    name = "swisstopo_" + uuid4().hex + ".png"
    filename = os.path.join(folder, name)
    with open(filename, "xb") as output:
        output.write(image)
    old = os.path.join(folder, bd[c4d.BASEDRAW_DATA_PICTURE] or "")
    # The viewport can still hold the previous bitmap's aspect ratio while
    # loading its replacement. The WMS bounds define both axes explicitly.
    bd[c4d.BASEDRAW_DATA_KEEP_ASPECT] = False
    bd[c4d.BASEDRAW_DATA_PICTURE] = name
    bd[c4d.BASEDRAW_DATA_SIZEX] = xmax - xmin
    bd[c4d.BASEDRAW_DATA_SIZEY] = zmax - zmin
    bd[c4d.BASEDRAW_DATA_OFFSETX] = (xmin + xmax)/2 - ox
    bd[c4d.BASEDRAW_DATA_OFFSETY] = (zmin + zmax)/2 - oz
    bd[c4d.BASEDRAW_DATA_SHOWPICTURE] = True
    generated.add(filename)
    if old in generated:
        try:
            os.remove(old)
        except OSError:
            pass
        generated.discard(old)
    redraw_background(bd)
