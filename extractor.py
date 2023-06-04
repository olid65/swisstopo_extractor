
import c4d
import shapefile
import os, json, sys
import socket
import json
import urllib
from zipfile import ZipFile
import subprocess

# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
# def state():
#    return True

sys.path.append(os.path.dirname(__file__))
from thread_download import ThreadDownload

from maquette_depuis_dossier_swissextractor import main as import_maquette
import utils.trees_esri_rest_api_geojson as trees



CONTAINER_ORIGIN = 1026473

ID_RECTANGLE_TOOL = 1058813

ID_SWISSTOPO_ORTHO_DISPLAY = 1058393
ID_SWISSTOPO_CN10_DISPLAY = 1058394

#NOMBRE DE POLYGONES MAX POUR UN MNT
#AU DESSUS ON NE PEUT PAS CHARGER
NB_POLYGONES_MAX = 2000000


FOLDER_NAME_SWISSTOPO = "swisstopo"


URL_STAC_SWISSTOPO_BASE = 'https://data.geo.admin.ch/api/stac/v0.9/collections/'

DIC_LAYERS = {'ortho':'ch.swisstopo.swissimage-dop10',
              'mnt':'ch.swisstopo.swissalti3d',
              'bati3D':'ch.swisstopo.swissbuildings3d_2',
              }

#Fichier pour le noms de lieu au même emplacement que ce fichier
LOCATIONS_FILE = os.path.join(os.path.dirname(__file__),'noms_lieux.json')


TXT_NO_FILE_TO_DOWNLOAD = "Tous les fichiers existent déjà, ou il n'y a pas de fichier à télécharger"

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

def extractFromBbox(raster_srce, raster_dst,xmin,ymin,xmax,ymax,path_to_gdal_translate = None):
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
    req = f'"{path_to_gdal_translate}" {wld} -projwin {xmin} {ymax} {xmax} {ymin} "{raster_srce}" "{raster_dst}"'
    output = subprocess.check_output(req,shell=True)
    if os.path.isfile(raster_dst):
        return raster_dst

    return False

######################################################################################################

def verify_web_connexion(hostname = "www.google.com"):
  """pour vérifier s'il y a une connexion internet"""
  # from : https://askcodez.com/tester-si-une-connexion-internet-est-presente-en-python.html
  try:
    # see if we can resolve the host name -- tells us if there is
    # a DNS listening
    host = socket.gethostbyname(hostname)
    # connect to the host -- tells us if the host is actually
    # reachable
    s = socket.create_connection((host, 80), 2)
    return True
  except:
     pass
  return False

def empriseVueHaut(bd, origine):
    dimension = bd.GetFrame()
    largeur = dimension["cr"] - dimension["cl"]
    hauteur = dimension["cb"] - dimension["ct"]

    mini = bd.SW(c4d.Vector(0, hauteur, 0)) + origine
    maxi = bd.SW(c4d.Vector(largeur, 0, 0)) + origine

    return mini, maxi, largeur, hauteur


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
    
    return mini, maxi


def fichierPRJ(fn):
    fn = os.path.splitext(fn)[0] + '.prj'
    f = open(fn, 'w')
    f.write(
        """PROJCS["CH1903+_LV95",GEOGCS["GCS_CH1903+",DATUM["D_CH1903+",SPHEROID["Bessel_1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Hotine_Oblique_Mercator_Azimuth_Center"],PARAMETER["latitude_of_center",46.95240555555556],PARAMETER["longitude_of_center",7.439583333333333],PARAMETER["azimuth",90],PARAMETER["scale_factor",1],PARAMETER["false_easting",2600000],PARAMETER["false_northing",1200000],UNIT["Meter",1]]""")
    f.close()


def bbox2shapefile(mini, maxi):
    poly = [[[mini.x, mini.z], [mini.x, maxi.z], [maxi.x, maxi.z], [maxi.x, mini.z]]]

    fn = c4d.storage.LoadDialog(flags=c4d.FILESELECT_SAVE)

    if not fn: return
    with shapefile.Writer(fn, shapefile.POLYGON) as w:
        w.field('id', 'I')
        w.record(1)
        w.poly(poly)

        fichierPRJ(fn)

def lv95towgs84(x,y):
    url = f'http://geodesy.geo.admin.ch/reframe/lv95towgs84?easting={x}&northing={y}&format=json'

    f = urllib.request.urlopen(url)
    #TODO : vérifier que cela à bien fonctionnéé (code =200)
    txt = f.read().decode('utf-8')
    json_res = json.loads(txt)

    return float(json_res['easting']),float(json_res['northing'])


def get_list_from_STAC_swisstopo(url,xmin,ymin,xmax,ymax, gdb = False):
    #pour les bati3D il y a chaque fois toute la Suisse dans 2 gdb
    #pour les mnt on aussi du xyz
    # attention bien prendre les 8 derniers caractères
    if gdb :
        lst_indesirables = []
    else:
        lst_indesirables = ['.xyz.zip','.gdb.zip']
    #conversion coordonnées
    est,sud = lv95towgs84(xmin,ymin)
    ouest, nord = lv95towgs84(xmax,ymax)

    sufixe_url = f"/items?bbox={est},{sud},{ouest},{nord}"


    url += sufixe_url
    f = urllib.request.urlopen(url)
    txt = f.read().decode('utf-8')
    json_res = json.loads(txt)

    res = []

    for item in json_res['features']:
        for k,dic in item['assets'].items():
            href = dic['href']
            if gdb:
                #on garde que les gdb
                if href[-8:] == '.gdb.zip':
                    #dans la version 3 on a soit un url qui se termine par swissbuildings3d_3_0_2021_2056_5728.gdb.zip
                    #qui contient la moitié de la suisse
                    #ou swissbuildings3d_3_0_2020_1301-31_2056_5728.gdb.zip sous forme de tuile
                    #-> donc on ne garde que la dernière qui après un split('_') a une longueur de 7
                    if len(dic['href'].split('/')[-1].split('_'))==7:
                        res.append(dic['href'])
            else:
                if href[-8:] not in lst_indesirables:
                    res.append(dic['href'])
    return res

def suppr_doublons_list_ortho(lst):
    """supprime les doublons de no de feuilles et garde uniquement la plus récente"""
    dic = {}
    for url in lst:
        #exemple url
        #https://data.geo.admin.ch/ch.swisstopo.swissimage-dop10/swissimage-dop10_2020_2567-1107/swissimage-dop10_2020_2567-1107_2_2056.tif
        #on extrait le dernier élément en splitant par /
        #on ne grade pas l'extension [:-4]
        # et on split par _ pour récupérer nom,an,noflle,taille_px,epsg
        nom,an,noflle,taille_px,epsg = url.split('/')[-1][:-4].split('_')
        dic.setdefault((noflle,float(taille_px)),[]).append((an,url))
    res = []
    for noflle,lst in dic.items():
        an, url = sorted(lst,reverse = True)[0]
        res.append(url)
    return res

def suppr_doublons_bati3D(lst_url):    
    dico = {}
    dxf_files = [url for url in lst_url if url[-8:]=='.dxf.zip']
    for dxf in dxf_files:
        #on a une url du genre :
        #https://data.geo.admin.ch/ch.swisstopo.swissbuildings3d_2/swissbuildings3d_2_2021-09_1300-24/swissbuildings3d_2_2021-09_1300-24_2056_5728.dxf.zip
        #on split par /
        #et on prend le dossier parent qui contient la date et le n° de feuille (avant-dernier ->[-2]):
        #'swissbuildings3d_2_2021-09_1300-24'
        # le *a sert simplement à récupérer tout ce qui a avant date et feuille

        *a,date,feuille = dxf.split('/')[-2].split('_')
        #on fait un dico avec le nom de la feuille comme clé
        #et une liste de tuple (date, url_du_dxf)
        dico.setdefault(feuille,[]).append((date,dxf))
        
    res = []
    for k,liste in dico.items():
        #en triant la liste en décroissant on a le fichier le plus récent en premier
        res.append(sorted(liste,reverse=True)[0][1])
    return res

def isRectangleNordSud(sp):
    if sp.GetPointCount()!= 4:
        return False

    p1,p2,p3,p4 = [p*sp.GetMg() for p in sp.GetAllPoints()]

    for p1,p2 in zip([p1,p2,p3,p4],[p2,p3,p4,p1]):
        v = p2-p1

        if v.x !=0 and v.z !=0:
            return False
    return True

def get_spline_from_plane(obj):
    pts = [c4d.Vector(p*obj.GetMg()) for p in obj.GetAllPoints()]

    if len(pts)<3 :
        print('pas assez de points')
        return
    p1,p2,*r = pts

    p1.y = 0
    p2.y = 0

    off = c4d.Vector(p1)
    v1 = (p2-p1).GetNormalized()

    if v1 == c4d.Vector(0):
        print('pas conforme')
        return
    if v1.y :
        print('pas horizontal')
        return

    v2 = c4d.Vector(0,1,0)
    v3 = v1.Cross(v2)

    mg = c4d.Matrix(off,v1,v2,v3)

    #onull = c4d.BaseObject(c4d.Onull)
    #onull.SetMg(mg)
    #doc.InsertObject(onull)

    #

    pts = [p*~mg for p in pts]

    xmin = min([p.x for p in pts])
    xmax = max([p.x for p in pts])
    zmin = min([p.z for p in pts])
    zmax = max([p.z for p in pts])

    sp = c4d.SplineObject(4,c4d.SPLINETYPE_LINEAR)
    sp.SetAllPoints([c4d.Vector(xmin,0,zmin),c4d.Vector(xmax,0,zmin),c4d.Vector(xmax,0,zmax),c4d.Vector(xmin,0,zmax)])
    sp[c4d.SPLINEOBJECT_CLOSED] = True
    sp.SetMg(mg)
    sp.SetName(obj.GetName())
    return sp

class DlgBbox(c4d.gui.GeDialog):
    N_MIN = 1015
    N_MAX = 1016
    E_MIN = 1017
    E_MAX = 1018

    COMBO_LOCALISATION =1039
    BTON_ORTHO = 1040
    BTON_CN = 1041

    BTON_DRAW_RECTANGLE = 1049
    BTON_FROM_OBJECT = 1050
    BTON_FROM_VIEW = 1051
    BTON_COPY_ALL = 1052
    BTON_PLANE = 1053
    BTON_EXPORT_SHP = 1054

    BTON_N_MIN = 1055
    BTON_N_MAX = 1056
    BTON_E_MIN = 1057
    BTON_E_MAX = 1058

    CHECKBOX_MNT2M = 1500
    CHECKBOX_MNT50CM = 1501
    CHECKBOX_BATI3D = 1502
    CHECKBOX_BATI3D_V3 = 1505
    CHECKBOX_ORTHO2M = 1503
    CHECKBOX_ORTHO10CM = 1504
    CHECKBOX_TREES = 1506
    CHECKBOX_FOREST = 1507

    ID_TXT_NBRE_POLYS_MNT = 1508
    ID_TAILLE_MAILLE_MNT = 1509
    ID_CHECKBOX_CUT_WITH_SPLINE = 1510


    CHECKBOX_SWISSTOPO_FOLDER = 1515


    BTON_GET_URLS_DOWNLOAD = 1600

    ID_MAIN_GROUP = 1700
    ID_GROUP_IMPORT_MODEL =1701
    BTON_IMPORT_MODEL = 1702

    ID_TXT_DOWNLOAD_STATUS = 1800


    LABEL_MNT2M = "MNT 2m"
    LABEL_MNT50CM = "MNT 50cm"
    LABEL_BATI3D = "Bâtiments 3D"
    LABEL_BATI3D_V3 = "Bâtiments 3D V3 (pour impression 3D)"
    LABEL_ORTHO2M = "Orthophoto 2m"
    LABEL_ORTHO10CM = "Orthophoto 10cm"
    LABEL_TREES = "Arbres isolés"
    LABEL_FOREST = "Cordons boisés et forêts"

    LABEL_SWISSTOPO_FOLDER = f'télécharger dans le dossier "{FOLDER_NAME_SWISSTOPO}"'

    TXT_NO_SURFACE = "Pas d'emprise définie"
    TXT_SURFACE_NOMBRE_POLYS_MNT = "Nombre de polygones pour le MNT : "
    TXT_CUT_WITH_SPLINE = "Découpage selon la spline sélectionnée"

    TXT_NOT_SAVED = "Le document doit être enregistré pour pouvoir copier les textures dans le dossier tex, vous pourrez le faire à la prochaine étape\nVoulez-vous continuer ?"
    TXT_DOC_NOT_IN_METERS = "Les unités du document ne sont pas en mètres, si vous continuez les unités seront modifiées.\nVoulez-vous continuer ?"
    TXT_NAS_HEPIA = "Votre document est enregistré sur le NAS (hes-nas-prairie.hes.adhes.hesge.ch).\nEnregistrez le projet et les ressources utilisées sur un autre disque (disque dur externe, Partage, ou dossier à votre nom à la racine de C:)"
    TXT_PATH_CAR_SPECIAL = "Le chemin de fichier continet un ou plusieurs caractères spéciaux (accents,cédille,...) \nImport impossible !"


    TXT_NO_PATH_TO_QGIS = "QGis ne semble pas installé sur cette machine, vous pourrez importer les différents fichiers sur votre ordinateur, mais pas importer la maquette dans Cinema4D."
    TXT_NO_PATH_TO_QGIS_QUESTION = TXT_NO_PATH_TO_QGIS +" Voulez-vous continuer ?"
    TXT_NO_PATH_TO_QGIS_FINAL = "Sans Qgis l'import de la maquette est impossible !"

    TXT_NO_ORIGIN = "Le document n'est pas géoréférencé !"
    TXT_NOT_VIEW_TOP = "Vous devez activer une vue de haut !"
    TXT_NO_SELECTION = "Vous devez sélectionner un objet !"
    TXT_MULTI_SELECTION = "Vous devez sélectionner un seul objet !"

    TXT_NO_PLUGIN_SWISSTOPO_DISPLAY = """Le plugin "affichage swisstopo" n'est pas intallé !"""
    TXT_NO_PLUGIN_RECTANGLE = "Le plugin de dessin de rectangle n'est pas installé !"

    TXT_IMPORT_MODEL = "Tous les fichiers ont été téléchargés, voulez vous importer la maquette ?"

    TITLE_GEOLOC = "1. Géolocalisation et affichage d'arrière plan"
    TITLE_EMPRISE = "2. Définissez l'emprise de l'extraction"
    TITLE_LAYER_CHOICE = "3. Choisissez les couches"
    TITLE_LIST_TO_DOWNLOAD = "4. Liste des fichiers à télécharger"

    MARGIN = 10
    LARG_COORD = 130

    dico_lieux = None
    lst_lieux = None


    doc = None
    origine = None
    pth_swisstopo_data = None
    bbox = None
    taille_maille = None
    mini = maxi = None
    total_polys = 0

    spline_cut = None
    mnt2m = False
    mnt50cm = False
    bati3D = False
    bati3D_v3 = False
    ortho2m = False
    ortho10cm = False

    fn_trees = None
    fn_forest = None
    
    def CreateLayout(self):
        #lecture du fichier des lieux
        if os.path.isfile(LOCATIONS_FILE):
            with open(LOCATIONS_FILE, encoding = 'utf-8') as f:
                self.dico_lieux = json.load(f)
            if self.dico_lieux:
                self. lst_lieux =[k for k in self.dico_lieux.keys()]


        self.SetTitle("swisstopo extractor")
        # MAIN GROUP
        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=1, rows=6)
        self.GroupBorderSpace(self.MARGIN*2, self.MARGIN*2, self.MARGIN*2, self.MARGIN*2)

        # GEOLOCALISATION
        self.AddStaticText(400, flags=c4d.BFH_LEFT, initw=0, inith=0, name=self.TITLE_GEOLOC, borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)

        self.AddComboBox(self.COMBO_LOCALISATION, flags=c4d.BFH_LEFT, initw=200, inith=0, specialalign=False, allowfiltering=True)
        #
        self.AddChild(self.COMBO_LOCALISATION,0,'--choisissez un lieu--')
        if self.dico_lieux:
            for i,k in enumerate(self.dico_lieux.keys()):
                self.AddChild(self.COMBO_LOCALISATION,i+1,k)

        self.AddButton(self.BTON_ORTHO, flags=c4d.BFH_MASK, initw=0, inith=0, name="orthophoto")
        self.AddButton(self.BTON_CN, flags=c4d.BFH_MASK, initw=0, inith=0, name="carte nationale")
        self.GroupEnd()
        self.AddSeparatorH( initw=150, flags=c4d.BFH_FIT)

        # EMPRISE
        self.AddStaticText(400, flags=c4d.BFH_LEFT, initw=0, inith=0, name=self.TITLE_EMPRISE, borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.AddStaticText(1001, name="Nord :", flags=c4d.BFH_MASK, initw=50)
        self.AddEditNumber(self.N_MAX, flags=c4d.BFH_MASK, initw=self.LARG_COORD, inith=0)
        self.AddButton(self.BTON_N_MAX, flags=c4d.BFH_MASK, initw=0, inith=0, name="copier")
        self.GroupEnd()

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=7, rows=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.AddStaticText(1003, name="Est :", flags=c4d.BFH_MASK, initw=50)
        self.AddEditNumber(self.E_MIN, flags=c4d.BFH_MASK, initw=self.LARG_COORD, inith=0)
        self.AddButton(self.BTON_E_MIN, flags=c4d.BFH_MASK, initw=0, inith=0, name="copier")
        self.AddStaticText(1005, name="", flags=c4d.BFH_MASK, initw=200)
        self.AddStaticText(1004, name="Ouest :", flags=c4d.BFH_MASK, initw=50)
        self.AddEditNumber(self.E_MAX, flags=c4d.BFH_MASK, initw=self.LARG_COORD, inith=0)
        self.AddButton(self.BTON_E_MAX, flags=c4d.BFH_MASK, initw=0, inith=0, name="copier")
        self.GroupEnd()

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.AddStaticText(1002, name="Sud :", flags=c4d.BFH_MASK, initw=50)
        self.AddEditNumber(self.N_MIN, flags=c4d.BFH_MASK, initw=self.LARG_COORD, inith=0)
        self.AddButton(self.BTON_N_MIN, flags=c4d.BFH_MASK, initw=0, inith=0, name="copier")
        self.GroupEnd()

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, 0)

        self.AddButton(self.BTON_DRAW_RECTANGLE, flags=c4d.BFH_MASK, initw=150, inith=20, name="dessiner une emprise")
        self.AddButton(self.BTON_FROM_OBJECT, flags=c4d.BFH_MASK, initw=150, inith=20, name="depuis la sélection")
        self.AddButton(self.BTON_FROM_VIEW, flags=c4d.BFH_MASK, initw=150, inith=20, name="depuis la vue")

        self.GroupEnd()

        self.GroupBegin(500, flags=c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(self.MARGIN, 0, self.MARGIN, self.MARGIN)

        self.AddButton(self.BTON_COPY_ALL, flags=c4d.BFH_MASK, initw=150, inith=20, name="copier toutes les valeurs")
        self.AddButton(self.BTON_PLANE, flags=c4d.BFH_MASK, initw=150, inith=20, name="créer un plan")
        self.AddButton(self.BTON_EXPORT_SHP, flags=c4d.BFH_MASK, initw=150, inith=20, name="créer un shapefile")

        self.GroupEnd()

        self.AddSeparatorH( initw=150, flags=c4d.BFH_FIT)

        #CHOIX COUCHES
        self.AddStaticText(401, flags=c4d.BFH_LEFT, initw=0, inith=0, name=self.TITLE_LAYER_CHOICE, borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        self.GroupBegin(600, flags=c4d.BFH_CENTER, cols=1, rows=5)

        self.GroupBegin(601, flags=c4d.BFH_CENTER, cols=2, rows=1)
        self.AddCheckbox(self.CHECKBOX_MNT2M, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_MNT2M)
        self.AddCheckbox(self.CHECKBOX_MNT50CM, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_MNT50CM)
        self.GroupEnd()

        self.GroupBegin(606, flags=c4d.BFH_CENTER, cols=2, rows=1)
        self.AddCheckbox(self.CHECKBOX_BATI3D, flags=c4d.BFH_MASK, initw=300, inith=20, name=self.LABEL_BATI3D)
        self.AddCheckbox(self.CHECKBOX_BATI3D_V3, flags=c4d.BFH_MASK, initw=300, inith=20, name=self.LABEL_BATI3D_V3)
        self.GroupEnd()

        self.GroupBegin(600, flags=c4d.BFH_CENTER, cols=2, rows=1)
        self.AddCheckbox(self.CHECKBOX_ORTHO2M, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_ORTHO2M)
        self.AddCheckbox(self.CHECKBOX_ORTHO10CM, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_ORTHO10CM)
        self.GroupEnd()

        self.GroupBegin(605, flags=c4d.BFH_CENTER, cols=2, rows=1)
        self.AddCheckbox(self.CHECKBOX_TREES, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_TREES)
        self.AddCheckbox(self.CHECKBOX_FOREST, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_FOREST)
        self.GroupEnd()

        self.GroupBegin(650, flags=c4d.BFH_CENTER, cols=1, rows=3)
        self.GroupBorderSpace(self.MARGIN , self.MARGIN, self.MARGIN, self.MARGIN)
        self.AddStaticText(self.ID_TXT_NBRE_POLYS_MNT, flags=c4d.BFH_CENTER, initw=300, inith=20, name='nombre polygones MNT', borderstyle=c4d.BORDER_WITH_TITLE_BOLD)
        self.AddEditNumber(self.ID_TAILLE_MAILLE_MNT, flags=c4d.BFH_MASK, initw=100, inith=20)
        self.AddCheckbox(self.ID_CHECKBOX_CUT_WITH_SPLINE, flags=c4d.BFH_MASK, initw=300, inith=20, name=self.TXT_CUT_WITH_SPLINE)
        self.GroupEnd()

        self.GroupEnd()

        # LISTE DES TELECHARGEMNT
        self.AddStaticText(701, flags=c4d.BFH_LEFT, initw=0, inith=0, name=self.TITLE_LIST_TO_DOWNLOAD, borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        self.GroupBegin(700, flags=c4d.BFH_CENTER, cols=1, rows=2)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.AddCheckbox(self.CHECKBOX_SWISSTOPO_FOLDER, flags=c4d.BFH_MASK, initw=150, inith=20, name=self.LABEL_SWISSTOPO_FOLDER,)
        self.AddButton(self.BTON_GET_URLS_DOWNLOAD, flags=c4d.BFH_MASK, initw=250, inith=20, name="Téléchargement")        
        self.GroupEnd()

        #BOUTON pour l'import de la maquette
        #pour qu'il s'active il faut que les fichiers soient téléchargés
        #attention pour que masquer le bouton il faut le metrre dans un groupe qui doit aussi être dans un groupe !  
        # if self.GroupBegin(self.ID_MAIN_GROUP, flags=c4d.BFH_CENTER):
        #     if self.GroupBegin(self.ID_GROUP_IMPORT_MODEL, flags=c4d.BFH_CENTER, cols=1, rows=1):
        #         self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        #         self.AddButton(self.BTON_IMPORT_MODEL, flags=c4d.BFH_MASK, initw=250, inith=20, name="Importer la maquette")
        #         self.GroupEnd()
        #     self.GroupEnd()

        #ETAT DU TELECHARGEMENT
        #self.GroupBegin(700, flags=c4d.BFH_SCALEFIT, cols=1, rows=1)
        #self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)

        self.AddStaticText(self.ID_TXT_DOWNLOAD_STATUS, flags=c4d.BFH_RIGHT, initw=500, inith=0, name="Pas de téléchargement en cours", borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        #self.GroupEnd()
        self.GroupEnd()
        return True

    def InitValues(self):
        self.doc = c4d.documents.GetActiveDocument()
        self.SetMeter(self.N_MAX, 0.0)
        self.SetMeter(self.N_MIN, 0.0)
        self.SetMeter(self.E_MIN, 0.0)
        self.SetMeter(self.E_MAX, 0.0)

        self.SetBool(self.CHECKBOX_MNT2M,True)
        self.SetBool(self.CHECKBOX_BATI3D,True)
        self.SetBool(self.CHECKBOX_BATI3D_V3,False)
        self.SetBool(self.CHECKBOX_ORTHO2M,True)
        self.SetBool(self.CHECKBOX_TREES,True)
        self.SetBool(self.CHECKBOX_FOREST,True)
        self.SetMeter(self.ID_TAILLE_MAILLE_MNT, 2.0)
        self.taille_maille = 2.0

        self.SetString(self.ID_TXT_NBRE_POLYS_MNT,self.TXT_NO_SURFACE)

        self.Enable(self.ID_CHECKBOX_CUT_WITH_SPLINE, False)

        #masquage du bouton d'import de la maquette tant que l'on n'a pas
        #téléchargé tous les fichiers
        self.HideElement(self.ID_GROUP_IMPORT_MODEL, hide = True)

        self.SetBool(self.CHECKBOX_SWISSTOPO_FOLDER,True)

        self.qgispath = getPathToQGISbin()

        if not self.qgispath:
            c4d.gui.MessageDialog(self.TXT_NO_PATH_TO_QGIS)

        return True

    def getBbox(self):
        mini = c4d.Vector()
        maxi = c4d.Vector()
        maxi.z = self.GetFloat(self.N_MAX)
        mini.z = self.GetFloat(self.N_MIN)
        maxi.x = self.GetFloat(self.E_MAX)
        mini.x = self.GetFloat(self.E_MIN)
        return mini, maxi

    def planeFromBbox(self, mini, maxi, origine):
        plane = c4d.BaseObject(c4d.Oplane)
        plane[c4d.PRIM_AXIS] = c4d.PRIM_AXIS_YP
        plane[c4d.PRIM_PLANE_SUBW] = 1
        plane[c4d.PRIM_PLANE_SUBH] = 1

        plane[c4d.PRIM_PLANE_WIDTH] = maxi.x - mini.x
        plane[c4d.PRIM_PLANE_HEIGHT] = maxi.z - mini.z

        pos = (mini + maxi) / 2 - origine

        plane.SetAbsPos(pos)
        return plane
    
    def modifBbox(self):
        self.SetMeter(self.N_MAX, self.maxi.z)
        self.SetMeter(self.N_MIN, self.mini.z)
        self.SetMeter(self.E_MIN, self.mini.x)
        self.SetMeter(self.E_MAX, self.maxi.x)
        self.majNombresPolys()
    
    def majNombresPolys(self):
        if self.maxi and self.mini:
            larg = self.maxi.x - self.mini.x
            haut = self.maxi.z - self.mini.z

            val_px = self.GetFloat(self.ID_TAILLE_MAILLE_MNT)

            if not larg or not haut or not val_px:
                self.SetString(self.ID_TXT_NBRE_POLYS_MNT,self.TXT_NO_SURFACE)
            else:
                nb_px_larg = round(round(larg /val_px,0))
                nb_px_haut = round(haut/val_px,0)
                self.total_polys = round(nb_px_larg * nb_px_haut)
                total_txt = f'{self.total_polys:,}'.replace(",","'")
                txt = f'{total_txt} polygones (boîte englobante)'
                self.SetString(self.ID_TXT_NBRE_POLYS_MNT,txt)
            
            if self.total_polys > NB_POLYGONES_MAX:
                self.SetDefaultColor(self.ID_TXT_NBRE_POLYS_MNT, c4d.COLOR_TEXT, c4d.Vector(1.0, 0, 0))
            else:
                self.SetDefaultColor(self.ID_TXT_NBRE_POLYS_MNT, c4d.COLOR_TEXT, c4d.Vector(0.0, 1.0, 0.0))


    def Command(self, id, msg):
        #########
        # 1 : GEOLOCALISATION
        #########


        # Choix du lieu
        if id == self.COMBO_LOCALISATION:
            id_lieu = self.GetInt32(self.COMBO_LOCALISATION)
            if id_lieu>0:
                id_lieu-=1
                nom_lieu = self.lst_lieux[id_lieu]
                x,z = self.dico_lieux[nom_lieu]
                pos = c4d.Vector(float(x),0,float(z))

                rep = True
                doc = c4d.documents.GetActiveDocument()
                if doc[CONTAINER_ORIGIN]:
                    rep  = c4d.gui.QuestionDialog("Le document est déjà géoréférencé voulez-vous modifier l'origine")

                if rep :
                    doc[CONTAINER_ORIGIN] = pos

                    #TODO remettre la camera au centre
                    c4d.EventAdd()

        #Affichage OrthoPhoto
        if id ==self.BTON_ORTHO:
            if c4d.plugins.FindPlugin(ID_SWISSTOPO_ORTHO_DISPLAY):
                #self.mode_draw = True
                c4d.CallCommand(ID_SWISSTOPO_ORTHO_DISPLAY)
            else:
                c4d.gui.MessageDialog(self.TXT_NO_PLUGIN_SWISSTOPO_DISPLAY)


        #Affichage CarteNationale
        if id ==self.BTON_CN:
            if c4d.plugins.FindPlugin(ID_SWISSTOPO_CN10_DISPLAY):
                #self.mode_draw = True
                c4d.CallCommand(ID_SWISSTOPO_CN10_DISPLAY)
            else:
                c4d.gui.MessageDialog(self.TXT_NO_PLUGIN_SWISSTOPO_DISPLAY)
        
        ##########################
        #EMPRISE
        ############################

        #VALEURS BBOX
        if id==self.N_MAX or id==self.N_MIN or id==self.E_MIN or id==self.E_MAX:
            zmax = self.GetFloat(self.N_MAX)
            zmin = self.GetFloat(self.N_MIN)
            xmin = self.GetFloat(self.E_MIN)
            xmax = self.GetFloat(self.E_MAX)
            self.mini = c4d.Vector(xmin,0,zmin)
            self.maxi = c4d.Vector(xmax,0,zmax)

            self.majNombresPolys()
        
        #DESSINER RECTANGLE
        if id==self.BTON_DRAW_RECTANGLE:
            if c4d.plugins.FindPlugin(ID_RECTANGLE_TOOL):
                #self.mode_draw = True
                c4d.CallCommand(ID_RECTANGLE_TOOL)
                #TODO -> récupérer directement le rectangle une fois dessiné
            else:
                c4d.gui.MessageDialog(self.TXT_NO_PLUGIN_RECTANGLE)


        # DEPUIS L'OBJET ACTIF
        # TODO : sélection multiple
        if id == self.BTON_FROM_OBJECT:
            doc = c4d.documents.GetActiveDocument()
            origine = doc[CONTAINER_ORIGIN]
            if not origine:
                c4d.gui.MessageDialog(self.TXT_NO_ORIGIN)
                return True
            op = doc.GetActiveObjects(0)
            if not op:
                c4d.gui.MessageDialog(self.TXT_NO_SELECTION)
                return True
            if len(op) > 1:
                c4d.gui.MessageDialog(self.TXT_MULTI_SELECTION)
                return True
            obj = op[0]

            self.mini, self.maxi = empriseObject(obj, origine)
            self.modifBbox()

            #si une spline est sélectionnée
            #et que ce n'est pas un rectangle Nord-Sud
            #on active le découpage par spline
            #ID_CHECKBOX_CUT_WITH_SPLINE

            sp = obj.GetRealSpline()

            #si pas de spline on regarde si on a un plan  que l'on transforme en spline découpe
            if not sp:
                if not obj.CheckType(c4d.Opoint):
                    obj = obj.GetCache()
                if obj :
                    sp = get_spline_from_plane(obj)


            if sp and not isRectangleNordSud(sp):
                self.SetBool(self.ID_CHECKBOX_CUT_WITH_SPLINE,True)
                self.Enable(self.ID_CHECKBOX_CUT_WITH_SPLINE, True)
                self.spline_cut = sp
                
            else:
                self.SetBool(self.ID_CHECKBOX_CUT_WITH_SPLINE,False)
                self.Enable(self.ID_CHECKBOX_CUT_WITH_SPLINE, False)
                self.spline_cut = None
                
            

        # DEPUIS LA VUE DE HAUT
        if id == self.BTON_FROM_VIEW:
            doc = c4d.documents.GetActiveDocument()
            origine = doc[CONTAINER_ORIGIN]
            if not origine:
                c4d.gui.MessageDialog(self.TXT_NO_ORIGIN)
                return True

            bd = doc.GetActiveBaseDraw()
            camera = bd.GetSceneCamera(doc)
            if not camera[c4d.CAMERA_PROJECTION] == c4d.Ptop:
                c4d.gui.MessageDialog(self.TXT_NOT_VIEW_TOP)
                return True

            self.mini, self.maxi, larg, haut = empriseVueHaut(bd, origine)
            self.modifBbox()

        # COPIER LES VALEURS (et print)
        if id == self.BTON_COPY_ALL:
            n_max = self.GetFloat(self.N_MAX)
            n_min = self.GetFloat(self.N_MIN)
            e_max = self.GetFloat(self.E_MAX)
            e_min = self.GetFloat(self.E_MIN)
            txt = "{0},{1},{2},{3}".format(e_min,n_min,e_max,n_max)
            print(txt)
            c4d.CopyStringToClipboard(txt)

        # CREER UN PLAN
        if id == self.BTON_PLANE:

            mini, maxi = self.getBbox()

            if mini == c4d.Vector(0) or maxi == c4d.Vector(0):
                return True
            doc = c4d.documents.GetActiveDocument()
            doc.StartUndo()
            origine = doc[CONTAINER_ORIGIN]
            if not origine:
                origine = (mini + maxi) / 2
                # pas réussi à faire un undo pour le doc !
                doc[CONTAINER_ORIGIN] = origine

            plane = self.planeFromBbox(mini, maxi, origine)
            doc.AddUndo(c4d.UNDOTYPE_NEW, plane)
            doc.InsertObject(plane)
            doc.EndUndo()
            c4d.EventAdd()

        # EXPORT SHAPEFILE
        if id == self.BTON_EXPORT_SHP:
            mini, maxi = self.getBbox()
            if mini == c4d.Vector(0) or maxi == c4d.Vector(0):
                return True

            bbox2shapefile(mini, maxi)

        # BOUTONS COPIE COORDONNEES
        if id == self.BTON_N_MIN:
            c4d.CopyStringToClipboard(str(self.GetFloat(self.N_MIN)))

        if id == self.BTON_N_MAX:
            c4d.CopyStringToClipboard(self.GetFloat(self.N_MAX))

        if id == self.BTON_E_MIN:
            c4d.CopyStringToClipboard(str(self.GetFloat(self.E_MIN)))

        if id == self.BTON_E_MAX:
            c4d.CopyStringToClipboard(str(self.GetFloat(self.E_MAX)))


        #############################################################
        # 3 CHOIX DES COUCHES
        if id == self.CHECKBOX_MNT2M:
            # si le 50 cm est actif on le désactive
            if self.GetBool(self.CHECKBOX_MNT50CM):
                self.SetBool(self.CHECKBOX_MNT50CM,False)
            self.taille_maille = 2
            self.SetMeter(self.ID_TAILLE_MAILLE_MNT,self.taille_maille)
            self.taille_maille = 2
            self.majNombresPolys()

        if id == self.CHECKBOX_MNT50CM:
            # si le 50 cm est actif on le désactive
            if self.GetBool(self.CHECKBOX_MNT2M):
                self.SetBool(self.CHECKBOX_MNT2M,False)
            self.taille_maille = 0.5
            self.SetMeter(self.ID_TAILLE_MAILLE_MNT,self.taille_maille)
            self.majNombresPolys()

        if id == self.CHECKBOX_BATI3D:
            pass

        if id == self.CHECKBOX_BATI3D_V3:
            pass

        if id == self.CHECKBOX_ORTHO2M:
            # si le 50 cm est actif on le désactive
            if self.GetBool(self.CHECKBOX_ORTHO10CM):
                self.SetBool(self.CHECKBOX_ORTHO10CM,False)

        if id == self.CHECKBOX_ORTHO10CM:
            # si le 50 cm est actif on le désactive
            if self.GetBool(self.CHECKBOX_ORTHO2M):
                self.SetBool(self.CHECKBOX_ORTHO2M,False)


        #CHANGEMENT TAILLE DE LA MAILLE
        if id==self.ID_TAILLE_MAILLE_MNT:
            self.taille_maille = self.GetFloat(self.ID_TAILLE_MAILLE_MNT)
            if self.taille_maille >=2 :
                self.SetBool(self.CHECKBOX_MNT2M,True)
                self.SetBool(self.CHECKBOX_MNT50CM,False)
            elif self.taille_maille <0.5 :
                self.SetMeter(self.ID_TAILLE_MAILLE_MNT,0.5)
                self.taille_maille = 0.5
            else:
                self.SetBool(self.CHECKBOX_MNT2M,False)
                self.SetBool(self.CHECKBOX_MNT50CM,True)

            self.majNombresPolys()

        if id == self.ID_CHECKBOX_CUT_WITH_SPLINE:
            
            if not self.GetBool(self.ID_CHECKBOX_CUT_WITH_SPLINE):
                self.spline_cut = None
            



        #############################################################
        # 4 LISTE DES TELECHARGEMENTs

        #TODO : désactiver le bouton si les coordonnées ne sont pas bonnes !

        if id == self.BTON_GET_URLS_DOWNLOAD:
            #Vérification que le fichier est enregistré
            doc = c4d.documents.GetActiveDocument()

            path_doc = doc.GetDocumentPath()

            while not path_doc:
                rep = c4d.gui.QuestionDialog(self.TXT_NOT_SAVED)
                if not rep : return True
                c4d.documents.SaveDocument(doc, "", c4d.SAVEDOCUMENTFLAGS_DIALOGSALLOWED, c4d.FORMAT_C4DEXPORT)
                c4d.CallCommand(12098) # Enregistrer le projet
                path_doc = doc.GetDocumentPath()

            #Vérification qu'on n'est pas sur le NAS de l'école
            if 'hes-nas-prairie.hes.adhes.hesge.ch' in path_doc:
                c4d.gui.MessageDialog(self.TXT_NAS_HEPIA)
                return True

            #Vérification qu'il n'y ait pas de caractères spéciaux dans le chemin !
            #GDAL ne supporte pas
            try : 
                path_doc.encode(encoding='ASCII')
            except:
                c4d.gui.MessageDialog(self.TXT_PATH_CAR_SPECIAL)
                return True




            self.qgispath = getPathToQGISbin()
            if not self.qgispath:
                rep = c4d.gui.QuestionDialog(self.TXT_NO_PATH_TO_QGIS_QUESTION)
                if not rep : return True

            bbox = self.getDialogBbox()

            if not bbox :
                c4d.gui.MessageDialog("Coordonnées non valides")
                return True

            if bbox:
                xmin,ymin,xmax,ymax = bbox
                #self.dic_downloads = {}
                urls =[]

                #MNT
                if self.GetBool(self.CHECKBOX_MNT2M) or self.GetBool(self.CHECKBOX_MNT50CM):
                    #on
                    tri = '_2_'
                    if self.GetBool(self.CHECKBOX_MNT50CM): tri = '_0.5_'

                    url = URL_STAC_SWISSTOPO_BASE+DIC_LAYERS['mnt']
                    lst = [v for v in get_list_from_STAC_swisstopo(url,xmin,ymin,xmax,ymax) if tri in v]
                    urls+= lst
                    #for v in lst : print(v)
                    #print('---------')

                #BATI3D
                if self.GetBool(self.CHECKBOX_BATI3D):
                    url = URL_STAC_SWISSTOPO_BASE+DIC_LAYERS['bati3D']
                    lst = get_list_from_STAC_swisstopo(url,xmin,ymin,xmax,ymax)

                    #enlever les doublons, il y a deux versions bati3D 2018 et 2020 !
                    lst = suppr_doublons_bati3D(lst)
                    urls+= lst
                    #for v in lst : print(v)
                    #print('---------')
                
                #BATI3D V3
                if self.GetBool(self.CHECKBOX_BATI3D_V3):
                    url = URL_STAC_SWISSTOPO_BASE+DIC_LAYERS['bati3D_v3']
                    lst = get_list_from_STAC_swisstopo(url,xmin,ymin,xmax,ymax,gdb=True)
                    urls+= lst
                    #for v in lst : print(v)
                    #print('---------')

                #ORTHO
                if self.GetBool(self.CHECKBOX_ORTHO2M) or self.GetBool(self.CHECKBOX_ORTHO10CM):
                    tri = '_2_'
                    if self.GetBool(self.CHECKBOX_ORTHO10CM):
                        tri = '_0.1_'


                    url = URL_STAC_SWISSTOPO_BASE+DIC_LAYERS['ortho']
                    lst = [v for v in get_list_from_STAC_swisstopo(url,xmin,ymin,xmax,ymax) if tri in v]
                    #suppression des doublons de feuille, on garde que la feuille la plus récente
                    lst = suppr_doublons_list_ortho(lst)
                    urls+= lst
                    #for v in lst : print(v)
                    #print('---------')


                #TELECHARGEMENT
                
                pth = None
                #si le fichier est enregistré et que
                #la case "dossier swistopo" est cochée on crée automatiquement le dossier
                if self.GetBool(self.CHECKBOX_SWISSTOPO_FOLDER) and path_doc:
                    pth = os.path.join(path_doc,FOLDER_NAME_SWISSTOPO)
                    if not os.path.isdir(pth):
                        os.mkdir(pth)
                if not pth:
                    pth = c4d.storage.LoadDialog(title = 'Dossier pour les fichiers à télécharger',def_path = doc.GetDocumentPath(),flags = c4d.FILESELECT_DIRECTORY)
                if not pth:
                    return True
                #pth = '/Users/olivierdonze/Documents/TEMP/test_dwnld_swisstopo'

                self.dirs = []

                #list de tuple url,fn_dest pour envoyer dans le Thread
                self.dwload_lst = []

                for url in urls:
                    name_file = url.split('/')[-1]
                    name_dir = name_file.split('_')[0]
                    path_dir = os.path.join(pth,name_dir)
                    if '_0.1_'in name_file:
                        path_dir+='_10cm'
                    elif '_0.5_'in name_file:
                        path_dir+='_50cm'
                    elif '_2_'in name_file and not 'swissbuildings3d' in name_file :
                        path_dir+='_2m'

                    #bricolage pour v3 de swsisbuildings3d
                    elif 'swissbuildings3d_3_0' in name_file:
                        path_dir+='_v3'
                    
                    if not os.path.isdir(path_dir):
                        os.mkdir(path_dir)

                    fn = os.path.join(path_dir,name_file)
                    name,ext = os.path.splitext(fn)

                    self.dirs.append(path_dir)

                    #si le fichier existe on ne le télécharge pas
                    #attention pour les dxf il s'agit de fichier zip qui sont ensuite décompressés!
                    #l'extension se termine par '.dxf.zip' -> je supprime seulement le .zip
                    fn_temp = fn.replace('.zip','')
                    if not os.path.isfile(fn_temp):                            
                        self.dwload_lst.append((url,fn))
                        
                    #pour les orthos c'est un peu bizarre
                    #suivant la requâte il prend des fois 2017 des fois 2020
                    # et il y a même des doublons (même tuile sur 2 années différentes)
                    #TODO si doublon de tuile garder la plus récente
                    #-> supprimer la plus ancienne si déjà téléchargée
                    #-> enlever de la liste de téléchargement si une plus récente est téléchargée
                
                #VEGETATION
                #TODO : gérer l'origine de manière globale
                #et gérer le changement de doc !
                doc = c4d.documents.GetActiveDocument()
                origine = doc[CONTAINER_ORIGIN]

                self.fn_trees = None
                self.fn_forest = None

                #ARBRES ISOLES
                if self.GetBool(self.CHECKBOX_TREES):
                    name_file = 'trees.geojson'
                    fn = fn = os.path.join(pth,name_file)

                    if self.spline_cut:
                        url = trees.url_geojson_trees(self.spline_cut,origine)
                    else:
                        url = trees.url_geojson_trees((self.mini.x,self.mini.z,self.maxi.x,self.maxi.z),origine)
                    
                    self.dwload_lst.append((url,fn))
                    self.fn_trees = fn

                #FORETS
                if self.GetBool(self.CHECKBOX_FOREST):
                    name_file = 'forest.geojson'
                    fn = fn = os.path.join(pth,name_file)

                    if self.spline_cut:
                        url = trees.url_geojson_forest(self.spline_cut,origine)
                    else:
                        url = trees.url_geojson_forest((self.mini.x,self.mini.z,self.maxi.x,self.maxi.z),origine)
                    
                    self.dwload_lst.append((url,fn))
                    self.fn_forest = fn


                #si la liste est vide on quitte et on avertit
                #if not self.dwload_lst:
                    #c4d.gui.MessageDialog(TXT_NO_FILE_TO_DOWNLOAD)
                    #return

                #stockage des infos nécessaires pour la génération de la maquette
                #dans le Timer
                self.doc = doc
                self.pth_swisstopo_data = pth
                self.bbox = bbox
                #variable pour eviter de lancer la génération de la maquette plusieurs fois
                self.gen = True

                #LANCEMENT DU THREAD
                self.thread = ThreadDownload(self.dwload_lst)
                self.thread.Start()

                #lancement du timer pour voir l'avancement du téléchargement
                self.SetTimer(500)
                return True               

        return True

    def Timer(self,msg):
        nb = 0
        for url,fn in self.dwload_lst:
            if os.path.isfile(fn):
                nb+=1

        self.SetString(self.ID_TXT_DOWNLOAD_STATUS,f'nombre de fichiers téléchargés : {nb}/{len(self.dwload_lst)}')

        #si le thread est terminé on arrête le Timer et on lance la création des vrt
        if not self.thread.IsRunning():
            self.SetTimer(0)
            self.SetString(self.ID_TXT_DOWNLOAD_STATUS,f'Téléchargement terminé')
            self.qgispath = getPathToQGISbin()

            if not self.qgispath:
                c4d.gui.MessageDialog(self.TXT_NO_PATH_TO_QGIS_FINAL)
                return 
            
            if self.gen:
                if c4d.gui.QuestionDialog(self.TXT_IMPORT_MODEL):
                    #pour éviter de lancer plusieurs fois la génération de la maquette
                    self.gen = False
                    ###################################################################
                    #IMPORTATION DE LA MAQUETTE
                    ###################################################################
                    origine = self.doc[CONTAINER_ORIGIN]
                    xmin,ymin,xmax,ymax = self.bbox

                    #Test pour ajouter une valeur de maille autour de la bbox
                    #pour obtenir au final exactement l'emprise (pas concluant)
                    #xmin -= self.taille_maille
                    xmax += self.taille_maille
                    ymin -= self.taille_maille
                    #ymax += self.taille_maille

                    mnt2m = self.GetBool(self.CHECKBOX_MNT2M)
                    mnt50cm = self.GetBool(self.CHECKBOX_MNT50CM)
                    bati3D = self.GetBool(self.CHECKBOX_BATI3D)
                    bati3D_v3 = self.GetBool(self.CHECKBOX_BATI3D_V3)
                    ortho2m = self.GetBool(self.CHECKBOX_ORTHO2M)
                    ortho10cm = self.GetBool(self.CHECKBOX_ORTHO10CM)

                    fn_doc_arbres_sources =  os.path.join(os.path.dirname(__file__),'data','__arbres_sources__.c4d')
                    arbres_sources = None
                    if os.path.isfile(fn_doc_arbres_sources):
                        
                        doc_arbres_sources = c4d.documents.LoadDocument(fn_doc_arbres_sources, c4d.SCENEFILTER_OBJECTS)
                        if doc_arbres_sources:
                            arbres_sources = doc_arbres_sources.SearchObject('sources_vegetation')


                    import_maquette(self.doc,origine,self.pth_swisstopo_data,xmin,ymin,xmax,ymax, self.taille_maille,mnt2m,mnt50cm,bati3D,bati3D_v3,ortho2m,ortho10cm,self.fn_trees, self.fn_forest,arbres_sources = arbres_sources,spline_decoupe = self.spline_cut)
                    c4d.EventAdd()

            
            

    def getDialogBbox(self):

        xmin,ymin,xmax,ymax = self.GetFloat(self.E_MIN),self.GetFloat(self.N_MIN),self.GetFloat(self.E_MAX),self.GetFloat(self.N_MAX)

        if not xmin or not xmax or not ymin or not ymax:
            return False

        if xmax<xmin : return False
        if ymax<ymin : return False

        return xmin,ymin,xmax,ymax



URL_STAC_SWISSTOPO_BASE = 'https://data.geo.admin.ch/api/stac/v0.9/collections/'

DIC_LAYERS = {'ortho':'ch.swisstopo.swissimage-dop10',
              'mnt':'ch.swisstopo.swissalti3d',
              'bati3D':'ch.swisstopo.swissbuildings3d_2',
              'bati3D_v3':'ch.swisstopo.swissbuildings3d_3_0',
              }
def main():
    dlg = DlgBbox()
    dlg.Open(c4d.DLG_TYPE_ASYNC)


# Execute main()
if __name__ == '__main__':

    #main()
    dlg = DlgBbox()
    dlg.Open(c4d.DLG_TYPE_ASYNC)