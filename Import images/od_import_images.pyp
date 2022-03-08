import c4d
import os
import sys
from c4d import utils
import re
import os.path
from os import listdir
from os.path import isfile, join, basename

sys.path.append(os.path.dirname(__file__))
import png

# Be sure to use a unique ID obtained from www.plugincafe.com
ID_IMPORT_IMAGE_FILE = 1059133
ID_IMPORT_IMAGES_FOLDER = 1059134

DIC_TYPES = {'top':['top','haut','plan','carte'],
             'front':['coupe','elevation','face','profil','section','front','avant','perspective','vue','pers','croquis','dessin'],
             }

EXTENSIONS = ['.jpg','.png','.psd','.tif']

CODE_SCALE = 'ech' #example ech1000 -> 1/1000

CODE_RESOLUTION = 'dpi' #example 300dpi

DEFAULT_PROJECTION = 'top'
DEFAULT_SCALE = 500
DEFAULT_RESOLUTION = 300


TXT_DIRECTORY_CHOICE = "Dossier contenant les images"
TXT_FILE_CHOICE = "Fichier image"

TXT_NOT_INEXTENSIONS = f"Le fichier n'est pas un fichier image valide {str(EXTENSIONS).replace('[','(').replace(']',')')}"
TXT_NON_METRIC_DOC = "Le document n'est pas en système métrique, les échelles ne seront pas respectées, voulez-vous continuer ?"


COLOR_SCALE_AND_RESOLUTION = c4d.Vector(0,1,0)

#si jamais il y a le module unidecode
#qui fait ça très bien, mais il faut l'installer !
#unidecode.unidecode(texte_unicode)
def suppr_accents(txt):
    dico = { 'éèêẽ' : 'e',
             'ç'    : 'c',
             'àâãä' : 'a',
             'ù'    : 'u',
            }
    res = ''
    for car in txt:
        for k in dico:
            if car in k:
                car = dico[k]
                break
        res += car

    return res

def get_image_files(pth):
    """renvoie une liste des fichiers dont l'extension est
       présente dans la constante EXTENSIONS"""
    res = []

    for f in listdir(pth):
        if isfile(join(pth, f)):
            if f[-4:] in EXTENSIONS:
                res.append(os.path.join(pth,f))

    return res

def get_info_from_fn(fn):
    """renvoie projection,scale,resolution contenu dans le nom,
       si pas trouvé renvoie une valeur None pour chaque paramètre.
       projection -> selon liste de valeurs de DIC_TYPES
       resolution -> integer d'après série de chiffre après CODE_SCALE
       scale -> integer d'après série de chiffre avant CODE_RESOLUTION
       """
    txt = basename(fn)

    #suppression des accents
    txt = suppr_accents(txt)

    #type de projection
    projection = None
    for k,lst in DIC_TYPES.items():
        for name in lst:
            if name in txt :
                projection = k

    #extraction de l'échelle par ex ECH500 ech500 éch500 ...'
    scale = None
    p = re.compile(f'{CODE_SCALE}[0-9,/,]+', re.IGNORECASE)
    req = re.search(p,txt)
    if req:
        try : scale = int(req.group()[len(CODE_SCALE):])
        except:
            print(f"problème avec scale : {txt}")

    #extraction de la résolution par ex 220dpi 300DPI
    p2 = re.compile(f'[0-9]+{CODE_RESOLUTION}', re.IGNORECASE)

    resolution = None
    req = re.search(p2,txt)
    if req:
        try : resolution=int(req.group()[:-len(CODE_RESOLUTION)])
        except:
            print(f"problème avec resolution : {txt}")

    return projection,scale,resolution

def creer_mat(fn, doc, alpha = False):
    nom = basename(fn)
    relatif = False
    docpath = doc.GetDocumentPath()
    if docpath:
        relatif = c4d.IsInSearchPath(nom, docpath)
        #print(nom,relatif)
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(nom)
    shd = c4d.BaseList2D(c4d.Xbitmap)

    if relatif:
        shd[c4d.BITMAPSHADER_FILENAME] = nom
    else:
        shd[c4d.BITMAPSHADER_FILENAME] = fn

    mat[c4d.MATERIAL_COLOR_SHADER] = shd
    mat[c4d.MATERIAL_USE_REFLECTION] = False
    mat[c4d.MATERIAL_COLOR_MODEL] = c4d.MATERIAL_COLOR_MODEL_ORENNAYAR
    mat.InsertShader(shd)
    mat[c4d.MATERIAL_USE_SPECULAR]=False

    #on teste si il y a une couche alpha
    #le jpg ne peut pas contenir d'alpha'
    if fn[:-4] != '.jpg':
        bmp = c4d.bitmaps.BaseBitmap()

        result, isMovie = bmp.InitWith(fn)
        if result == c4d.IMAGERESULT_OK: #int check

            if bmp.GetInternalChannel(): alpha = True
        bmp.FlushAll()

    if alpha :
        mat[c4d.MATERIAL_USE_ALPHA]=True
        shda = c4d.BaseList2D(c4d.Xbitmap)
        if relatif:
            shda[c4d.BITMAPSHADER_FILENAME] = nom
        else:
            shda[c4d.BITMAPSHADER_FILENAME] = fn
        mat[c4d.MATERIAL_ALPHA_SHADER]=shda
        mat.InsertShader(shda)

    mat.Message(c4d.MSG_UPDATE)
    mat.Update(True, True)
    return mat


def creer_plan(nom,mat,width,height, projection):
    plan = c4d.BaseObject(c4d.Oplane)
    plan.SetName(nom)
    plan[c4d.PRIM_PLANE_WIDTH]=width
    plan[c4d.PRIM_PLANE_HEIGHT]=height
    plan[c4d.PRIM_PLANE_SUBW]=1
    plan[c4d.PRIM_PLANE_SUBH]=1

    if projection == 'top':
        plan[c4d.PRIM_AXIS]=c4d.PRIM_AXIS_YP
    elif projection == 'front':
        plan[c4d.PRIM_AXIS]=c4d.PRIM_AXIS_ZN
    tag = c4d.TextureTag()
    tag.SetMaterial(mat)
    tag[c4d.TEXTURETAG_PROJECTION]=c4d.TEXTURETAG_PROJECTION_UVW
    plan.InsertTag(tag)

    return plan #doc.InsertObject(plan)

def png_get_size_in_meter(fn_png):
    """ renvoie la taille en mètres d'un fichier png ou None si pas trouvé
        attention il n'y a pas toujours l'info 'physical' en général si on
        réenregistre l'image sous dans psd cela fonctionne
        attention2 : utilise la lib png (un seul fichier png.py)"""
    with open(fn_png,'rb') as f:
        r=png.Reader(file=f)
        width,height,rows,info = r.read()
        #pprint(info)
        alpha = info.get('alpha',-1)
        #print(alpha)
        resol = info.get('physical',None)
        #print(resol)
        if resol:
            #print(resol.unit_is_meter)
            if resol.unit_is_meter:
                #dimensions en mètres
                largeur = width/resol.x
                hauteur = height/resol.y
                #print(largeur,hauteur)
            else:
                # à tester avec un exemple
                # j'ai supposé que cela donne des pouces -> /2.54'
                largeur = width/resol.x/2.54
                hauteur = height/resol.y/2.54
                #print(largeur,hauteur)
            #print(largeur,hauteur,alpha)
            return largeur,hauteur,alpha
    return None

def make_editable(op,doc):
    pred = op.GetPred()
    doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ,op)
    res = utils.SendModelingCommand(command=c4d.MCOMMAND_MAKEEDITABLE,
                            list=[op],
                            mode=c4d.MODELINGCOMMANDMODE_ALL,
                            bc=c4d.BaseContainer(),
                            doc=doc)

    if res:
        res = res[0]
        if res:
            doc.InsertObject(res, pred = pred)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,res)
            doc.SetActiveObject(res)
            return res

    return None


# Main function
def importImages(file = False):
    doc = c4d.documents.GetActiveDocument()

    usdata = doc[c4d.DOCUMENT_DOCUNIT]

    scale, unit = usdata.GetUnitScale()

    dic_units = {c4d.DOCUMENT_UNIT_KM:0.001,
                 c4d.DOCUMENT_UNIT_M:1,
                 c4d.DOCUMENT_UNIT_CM:100,
                 c4d.DOCUMENT_UNIT_MM:1,
                 }
    facteur_units = dic_units.get(unit,None)
    if not facteur_units:
        #si on n'est pas en système métrique soit on arrête
        #soit le facteur est mis à 1
        if c4d.gui.QuestionDialog(TXT_NON_METRIC_DOC):
            facteur_units =1
        else: return

    lst_files = []
    #choix dossier
    if not file :
        path = c4d.storage.LoadDialog(flags = c4d.FILESELECT_DIRECTORY, title = TXT_DIRECTORY_CHOICE )
        if not path : return
        lst_files = get_image_files(path)


    #ou choix fichier
    else:
        fn = c4d.storage.LoadDialog(type = c4d.FILESELECTTYPE_IMAGES, title = TXT_FILE_CHOICE)
        if not fn : return
        #TODO vérifier que c'est bien un fichier image'
        if not fn[-4:] in EXTENSIONS:
            c4d.gui.MessageDialog(TXT_NOT_INEXTENSIONS)
            return

        lst_files.append(fn)

    #Parcours des images
    dic_planes = {}
    doc.StartUndo()
    for fn in lst_files:
        largeur,hauteur = 0,0

        alpha = -1

        # si c'est un png on essaie de récupèrer directement la taille via la lib png
        if fn[-4:]=='.png':
            rep = png_get_size_in_meter(fn)
            if rep:
                largeur,hauteur, alpha = rep

        #print(largeur,hauteur)

        #récupération des différentes valeurs depuis le nom
        projection,scale,resolution = get_info_from_fn(fn)
        #print(projection,scale,resolution)

        #valeurs par defaut si pas renseigné
        #on met une couleur d'icônedifférente pour chaque cas de figure
        color = None
        if projection and scale:
            color = COLOR_SCALE_AND_RESOLUTION
        if not projection : projection= DEFAULT_PROJECTION
        if not scale : scale = DEFAULT_SCALE
        if not resolution : resolution = DEFAULT_RESOLUTION
        #print(projection,scale,resolution)

        # si on n'a pas réussi à récupérer ces valeurs
        # on utilise BaseBitmap
        if not largeur or not hauteur or alpha==-1:
            bmp = c4d.bitmaps.BaseBitmap()

            result, isMovie = bmp.InitWith(fn)
            if result == c4d.IMAGERESULT_OK: #int check
                width,height = bmp.GetSize()
                #TODO -> voir dans quelles unité on est par rapport au doc !!!
                if not largeur or not hauteur:
                    largeur = width / resolution * scale/2.54
                    hauteur = height/ resolution * scale/2.54
                else:
                    largeur *=scale
                    hauteur *=scale

                #on regarde s'il y a une couche alpha'
                if bmp.GetInternalChannel():
                    alpha = True
                else:
                    alpha = None

            else:
                print(f'problème de lecture de fichier  : {basename(fn)}')


            #print('----')
            bmp.FlushAll()
        else:
            largeur*=scale
            hauteur*=scale

        #adaptation des dimensions selon l'unité du document
        largeur*=facteur_units
        hauteur*=facteur_units

        mat = creer_mat(fn,doc,alpha)
        doc.InsertMaterial(mat)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mat)

        nom = basename(fn)
        plan = creer_plan(nom,mat,largeur,hauteur,projection)

        #Tag d'affichage en mode constant
        display_tag = c4d.BaseTag(c4d.Tdisplay)
        display_tag[c4d.DISPLAYTAG_AFFECT_DISPLAYMODE] = True
        display_tag[c4d.DISPLAYTAG_SDISPLAYMODE] = c4d.DISPLAYTAG_SDISPLAY_FLAT_WIRE
        plan.InsertTag(display_tag)

        # si on a une couleur c'est que l'échelle et la résol sont normalement OK
        #on l'indique par la couleur de l'icône
        if color:
            plan[c4d.ID_BASELIST_ICON_COLORIZE_MODE] = c4d.ID_BASELIST_ICON_COLORIZE_MODE_CUSTOM
            plan[c4d.ID_BASELIST_ICON_COLOR] = color

        #on stocke les plans selon leur orientation
        dic_planes.setdefault(plan[c4d.PRIM_AXIS],[]).append(plan)

        #doc.InsertObject(plan)
        #doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,plan)

    #insertion des plans
    pred = None
    for orient,planes in dic_planes.items():
        pos = c4d.Vector(0)
        for plan in planes:
            color = plan[c4d.ID_BASELIST_ICON_COLOR]
            pos.x+=plan[c4d.PRIM_PLANE_WIDTH]/2
            plan.SetAbsPos(pos)
            pos.x +=plan[c4d.PRIM_PLANE_WIDTH]/2
            doc.InsertObject(plan, pred = pred)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,plan)
            plan_edit = make_editable(plan,doc)
            if color:
                plan_edit[c4d.ID_BASELIST_ICON_COLORIZE_MODE] = c4d.ID_BASELIST_ICON_COLORIZE_MODE_CUSTOM
                plan_edit[c4d.ID_BASELIST_ICON_COLOR] = color

            pred = plan


    doc.EndUndo()
    c4d.EventAdd()



class ImportImagesFile(c4d.plugins.CommandData):
    def Execute(self, doc):
        importImages(file = True)
        return True

class ImportImagesFolder(c4d.plugins.CommandData):
    def Execute(self, doc):
        importImages(file = False)
        return True

def icone(nom) :
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", nom)
    bmp.InitWith(fn)
    return bmp

# main
if __name__ == "__main__":
    # Registers the plugin
    c4d.plugins.RegisterCommandPlugin(id=ID_IMPORT_IMAGE_FILE,
                                      str="#$01Importer une image",
                                      info=0,
                                      help="Importe une image sous forme de plan",
                                      dat=ImportImagesFile(),
                                      icon=icone("import_image.tif"))
    c4d.plugins.RegisterCommandPlugin(id=ID_IMPORT_IMAGES_FOLDER,
                                      str="#$02Importer un dossier d'images",
                                      info=0,
                                      help="Importe un dossier d'images sous forme de plans",
                                      dat=ImportImagesFolder(),
                                      icon=icone("import_dossier_images.tif"))
