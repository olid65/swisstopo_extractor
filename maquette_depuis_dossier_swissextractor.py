import c4d, os, sys
#from libs import importMNT
from glob import glob
import subprocess
import platform
import urllib, json
from datetime import datetime


CONTAINER_ORIGIN =1026473
GEOTAG_ID = 1026472

DIRNAME_MNT2M = 'swissalti3d_2m'
DIRNAME_MNT50CM = 'swissalti3d_50cm'
DIRNAME_BATI3D = 'swissbuildings3d'
DIRNAME_ORTHO2M = 'swissimage-dop10_2m'
DIRNAME_ORTHO10CM = 'swissimage-dop10_10cm'

# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

#if platform.system() =='Windows':
    #sys.path.append("C:/Users/olivier.donze/AppData/Roaming/Maxon/Maxon Cinema 4D R25_1FE0824E/plugins")
#else:
    #sys.path.append('/Users/olivierdonze/Library/Preferences/Maxon/Maxon Cinema 4D R25_EBA43BEE/plugins')

sys.path.append(os.path.dirname(__file__))

import utils.raster as raster
import utils.mnt as importMNT
import utils.nearest_location
import utils.dir_extract
import utils.swissbuildings3D as swissbuildings3D
import utils.cut_obj_from_spline
import utils.geojson_trees
import utils.mograph_trees


from utils.swissbuildings3D import SELECTION_NAME_TOITS
import utils.shapefile as shapefile

DOC_NOT_IN_METERS_TXT = "Les unités du document ne sont pas en mètres, si vous continuez les unités seront modifiées.\nVoulez-vous continuer ?"
CONTAINER_ORIGIN =1026473

EPAISSEUR = 10 #épaisseur du socle depuis le points minimum

NAME_SELECTION_MNT = 'mnt'

FORMAT_IMAGES = '.png'
FORMAT_IMAGES_GDAL = 'PNG'


def empriseVueHaut(bd, origine):
    dimension = bd.GetFrame()
    largeur = dimension["cr"] - dimension["cl"]
    hauteur = dimension["cb"] - dimension["ct"]

    mini = bd.SW(c4d.Vector(0, hauteur, 0)) + origine
    maxi = bd.SW(c4d.Vector(largeur, 0, 0)) + origine

    return mini, maxi, largeur, hauteur


def empriseObject(obj, origine):
    mg = obj.GetMg()

    rad = obj.GetRad()
    centre = obj.GetMp()

    # 4 points de la bbox selon orientation de l'objet
    pts = [c4d.Vector(centre.x + rad.x, centre.y + rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y + rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y - rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y - rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y - rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y + rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y + rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y - rad.y, centre.z + rad.z) * mg]

    mini = c4d.Vector(min([p.x for p in pts]), min([p.y for p in pts]), min([p.z for p in pts])) + origine
    maxi = c4d.Vector(max([p.x for p in pts]), max([p.y for p in pts]), max([p.z for p in pts])) + origine

    return mini, maxi

CONTAINER_ORIGIN =1026473

def fichierPRJ(fn):
    fn = os.path.splitext(fn)[0]+'.prj'
    f = open(fn,'w')
    f.write("""PROJCS["CH1903+_LV95",GEOGCS["GCS_CH1903+",DATUM["D_CH1903+",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Hotine_Oblique_Mercator_Azimuth_Center"],PARAMETER["latitude_of_center",46.95240555555556],PARAMETER["longitude_of_center",7.439583333333333],PARAMETER["azimuth",90],PARAMETER["scale_factor",1],PARAMETER["false_easting",2600000],PARAMETER["false_northing",1200000],UNIT["Meter",1]]""")
    f.close()

def createOutline(sp,distance,doc):
    bc = c4d.BaseContainer()
    bc[c4d.MDATA_SPLINE_OUTLINE] = distance
    bc[c4d.MDATA_SPLINE_OUTLINESEPARATE] = True
    res = c4d.utils.SendModelingCommand(command = c4d.MCOMMAND_SPLINE_CREATEOUTLINE,
                                list = [sp],
                                mode = c4d.MODELINGCOMMANDMODE_ALL,
                                bc = bc,
                                doc = doc)
    if res :
        return res[0]
    else :
        return None

def shapefileFromSpline(sp,doc,fn,buffer = 0):
    origine = doc[CONTAINER_ORIGIN]
    if not origine: return None

    if buffer :
        sp = createOutline(sp,buffer,doc)
        if not sp :
            print("problème outline")
            return
    nb_seg = sp.GetSegmentCount()
    mg = sp.GetMg()
    pts = [p*mg+origine for p in sp.GetAllPoints()]

    #UN SEUL SEGMENT
    if not nb_seg :
        poly = [[[p.x,p.z] for p in pts]]

    #MULTISEGMENT (attention avec segments interne à un autre il faut les points antihoraire)
    else:
        poly = []
        id_pt = 0
        for i in range(nb_seg):
            cnt = sp.GetSegment(i)['cnt']
            poly.append([[p.x,p.z] for p in pts[id_pt:id_pt+cnt]])
            id_pt +=cnt

    with shapefile.Writer(fn,shapefile.POLYGON) as w:
        w.field('id','I')
        w.record(1)
        w.poly(poly)

        fichierPRJ(fn)
    
    if os.path.isfile(fn):
        return fn
    
    return None


def selectEdgesContour(op):

    nb = c4d.utils.Neighbor(op)
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

        if nb.GetNeighbor(poly.d, poly.a, i)==-1:
            bs.Select(inf['edge'][3])

    op.SetSelectedEdges(nb,bs,c4d.EDGESELECTIONTYPE_SELECTION)


def socle(mnt,doc):
    """crée un socle et renvoie l'altitude minimum"""
    mg = mnt.GetMg()
    alts = [(p*mg).y for p in mnt.GetAllPoints()]
    alt_min = min(alts) - EPAISSEUR

    #tag de selection de polygone
    tag_sel_terrain = c4d.SelectionTag(c4d.Tpolygonselection)
    bs = tag_sel_terrain.GetBaseSelect()
    bs.SelectAll(mnt.GetPolygonCount())
    tag_sel_terrain[c4d.ID_BASELIST_NAME] = NAME_SELECTION_MNT

    mnt.InsertTag(tag_sel_terrain)

    #Sélection des arrêtes du contour
    selectEdgesContour(mnt)
    #Extrusion à zéro
    settings = c4d.BaseContainer()                 # Settings
    settings[c4d.MDATA_EXTRUDE_OFFSET] = 0      # Length of the extrusion

    res = c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_EXTRUDE_TOOL,
                                    list = [mnt],
                                    mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION,
                                    bc = settings,
                                    doc = doc)


    #Valeurs commune des points

    settings = c4d.BaseContainer()                 # Settings
    settings[c4d.MDATA_SETVALUE_SETY] = c4d.MDATA_SETVALUE_SET_SET
    settings[c4d.MDATA_SETVALUE_VAL] = c4d.Vector(0,alt_min,0)
    #settings[c4d.TEMP_MDATA_SETVALUE_VAL_Y] = -2000
    settings[c4d.MDATA_SETVALUE_SYSTEM] = c4d.MDATA_SETVALUE_SYSTEM_WORLD

    res = c4d.utils.SendModelingCommand(command = c4d.ID_MODELING_SETVALUE_TOOL,
                                    list = [mnt],
                                    mode = c4d.MODELINGCOMMANDMODE_EDGESELECTION,
                                    bc = settings,
                                    doc = doc)
    return alt_min

def get_imgs_georef(path, ext = FORMAT_IMAGES):
    res = []
    for fn in glob(os.path.join(path,'*'+ext)):
        fn_wld = fn.replace(ext,'.wld')
        if os.path.isfile(fn_wld):
            res.append(fn)
    return res


def get_cube_from_obj(obj, haut_sup = 100):
    """Lae paramètre haut_sup sert à avoirun peu de marge en haut et en bas lorsque l'on découpe les bâtiment"""
    mg = obj.GetMg()
    rad = obj.GetRad()
    centre = obj.GetMp()

    #4 points de la bbox selon orientation de l'objet
    pts = [ c4d.Vector(centre.x+rad.x,centre.y+rad.y,centre.z+rad.z) * mg,
            c4d.Vector(centre.x-rad.x,centre.y+rad.y,centre.z+rad.z) * mg,
            c4d.Vector(centre.x-rad.x,centre.y-rad.y,centre.z+rad.z) * mg,
            c4d.Vector(centre.x-rad.x,centre.y-rad.y,centre.z-rad.z) * mg,
            c4d.Vector(centre.x+rad.x,centre.y-rad.y,centre.z-rad.z) * mg,
            c4d.Vector(centre.x+rad.x,centre.y+rad.y,centre.z-rad.z) * mg,
            c4d.Vector(centre.x-rad.x,centre.y+rad.y,centre.z-rad.z) * mg,
            c4d.Vector(centre.x+rad.x,centre.y-rad.y,centre.z+rad.z) * mg]

    mini = c4d.Vector(min([p.x for p in pts]),min([p.y for p in pts]),min([p.z for p in pts]))
    maxi = c4d.Vector(max([p.x for p in pts]),max([p.y for p in pts]),max([p.z for p in pts]))

    cube = c4d.BaseObject(c4d.Ocube)
    centre = (mini+maxi)/2

    cube.SetAbsPos(centre)
    cube[c4d.PRIM_CUBE_LEN] = maxi-mini + c4d.Vector(0,haut_sup,0)

    return cube


##################################################################################################
#GDAL
##################################################################################################

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

def gdalBIN_OK(path_to_QGIS_bin, exe = 'gdal_translate'):
    if sys.platform == 'win32':
        exe+='.exe'
    path = os.path.join(path_to_QGIS_bin,exe)
    if os.path.isfile(path):
        return path
    else:
        return False

def createVRTfromDir(path_tifs, path_to_gdalbuildvrt = None):
    if not path_to_gdalbuildvrt:
        path_to_QGIS_bin = getPathToQGISbin()
        if path_to_QGIS_bin:
            path_to_gdalbuildvrt = gdalBIN_OK(path_to_QGIS_bin, exe = 'gdalbuildvrt')

    if not path_to_gdalbuildvrt:
        c4d.gui.MessageDialog("La génération du raster virtuel (.vrt) est impossible")
        return False
    fn_vrt = path_tifs+'.vrt'
    #fichier texte avec listes images tif
    lst_img_txt = dirImgToTextFile(path_tifs, ext = '.tif')
    if lst_img_txt:
        req = f'"{path_to_gdalbuildvrt}" -input_file_list "{lst_img_txt}" "{fn_vrt}"'
        output = subprocess.check_output(req,shell=True)
        #on supprime le fichier txt
        os.remove(lst_img_txt)
        if os.path.isfile(fn_vrt):

            return fn_vrt

    return False

def extractFromBbox(raster_srce, raster_dst,xmin,ymin,xmax,ymax,taille_maille = None,form = None, path_to_gdal_translate = None):
    """normalement l'extension du fichier de destination permet le choix du format (à vérifier)
       si on a du .png ou du .jpg un fichier wld est généré"""

    name,ext = os.path.splitext(raster_dst)
    if ext in ['.jpg','.png']:
        wld = '-co worldfile=yes'
    else:
        wld = ''
    if not path_to_gdal_translate:
        path_to_QGIS_bin = getPathToQGISbin()
        if path_to_QGIS_bin:
            path_to_gdal_translate = gdalBIN_OK(path_to_QGIS_bin, exe = 'gdal_translate')

    if not path_to_gdal_translate:
        c4d.gui.MessageDialog("L'extraction est impossible, gdal_translate non trouvé")
        return False
    f = ''
    #ATTENTION normalement gdal_translate met automatiquement le bon format en fonction de l'extension
    #mais avec le .asc il met appremment quelques fois le format Arc/Info Binary Grid (AIG) au lieu du AAIGrid !!!
    # (constaté sur PC)
    if form :
        f = f'-of {form}'
    
    if taille_maille :
        req = f'"{path_to_gdal_translate}" {f} {wld} -tr {taille_maille} {taille_maille} -projwin {xmin} {ymax} {xmax} {ymin} "{raster_srce}" "{raster_dst}"'
    else:
        req = f'"{path_to_gdal_translate}" {f} {wld} -projwin {xmin} {ymax} {xmax} {ymin} "{raster_srce}" "{raster_dst}"'

    
    output = subprocess.check_output(req,shell=True)
    if os.path.isfile(raster_dst):
        return raster_dst

    return False

def extractFromSpline(fn_shp,raster_srce, raster_dst,cellsize, form = 'AAIGrid', path_to_gdalwarp = None):
    if not path_to_gdalwarp:
        path_to_QGIS_bin = getPathToQGISbin()
        if path_to_QGIS_bin:
            path_to_gdalwarp = gdalBIN_OK(path_to_QGIS_bin, exe = 'gdalwarp')

    if not path_to_gdalwarp:
        c4d.gui.MessageDialog("L'extraction est impossible, gdal_translate non trouvé")
        return False
    
    layer_name = os.path.basename(fn_shp)[:-4]
    req = f'"{path_to_gdalwarp}" -overwrite -of {form} -cutline "{fn_shp}" -tr {cellsize} {cellsize} -cl "{layer_name}" -crop_to_cutline "{raster_srce}" "{raster_dst}"'
    output = subprocess.check_output(req,shell=True)
    
    if os.path.isfile(raster_dst):
        return raster_dst
    
    return False

def dirImgToTextFile(path_dir, ext = '.tif'):
    """crée un fichier texte avec le chemin de l'image pour chaque ligne"""
    fn_txt = path_dir+'.txt'
    len_ext = len(ext)
    lst_img = [os.path.join(path_dir,fn) for fn in os.listdir(path_dir) if fn[-len_ext:] == ext]

    if lst_img :
        with open(fn_txt,'w') as f:
            for fn in lst_img:
                f.write(fn+'\n')
        return fn_txt
    return False

######################################################################################################
#CIEL PHYSIQUE ET GI

def lv95towgs84(x,y):
    url = f'http://geodesy.geo.admin.ch/reframe/lv95towgs84?easting={x}&northing={y}&format=json'

    f = urllib.request.urlopen(url)
    #TODO : vérifier que cela à bien fonctionnéé (code =200)
    txt = f.read().decode('utf-8')
    json_res = json.loads(txt)

    return float(json_res['easting']),float(json_res['northing'])

def physical_sky_from_origin(doc, date_heure = '21.06.2022 17:00:00'):
    Ophysicalsky = 1011146
    sky = c4d.BaseObject(Ophysicalsky)

    #il faut bien cocher Generate GI pour avoir le ciel par défaut
    sky[c4d.SKY_MATERIAL_GLOBALILLUM_GENERATE] = True

    #c4d.CallCommand(1011145) # Physical Sky
    #sky = doc.GetFirstObject()

    # Parse the time string
    dt = datetime.strptime(date_heure,"%d.%m.%Y %H:%M:%S")
    dtd = sky[c4d.SKY_DATE_TIME]

    # Fills the Data object with the DateTime object
    dtd.SetDateTime(dt)
    sky[c4d.SKY_DATE_TIME] = dtd

    #sky = c4d.BaseObject(Ophysicalsky)
    sky[c4d.SKY_MATERIAL_GLOBALILLUM_GENERATE] = True

    origin = doc[CONTAINER_ORIGIN]

    #si on a pas d'origine on met le préréglage à Genève
    if not origin :
        sky[c4d.SKY_POS_CITY_COMBO] = 654 #Genève

    #sinon on calcule la latitude/longitude
    else:
        lon,lat = lv95towgs84(origin.x,origin.z)

        sky[c4d.SKY_POS_LATITUDE] = c4d.utils.Rad(lat)
        sky[c4d.SKY_POS_LONGITUDE] = c4d.utils.Rad(lon)

    return sky

def activeGI(doc):
    rd = doc.GetActiveRenderData()

    #on vérifie si il y a déjà la GI
    vp = rd.GetFirstVideoPost()
    while vp:
        if vp.GetType() == c4d.VPglobalillumination:
            break
        vp = vp.GetNext()
    if not vp :
        vp = c4d.documents.BaseVideoPost(c4d.VPglobalillumination)
        rd.InsertVideoPostLast(vp)
    else:
        #si la gi est présente on l'active'
        vp.SetAllBits(c4d.BIT_ACTIVE)

    vp[c4d.GI_SETUP_DATA_PRESETS] = 6220 #Preset Exterior Preview
######################################################################################################

def tex_folder(doc, subfolder = None):
    """crée le dossier tex s'il n'existe pas et renvoie le chemin
       si subfolder est renseigné crée également le sous-dossier
       et renvoie le chemin du sous dossier
       Si le doc n'est pas enregistré renvoie None
       """

    path_doc = doc.GetDocumentPath()
    #si le doc n'est pas enregistré renvoie None
    if not path_doc : return None

    path = os.path.join(path_doc,'tex')

    if subfolder:
        path = os.path.join(path,subfolder)

    if not os.path.isdir(path):
        os.makedirs(path)
    return path



# Main function
def main(doc,origine,pth,xmin,ymin,xmax,ymax,taille_maille,mnt2m,mnt50cm,bati3D,ortho2m,ortho10cm,fn_trees,fn_forest,arbres_sources = None,spline_decoupe = None):
    #suffixe avec la bbox pour l'orthophoto
    #pour ne pas refaire si l'image existe
    suffixe_img = f'_{round(xmin)}_{round(ymin)}_{round(xmax)}_{round(ymax)}'

    lst_imgs =[]
    lst_asc = []

    #création du shapefile pour le découpage
    if spline_decoupe:
        fn_shp = os.path.join(pth,'__emprise__.shp')
        fn_shp = shapefileFromSpline(spline_decoupe,doc,fn_shp,buffer = 2*taille_maille)

    if mnt2m:
        pth_tuiles_mnt2m = os.path.join(pth,DIRNAME_MNT2M)
        if os.path.isdir(pth_tuiles_mnt2m):
            #VRT
            fn_mnt2m_vrt = createVRTfromDir(pth_tuiles_mnt2m, path_to_gdalbuildvrt = None)
            #extraction mnt
            fn_mnt2m = fn_mnt2m_vrt.replace('.vrt','.asc')
            if spline_decoupe and fn_shp :
                extractFromSpline(fn_shp,fn_mnt2m_vrt, fn_mnt2m,taille_maille, form = 'AAIGrid', path_to_gdalwarp = None)
            else:
                extractFromBbox(fn_mnt2m_vrt, fn_mnt2m,xmin,ymin,xmax,ymax,taille_maille = taille_maille ,form = 'AAIGrid',path_to_gdal_translate = None)

            if os.path.isfile(fn_mnt2m):
                lst_asc.append(fn_mnt2m)
    
    if mnt50cm:
        pth_tuiles_mnt50cm = os.path.join(pth,DIRNAME_MNT50CM)
        if os.path.isdir(pth_tuiles_mnt50cm):
            #VRT
            fn_mnt50cm_vrt = createVRTfromDir(pth_tuiles_mnt50cm, path_to_gdalbuildvrt = None)
            #extraction mnt
            fn_mnt50cm = fn_mnt50cm_vrt.replace('.vrt','.asc')
            if spline_decoupe and fn_shp :
                extractFromSpline(fn_shp,fn_mnt50cm_vrt, fn_mnt50cm,taille_maille, form = 'AAIGrid', path_to_gdalwarp = None)
            else:
                extractFromBbox(fn_mnt50cm_vrt, fn_mnt50cm,xmin,ymin,xmax,ymax,taille_maille = taille_maille ,form = 'AAIGrid',path_to_gdal_translate = None)

            if os.path.isfile(fn_mnt50cm):
                lst_asc.append(fn_mnt50cm)

    if ortho2m:
        pth_tuiles_ortho2m = os.path.join(pth,DIRNAME_ORTHO2M)
        if os.path.isdir(pth_tuiles_ortho2m):
            #VRT
            fn_ortho2m_vrt = createVRTfromDir(pth_tuiles_ortho2m, path_to_gdalbuildvrt = None)
            #extraction 
            path_dir_imgs = tex_folder(doc, subfolder = 'swisstopo_images')
            nom_img = os.path.splitext(os.path.basename(fn_ortho2m_vrt))[0]
            nom_img+=suffixe_img + FORMAT_IMAGES

            fn_ortho2m = os.path.join(path_dir_imgs,nom_img)

            #TODO : rotation et découpage de l'image selon spline_decoupe
            extractFromBbox(fn_ortho2m_vrt, fn_ortho2m,xmin,ymin,xmax,ymax,taille_maille = 2 ,form = FORMAT_IMAGES_GDAL,path_to_gdal_translate = None)

            if os.path.isfile(fn_ortho2m):
                lst_imgs.append(fn_ortho2m)
    
    if ortho10cm:
        pth_tuiles_ortho10cm = os.path.join(pth,DIRNAME_ORTHO10CM)
        if os.path.isdir(pth_tuiles_ortho10cm):
            #VRT
            fn_ortho10cm_vrt = createVRTfromDir(pth_tuiles_ortho10cm, path_to_gdalbuildvrt = None)
            #extraction 
            path_dir_imgs = tex_folder(doc, subfolder = 'swisstopo_images')
            nom_img = os.path.splitext(os.path.basename(fn_ortho10cm_vrt))[0]
            nom_img+=suffixe_img + FORMAT_IMAGES

            fn_ortho10cm = os.path.join(path_dir_imgs,nom_img)

            #TODO : rotation et découpage de l'image selon spline_decoupe
            extractFromBbox(fn_ortho10cm_vrt, fn_ortho10cm,xmin,ymin,xmax,ymax,taille_maille = 0.1 ,form = FORMAT_IMAGES_GDAL,path_to_gdal_translate = None)

            if os.path.isfile(fn_ortho10cm):
                lst_imgs.append(fn_ortho10cm)
            



    #création des fichiers vrt pour les rasters
    """for directory in [x[0] for x in os.walk(pth)]:
        name = os.path.basename(directory)
        if 'swissalti3d' in name or 'swissimage' in name:
            #TODO : s'il y a un déjà un fichier VRT regarder si l'emprise est ok
            #pour pas le refaire si pas nécessaire
            vrt_file = createVRTfromDir(directory, path_to_gdalbuildvrt = None)

            #+ extraction de l'image'
            if 'swissimage' in name:
                path_dir_imgs = tex_folder(doc, subfolder = 'swisstopo_images')
                nom_img = os.path.splitext(os.path.basename(vrt_file))[0]
                nom_img+=suffixe_img + FORMAT_IMAGES

                raster_dst = os.path.join(path_dir_imgs,nom_img)

                lst_imgs.append(raster_dst)

                if not os.path.isfile(raster_dst):
                    extractFromBbox(vrt_file, raster_dst,xmin,ymin,xmax,ymax,form = None,path_to_gdal_translate = None)

            elif 'swissalti3d' in name:
                raster_dst = vrt_file.replace('.vrt','.asc')
                extractFromBbox(vrt_file, raster_dst,xmin,ymin,xmax,ymax,taille_maille = taille_maille ,form = 'AAIGrid',path_to_gdal_translate = None)"""

    #lst_asc = [fn_asc for fn_asc in glob(os.path.join(pth,'*.asc'))]
    #lst_dxf = get_swissbuildings3D_dxfs(pth)
    #lst_imgs = get_imgs_georef(pth)

    if not lst_asc and not lst_dxf and not lst_imgs:
        c4d.gui.MessageDialog("""Il n'y a ni terrain ni swissbuidings3D ni images géoréférée dans le dossier, import impossible""")
        return

    #document en mètre
    doc = c4d.documents.GetActiveDocument()

    usdata = doc[c4d.DOCUMENT_DOCUNIT]
    scale, unit = usdata.GetUnitScale()
    if  unit!= c4d.DOCUMENT_UNIT_M:
        rep = c4d.gui.QuestionDialog(DOC_NOT_IN_METERS_TXT)
        if not rep : return
        unit = c4d.DOCUMENT_UNIT_M
        usdata.SetUnitScale(scale, unit)
        doc[c4d.DOCUMENT_DOCUNIT] = usdata

    doc.StartUndo()

    alt_min = 0
    #Modèle(s) de terrain
    mnt = None
    cube_mnt = None
    for fn_asc in lst_asc:
        mnt = importMNT.terrainFromASC(fn_asc,doc)
        if spline_decoupe:
            volume_decoupe = utils.cut_obj_from_spline.volumeFromSpline(spline_decoupe)
            if volume_decoupe:
                mnt_decoupe = utils.cut_obj_from_spline.decoupeMNTfromVolume(mnt,volume_decoupe)
                if mnt_decoupe :
                    mnt.Remove()
                    mnt = mnt_decoupe

        if mnt:
            #alt_min = socle(mnt,doc)
            doc.InsertObject(mnt)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mnt)


            #CUBE pour la découpe des batiments
            cube_mnt = get_cube_from_obj(mnt)
            pos = cube_mnt.GetRelPos()
            #lorsque l'on génére le mnt la position se fait par le geotag
            #et le déplacement se fait après, du coup c'est le moyen pas très élégant
            #que j'ai trouvé pour que le cube soit au bon endroit'
            geotag = mnt.GetTag(GEOTAG_ID)
            if geotag:
                cube_mnt
                pos+= geotag[CONTAINER_ORIGIN] - doc[CONTAINER_ORIGIN]
                cube_mnt.SetRelPos(pos)


    #Swissbuidings3D
    buildings = None
    if bati3D:
        if spline_decoupe:
            volume_decoupe = utils.cut_obj_from_spline.volumeFromSpline(spline_decoupe)
            buildings = swissbuildings3D.importSwissBuidings(pth, doc, volume_decoupe)
        else:
            buildings = swissbuildings3D.importSwissBuidings(pth, doc, cube_mnt)
        
        if buildings :
            doc.InsertObject(buildings)

    ###################################
    # ARBRES
    ###################################

    # il faut un mnt (TODO générer les arbres au sol si on n'a pas de MNT ???)
    trees = None
    forest = None
    if mnt:
        if fn_trees:
            point_object_trees_sommets = utils.geojson_trees.pointObjectFromGeojson(fn_trees,origine, color = c4d.Vector4d(0.0, 1.0, 0.0, 1.0))
            if point_object_trees_sommets:
                trees = utils.mograph_trees.mograph_system_trees(point_object_trees_sommets, mnt, arbres_sources,doc)
                
                doc.InsertObject(trees)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,trees)


        if fn_forest:
            splines_forest = utils.geojson_trees.splinesFromGeojson(fn_forest,origine)
            if splines_forest :
                forest = utils.mograph_trees.mograph_system_forest(splines_forest, mnt, arbres_sources, doc, density = 0.02)

                doc.InsertObject(forest)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,forest)

    #IMAGES
    #si on a un mnt on le sélectionne pour que l'image se plaque dessus'
    # TODO si on n'a pas de MNT -> créer un plan à la taille de l'image ?
    if mnt:
        doc.SetActiveObject(mnt)
    #sinon on déselectionne tout
    else:
        for obj in doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_NONE):
            obj.DelBit(c4d.BIT_ACTIVE)


    for img in lst_imgs :
        #raster.main(fn = img, fn_calage = None, alerte = True)
        fn_calage = img.replace(FORMAT_IMAGES,'.wld')

        #il faut que l'image et le fichier de calage existe'
        if os.path.isfile(img) and os.path.isfile(fn_calage):
            gp = raster.Geopict(img,fn_calage,c4d.documents.GetActiveDocument())
            mat = gp.creerTexture(relatif=True)
            mat = gp.mat

        #on contraint les tags materiau au mnt
        if mnt :
            #on regarde si il a un geotag
            if not mnt.GetTag(1026472,0):
                tg = gp.creerGeoTag(mnt)
            tag = gp.creerTagTex(mnt, displayTag = False)
            tag[c4d.TEXTURETAG_RESTRICTION] = NAME_SELECTION_MNT

        if buildings:
            #on regarde si il a un geotag
            if not buildings.GetTag(1026472,0):
                tg = gp.creerGeoTag(buildings)
            tag = gp.creerTagTex(buildings, displayTag = False)
            tag[c4d.TEXTURETAG_RESTRICTION] = SELECTION_NAME_TOITS
        
        if trees:
            #on regarde si il a un geotag
            if not trees.GetTag(1026472,0):
                tg = gp.creerGeoTag(trees)
            tag = gp.creerTagTex(trees, displayTag = False)
        if forest :
            #on regarde si il a un geotag
            if not forest.GetTag(1026472,0):
                tg = gp.creerGeoTag(forest)
            tag = gp.creerTagTex(forest, displayTag = False)


    ##################################
    #SOCLE MNT
    ##################################
    if mnt:
        alt_min = socle(mnt,doc)
        #doc.InsertObject(mnt)
        #doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mnt)


        #CUBE pour la découpe des batiments
        cube_mnt = get_cube_from_obj(mnt)
        pos = cube_mnt.GetRelPos()
        #lorsque l'on génére le mnt la position se fait par le geotag
        #et le déplacement se fait après, du coup c'est le moyen pas très élégant
        #que j'ai trouvé pour que le cube soit au bon endroit'
        geotag = mnt.GetTag(GEOTAG_ID)
        if geotag:
            cube_mnt
            pos+= geotag[CONTAINER_ORIGIN] - doc[CONTAINER_ORIGIN]
            cube_mnt.SetRelPos(pos)

    ##############################################
    #ENVIRONNEMENT
    ##############################################
    #on crée seulement si on n'en trouve pas déjà un 
    if not doc.SearchObject('environnement'):
        environnement = c4d.BaseObject(c4d.Onull)
        environnement.SetName('environnement')

        #MATERIAU ARRIERE-PLAN
        mat_back = c4d.BaseMaterial(c4d.Mmaterial)
        mat_back.SetName('Fond')
        mat_back[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(1)
        
        doc.InsertMaterial(mat_back)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mat_back)

        #SOL
        sol = c4d.BaseObject(c4d.Ofloor)
        if mnt and alt_min:
            sol.SetAbsPos(c4d.Vector(0,alt_min,0))
        #compositing tag pour compositing background
        tag_comp = c4d.BaseTag(c4d.Tcompositing)   
        tag_comp[c4d.COMPOSITINGTAG_BACKGROUND] = True
        sol.InsertTag(tag_comp)
        #tag materiau
        mat_tag = c4d.TextureTag()
        mat_tag.SetMaterial(mat_back)
        mat_tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_FRONTAL
        sol.InsertTag(mat_tag)
        sol.InsertUnder(environnement)
        
        #ARRIERE-PLAN
        bg = c4d.BaseObject(c4d.Obackground)
        mat_tag = c4d.TextureTag()
        mat_tag.SetMaterial(mat_back)
        mat_tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_FRONTAL
        bg.InsertTag(mat_tag)
        bg.InsertUnder(environnement)


        doc.InsertObject(environnement)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,environnement)

        #GI et Ciel Physique
        activeGI(doc)
        sky = physical_sky_from_origin(doc)
        #compositing tag pour qu'il ne soit pas visible
        tag_comp = c4d.BaseTag(c4d.Tcompositing)    
        tag_comp[c4d.COMPOSITINGTAG_SEENBYCAMERA] = False
        sky.InsertTag(tag_comp)
        sky.InsertUnder(environnement)

    doc.EndUndo()
    c4d.EventAdd()

# Execute main()
if __name__=='__main__':
    doc = c4d.documents.GetActiveDocument()
    origine = doc[CONTAINER_ORIGIN]

    op = doc.GetActiveObject()
    if not op:
        c4d.gui.MessageDialog("Il faut sélectionner un objet pour l'emprise")
    
    if op:
        #
        #pth = 'E:/OD/Vallee_du_Trient/SIG/swisstopo_extraction_diligences/vernayaz'
        pth = c4d.storage.LoadDialog(flags = c4d.FILESELECT_DIRECTORY,title="Dossier contenant les .dxf de swisstopo")
        
        if pth : 
    
            mini,maxi = empriseObject(op,origine)
            xmin,ymin,xmax,ymax = mini.x,mini.z,maxi.x,maxi.z
            main(doc,origine,pth,xmin,ymin,xmax,ymax)
