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


def gdbs2shp(lst_gdbs,path_to_ogr2ogr,xmin,zmin,xmax,zmax)->str:
    #conversion GDB->SHP
    #renvoie le chemin du dossier contenant les dossiers contenant les shapefiles
    for fn_gdb in lst_gdbs:
        pth_shapefile = os.path.join(os.path.dirname(fn_gdb),'shapefiles')
        if not os.path.isdir(pth_shapefile):
            os.mkdir(pth_shapefile)
        dir_shp = os.path.join(pth_shapefile,os.path.basename(fn_gdb[:-4]))
        #on convertit uniquement si le dossier n'existe pas
        if not os.path.isdir(dir_shp):
            os.mkdir(dir_shp)
            req = f'"{path_to_ogr2ogr}" -spat {xmin} {zmin} {xmax} {zmax} "{dir_shp}" "{fn_gdb}"'
            #print(req)
            output = subprocess.check_output(req,shell=True)
    return pth_shapefile


############################################################################################################
#IMPORT SHAPEFILES
############################################################################################################

def listdirectory2(path):
    fichier=[]
    for root, dirs, files in os.walk(path):
        for i in files:
            #print(i)
            if i == 'Building_solid.shp':
                fichier.append(os.path.join(root, i))
    return fichier

def import_swissbuildings3D_v3_shape(fn,doc):
    res = c4d.BaseObject(c4d.Onull)
    #pour le nom on donne le nom du dossier parent
    res.SetName(os.path.basename(os.path.dirname(fn)))
    r = shp.Reader(fn)

    xmin,ymin,xmax,ymax = r.bbox
    centre = c4d.Vector((xmin+xmax)/2,0,(ymax+ymin)/2)

    origin = doc[CONTAINER_ORIGIN]
    if not origin :
        doc[CONTAINER_ORIGIN] = centre
        origin = centre


    # géométries
    shapes = r.shapes()

    nbre = 0
    for shape in shapes:
        xs = [x for x,y in shape.points]
        zs = [y for x,y in shape.points]
        ys = [z for z in shape.z]

        #pour l'axe on prend la moyenne de x et z et le min de y auquel on ajoute 3m
        #car les bati swisstopo rajoute 3m sous le point le plus bas du MNT
        #comme ça on peut modifier l'échelle des hauteurs
        axe = c4d.Vector((min(xs)+max(xs))/2,min(ys)+3,(min(zs)+max(zs))/2)

        pts = [c4d.Vector(x,z,y)-axe for (x,y),z in zip(shape.points,shape.z)]

        nb_pts = len(pts)
        polys = []

        pred = 0
        for i in shape.parts:
            if pred:
                nb_pts_poly = i-pred

            poly = c4d.CPolygon(i,i+1,i+2,i+3)
            polys.append(poly)
            pred = i


        po =c4d.PolygonObject(nb_pts,len(polys))
        #TODO : tag phong !
        po.SetAllPoints(pts)
        for i,poly in enumerate(polys):
            po.SetPolygon(i,poly)

        po.SetAbsPos(axe-origin)
        po.Message(c4d.MSG_UPDATE)
        po.InsertUnderLast(res)
    return res

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

############################################################################################################
#FERMETURE DES TROUS
############################################################################################################
def selectContour(op):
    res = False

    nb = c4d.utils.Neighbor()
    nb.Init(op)
    bs = op.GetSelectedEdges(nb,c4d.EDGESELECTIONTYPE_SELECTION)
    bs.DeselectAll()
    for i,poly in enumerate(op.GetAllPolygons()):
        inf = nb.GetPolyInfo(i)
        if nb.GetNeighbor(poly.a, poly.b, i)==-1:
            bs.Select(inf['edge'][0])

        if nb.GetNeighbor(poly.b, poly.c, i)==-1:
            bs.Select(inf['edge'][1])


        #si pas triangle
        if not poly.c == poly.d :
            if nb.GetNeighbor(poly.c, poly.d, i)==-1:
                bs.Select(inf['edge'][2])
                res = True
        if nb.GetNeighbor(poly.d, poly.a, i)==-1:
            bs.Select(inf['edge'][3])
            res = True

    op.SetSelectedEdges(nb,bs,c4d.EDGESELECTIONTYPE_SELECTION)
    return res

def closePolys(op,doc):
    doc.SetMode(c4d.Medges)
    nbr = c4d.utils.Neighbor()
    nbr.Init(op)
    vcnt = op.GetPolygonCount()
    settings = c4d.BaseContainer()
    settings[c4d.MDATA_CLOSEHOLE_INDEX] = op
    doc.AddUndo(c4d.UNDO_CHANGE,op)

    for i in range(0,vcnt):
        vadr = op.GetPolygon(i)
        pinf = nbr.GetPolyInfo(i)
        if nbr.GetNeighbor(vadr.a, vadr.b, i) == c4d.NOTOK:
            settings[c4d.MDATA_CLOSEHOLE_EDGE] = pinf["edge"][0]
            c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_CLOSEHOLE_TOOL, list = [op], mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION, bc = settings, doc = doc)
            nbr.Init(op)
        if nbr.GetNeighbor(vadr.b, vadr.c, i) == c4d.NOTOK:
            settings[c4d.MDATA_CLOSEHOLE_EDGE] = pinf["edge"][1]
            c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_CLOSEHOLE_TOOL, list = [op], mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION, bc = settings, doc = doc)
            nbr.Init(op)
        if vadr.c != vadr.d and nbr.GetNeighbor(vadr.c, vadr.d, i) == c4d.NOTOK:
            settings[c4d.MDATA_CLOSEHOLE_EDGE] = pinf["edge"][2]
            c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_CLOSEHOLE_TOOL, list = [op], mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION, bc = settings, doc = doc)
            nbr.Init(op)
        if nbr.GetNeighbor(vadr.d, vadr.a, i) == c4d.NOTOK:
            settings[c4d.MDATA_CLOSEHOLE_EDGE] = pinf["edge"][3]
            c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_CLOSEHOLE_TOOL, list = [op], mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION, bc = settings, doc = doc)
            nbr.Init(op)


def triangulate(lst_objs,doc):
    doc.SetMode(c4d.Mpolygons)
    settings = c4d.BaseContainer()  # Settings
    res = c4d.utils.SendModelingCommand(command=c4d.MCOMMAND_TRIANGULATE,
                                    list=lst_objs,
                                    mode=c4d.MODELINGCOMMANDMODE_ALL,
                                    bc=settings,
                                    doc=doc)

def untriangulate(lst_objs,doc):
    doc.SetMode(c4d.Mpolygons)
    settings = c4d.BaseContainer()  # Settings
    settings[c4d.MDATA_UNTRIANGULATE_NGONS] = True
    settings[c4d.MDATA_UNTRIANGULATE_ANGLE_RAD] = c4d.utils.Rad(0.1)

    res = c4d.utils.SendModelingCommand(command=c4d.MCOMMAND_UNTRIANGULATE,
                                    list=lst_objs,
                                    mode=c4d.MODELINGCOMMANDMODE_ALL,
                                    bc=settings,
                                    doc=doc)


def importSwissBuildings(path, doc, cube_mnt):
    #emprise objet
    origine = doc[CONTAINER_ORIGIN]
    xmin,zmin,xmax,zmax = empriseObject(cube_mnt, origine)

    #nouveau doc pour Polygonize
    doc = c4d.documents.BaseDocument()
    #document en mètre
    usdata = doc[c4d.DOCUMENT_DOCUNIT]
    scale, unit = usdata.GetUnitScale()
    if  unit!= c4d.DOCUMENT_UNIT_M:
        #rep = c4d.gui.QuestionDialog(DOC_NOT_IN_METERS_TXT)
        #if not rep : return
        unit = c4d.DOCUMENT_UNIT_M
        usdata.SetUnitScale(scale, unit)
        doc[c4d.DOCUMENT_DOCUNIT] = usdata
    #doc = c4d.documents.LoadDocument('temp', c4d.SCENEFILTER_NONE, thread=None)

    doc[CONTAINER_ORIGIN] = origine

    ##################################################################
    #OGR2OGR transformation des gdb en shp
    #TODO : inclure dans un Thread avec toutes les opérations GDAL/OGR
    ##################################################################

    #chemin pour ogr2ogr
    path_to_QGISbin = getPathToQGISbin()
    if not path_to_QGISbin:
        c4d.gui.MessageDialog("QGIS n'est pas installé ou le chemin n'est pas le bon")
        return True

    #on vérifie que ogr2ogr est bien là
    path_to_ogr2ogr = ogrBIN_OK(path_to_QGISbin)
    if not path_to_QGISbin:
        c4d.gui.MessageDialog("Il semble qu'il manque ogr2ogr dans le dossier de QGIS")
        return True

    lst_gdbs = get_swissbuildings3D_v3_gdbs(path)

    #TODO si on n'a pas de gdb ???'
    #print(lst_gdbs)
    path_shapefiles = gdbs2shp(lst_gdbs,path_to_ogr2ogr,xmin,zmin,xmax,zmax)


    ###########################################################
    #Import shapefiles
    ###############################################

    onull_bat = c4d.BaseObject(c4d.Onull)
    onull_bat.SetName(NAME_SWISSBUILDINGS3D_V3)

    for fn in listdirectory2(path_shapefiles):
        res = import_swissbuildings3D_v3_shape(fn,doc)
        res.InsertUnderLast(onull_bat)
    doc.InsertObject(onull_bat)


    #OPTIMISATION, fermeture des trous, et mise en rouge si pas ok

    for onull in onull_bat.GetChildren():

        #OPTIMIZE POINTS
        settings = c4d.BaseContainer()  # Settings
        settings[c4d.MDATA_OPTIMIZE_TOLERANCE] = 0.1
        settings[c4d.MDATA_OPTIMIZE_POINTS] = True
        settings[c4d.MDATA_OPTIMIZE_POLYGONS] = True
        settings[c4d.MDATA_OPTIMIZE_UNUSEDPOINTS] = True



        res = c4d.utils.SendModelingCommand(command=c4d.MCOMMAND_OPTIMIZE,
                                        list=[o for o in onull.GetChildren()],
                                        mode=c4d.MODELINGCOMMANDMODE_POLYGONSELECTION,
                                        bc=settings,
                                        doc=doc)

        for o in onull.GetChildren():
            #on ferme d'abord les polygones'
            closePolys(o,doc)
            #si on a encore des edges contour on met l'objet en rouge
            if selectContour(o):
                o[c4d.ID_BASEOBJECT_USECOLOR] = c4d.ID_BASEOBJECT_USECOLOR_ALWAYS
                o[c4d.ID_BASEOBJECT_COLOR] = c4d.Vector(1,0,0)
                #icone
                o[c4d.ID_BASELIST_ICON_COLORIZE_MODE] =c4d.ID_BASELIST_ICON_COLORIZE_MODE_CUSTOM
                o[c4d.ID_BASELIST_ICON_COLOR]= c4d.Vector(1,0,0)
                #on le met en haut de la hierarchie
                o.InsertUnder(onull)
            else:
                o[c4d.ID_BASEOBJECT_USECOLOR] = c4d.ID_BASEOBJECT_USECOLOR_OFF
                o[c4d.ID_BASELIST_ICON_COLORIZE_MODE] =c4d.ID_BASELIST_ICON_COLORIZE_MODE_NONE

    ##################################
    #DECOUPAGE BOOLEEN
    ##################################
    boole = c4d.BaseObject(c4d.Oboole)
    boole.SetName(NAME_SWISSBUILDINGS3D_V3)
    boole[c4d.BOOLEOBJECT_HIGHQUALITY] = False
    boole[c4d.BOOLEOBJECT_TYPE] = c4d.BOOLEOBJECT_TYPE_INTERSECT

    cube_mnt.InsertUnder(boole)

    onull_bat.InsertUnder(boole)

    doc.InsertObject(boole)

    doc_poly = doc.Polygonize()
    
    parent_bat = doc_poly.GetFirstObject().GetDown()
    ###############
    #Fermeture des trous

    for ssobj in parent_bat.GetChildren():
        for o in ssobj.GetChildren():
            closePolys(o,doc)
    
            
    lst_polyobjs = getPolygonObjects(parent_bat,lst = [], stop = parent_bat)
    #print(len(lst_polyobjs))
    triangulate(lst_polyobjs,doc_poly)
    untriangulate(lst_polyobjs,doc_poly)
    res = parent_bat.GetClone()
    c4d.documents.KillDocument(doc)
    c4d.documents.KillDocument(doc_poly)
    
    return res
    

def getPolygonObjects(obj,lst = [], stop = None):
    while obj:
        if obj.CheckType(c4d.Opolygon):
            lst.append(obj)
        lst = getPolygonObjects(obj.GetDown(),lst = lst, stop = stop)
        if obj == stop : return lst
        obj = obj.GetNext()
    return lst


def main() -> None:

    cube_mnt = op.GetClone()

    #emprise objet
    origine = doc[CONTAINER_ORIGIN]
    xmin,zmin,xmax,zmax = empriseObject(cube_mnt, origine)

    path = "/Users/olivierdonze/Documents/TEMP/test_meyrin/swisstopo"

    bats = importSwissBuildings(path, doc, cube_mnt)
    doc.InsertObject(bats)
    doc.AddUndo(c4d.UNDOTYPE_NEW,bats)
    
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