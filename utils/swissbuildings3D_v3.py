from pathlib import Path
import tempfile
from typing import Optional
import c4d
import os
from glob import glob
import sys
import subprocess
import shapefile as shp

doc: c4d.documents.BaseDocument  # The active document
op: Optional[c4d.BaseObject]  # The active object, None if unselected

CONTAINER_ORIGIN = 1026473

NAME_SWISSBUILDINGS3D_V3 = 'swissbuildings3d_v3'

def getPathToQGISbin(path_to_QGIS = None):
    #Si le path_to_QGIS n'est pas renseigné on prend le chemin par défaut selon la plateforme
    win = sys.platform == 'win32'
    if not path_to_QGIS:
        if sys.platform == 'win32':
            path_to_QGIS = 'C:\\Program Files'
        else:
            path_to_QGIS = '/Applications'
    for folder_name in os.listdir(path_to_QGIS):
        if 'QGIS'  in folder_name:
            if win :
                path = os.path.join(path_to_QGIS,folder_name,'bin')
            else:

                path = os.path.join(path_to_QGIS,folder_name,'Contents/MacOS/bin')

            if os.path.isdir(path):
                # on vérifie qu'il y ait bien gdal_translate
                #TODO vérifier les autres
                if win :
                    if os.path.isfile(os.path.join(path,'gdal_translate.exe')):
                        return path
                else:
                    if os.path.isfile(os.path.join(path,'gdal_translate')):
                        return path
    return None

def ogrBIN_OK(path_to_QGIS_bin, exe = 'ogr2ogr'):
    if sys.platform == 'win32':
        exe+='.exe'
    path = os.path.join(path_to_QGIS_bin,exe)
    if os.path.isfile(path):
        return path
    else:
        return False

def get_swissbuildings3D_v3_gdbs(path):
    """renvoie une liste de fichier dxf contenus dans
       un sous-dossier qui contient le mot swissbuildings3d"""
    lst_gdb = None

    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs:
            #print(name)
            if name == NAME_SWISSBUILDINGS3D_V3 :
                lst_gdb = [fn_dxf for fn_dxf in glob(os.path.join(root, name,'*.gdb'))]
    return lst_gdb


SURFACES = (("Floor", "sols"), ("Wall", "facades"), ("Roof", "toits"))


def shape_directories(databases, ogr, bounds):
    """Cache the spatially filtered conversion for precisely this extent."""
    layers = ["Building_solid"] + [name for name, _ in SURFACES]
    for database in sorted(databases or []):
        parent = Path(database).parent / "shapefiles" / Path(database).stem
        parent.mkdir(parents=True, exist_ok=True)
        extent = "_".join(map(str, bounds))
        directory = parent / extent
        if not directory.is_dir():
            with tempfile.TemporaryDirectory(dir=parent) as staging:
                output = Path(staging) / "shapes"
                subprocess.run([ogr, "-f", "ESRI Shapefile", "-spat", *map(str, bounds),
                                str(output), database, *layers], check=True)
                for layer in layers:
                    if not (output / (layer + ".shp")).is_file():
                        raise ValueError(f"Couche absente de la conversion : {layer}")
                os.rename(output, directory)
        yield directory


def patch_faces(shape):
    ends = list(shape.parts[1:]) + [len(shape.points)]
    if shape.shapeType == shp.POLYGONZ:
        # OGR may encode triangulated surface patches as closed PolygonZ rings.
        # Unlike MultiPatch records, PolygonZ records have no part-type array.
        for start, end in zip(shape.parts, ends):
            if shape.points[start] == shape.points[end-1] and shape.z[start] == shape.z[end-1]:
                end -= 1
            if end - start != 3:
                raise ValueError("Une face PolygonZ non triangulée a été rencontrée.")
            yield start, start+1, start+2
        return
    if shape.shapeType != shp.MULTIPATCH:
        raise ValueError(f"Type de géométrie 3D non pris en charge : {shape.shapeType}")
    for start, end, kind in zip(shape.parts, ends, shape.partTypes):
        if kind == shp.TRIANGLE_STRIP:
            for i in range(start, end-2):
                yield (i+1, i, i+2) if (i-start) % 2 else (i, i+1, i+2)
        elif kind == shp.TRIANGLE_FAN:
            for i in range(start+1, end-1):
                yield start, i, i+1
        else:
            if shape.points[start] == shape.points[end-1] and shape.z[start] == shape.z[end-1]:
                end -= 1
            if kind in (shp.INNER_RING, shp.RING) or end-start > 4:
                raise ValueError("MultiPatch non triangulé dans les données swissBUILDINGS3D.")
            if end-start >= 3:
                yield tuple(range(start, end))


class Mesh:
    def __init__(self):
        self.vertices = []
        self.indices = {}
        self.faces = []
        self.selections = {}

    def add(self, vertices, label=None):
        indices = []
        for point in vertices:
            key = (point.x, point.y, point.z)
            index = self.indices.get(key)
            if index is None:
                index = len(self.vertices)
                self.indices[key] = index
                self.vertices.append(point)
            indices.append(index)
        if len(set(indices)) < 3:
            return
        if label is not None:
            self.selections.setdefault(label, []).append(len(self.faces))
        self.faces.append(c4d.CPolygon(*indices))

    def read(self, filename, origin, label=None):
        with shp.Reader(str(filename)) as reader:
            for shape in reader.iterShapes():
                if not shape.points:
                    continue
                vertices = [c4d.Vector(x, h, y) - origin
                            for (x, y), h in zip(shape.points, shape.z)]
                for face in patch_faces(shape):
                    self.add((vertices[i] for i in face), label)

    def object(self, name, labels=()):
        result = c4d.PolygonObject(len(self.vertices), len(self.faces))
        result.SetName(name)
        result.SetAllPoints(self.vertices)
        for i, face in enumerate(self.faces):
            result.SetPolygon(i, face)
        for label in labels:
            tag = result.MakeTag(c4d.Tpolygonselection)
            tag.SetName(label)
            selection = tag.GetBaseSelect()
            for i in self.selections.get(label, ()):
                selection.Select(i)
        result.Message(c4d.MSG_UPDATE)
        return result


def clip_mesh(source, volume, labels):
    """Keep source selections on clipped faces. Only the solid gets cut caps."""
    if not source.GetPolygonCount():
        return source
    temp = c4d.documents.BaseDocument()
    boolean = c4d.BaseObject(c4d.Oboole)
    boolean[c4d.BOOLEOBJECT_TYPE] = c4d.BOOLEOBJECT_TYPE_INTERSECT
    boolean[c4d.BOOLEOBJECT_HIGHQUALITY] = False
    source.InsertUnder(boolean)
    volume.GetClone().InsertUnderLast(boolean)
    temp.InsertObject(boolean)
    evaluated = temp.Polygonize()
    if evaluated is None:
        raise RuntimeError("Impossible de découper les bâtiments v3.")
    mesh = Mesh()
    stack = [evaluated.GetFirstObject()]
    while stack:
        obj = stack.pop()
        if obj is None:
            continue
        stack.extend(reversed(obj.GetChildren()))
        if not isinstance(obj, c4d.PolygonObject):
            continue
        groups = {t.GetName(): t.GetBaseSelect() for t in obj.GetTags()
                  if t.CheckType(c4d.Tpolygonselection) and t.GetName() in labels}
        vertices = [obj.GetMg() * p for p in obj.GetAllPoints()]
        for i, face in enumerate(obj.GetAllPolygons()):
            label = next((key for key, sel in groups.items() if sel.IsSelected(i)), None)
            if labels and label is None:
                continue
            ids = (face.a, face.b, face.c) if face.c == face.d else (face.a, face.b, face.c, face.d)
            mesh.add((vertices[k] for k in ids), label)
    return mesh.object(source.GetName(), labels)


def importSwissBuildings(path, doc, cube_mnt, xmin, zmin, xmax, zmax):
    qgis = getPathToQGISbin()
    ogr = ogrBIN_OK(qgis) if qgis else None
    if not ogr:
        raise RuntimeError("L’outil ogr2ogr est introuvable dans le dossier de QGIS.")
    databases = get_swissbuildings3D_v3_gdbs(path)
    if not databases:
        raise ValueError("Aucune géodatabase SwissBuildings3D à convertir.")
    solid, surfaces = Mesh(), Mesh()
    origin = doc[CONTAINER_ORIGIN]
    bounds = (xmin, zmin, xmax, zmax)
    for directory in shape_directories(databases, ogr, bounds):
        solid.read(directory / "Building_solid.shp", origin)
        for layer, label in SURFACES:
            surfaces.read(directory / (layer + ".shp"), origin, label)
    labels = [label for _, label in SURFACES]
    visible = clip_mesh(surfaces.object(NAME_SWISSBUILDINGS3D_V3, labels), cube_mnt, labels)
    hidden = clip_mesh(solid.object(NAME_SWISSBUILDINGS3D_V3 + "_solid"), cube_mnt, ())
    hidden[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
    hidden[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF
    return visible, hidden


def empriseObject(obj, origine):
    geom = obj
    if not geom.CheckType(c4d.Opoint):
        geom = geom.GetCache()
        if not geom.CheckType(c4d.Opoint) : return None
    mg = obj.GetMg()
    pts = [p*mg+origine for p in geom.GetAllPoints()]
    lst_x = [p.x for p in pts]
    lst_y = [p.y for p in pts]
    lst_z = [p.z for p in pts]

    xmin = min(lst_x)
    xmax = max(lst_x)
    ymin = min(lst_y)
    ymax = max(lst_y)
    zmin = min(lst_z)
    zmax = max(lst_z)

    mini = c4d.Vector(xmin,ymin,zmin)
    maxi = c4d.Vector(xmax,ymax,zmax)

    return xmin,zmin,xmax,zmax

def main() -> None:

    doc = c4d.documents.GetActiveDocument()
    op = doc.GetActiveObject()
    if not op:
        return
    cube_mnt = op.GetClone()

    #emprise objet
    origine = doc[CONTAINER_ORIGIN]
    xmin,zmin,xmax,zmax = empriseObject(cube_mnt, origine)

    path = c4d.storage.LoadDialog(flags=c4d.FILESELECT_DIRECTORY, title="Dossier SwissBuildings3D")
    if not path:
        return

    bats = importSwissBuildings(path, doc, cube_mnt, xmin, zmin, xmax, zmax)
    if not bats:
        return
    doc.StartUndo()
    try:
        for obj in bats:
            doc.InsertObject(obj)
            doc.AddUndo(c4d.UNDOTYPE_NEW, obj)
    finally:
        doc.EndUndo()
    

    c4d.EventAdd()
    return

"""
def state():
    # Defines the state of the command in a menu. Similar to CommandData.GetState.
    return c4d.CMD_ENABLED
"""

if __name__ == '__main__':
    main()