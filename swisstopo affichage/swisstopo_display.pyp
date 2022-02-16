import c4d, os, sys
import urllib.request
#from c4d import plugins, bitmaps, gui, documents, Vector
from c4d.plugins import GeLoadString as txt
from datetime import datetime

__version__ = 1.0
__date__    = "26/09/2021"


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


#ch.swisstopo.landeskarte-farbe-10

#ch.swisstopo.images-swissimage

#exemples de requetes:

#http://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=ch.swisstopo.landeskarte-farbe-10&STYLES=default&CRS=EPSG:2056&BBOX=2569660.0,1228270.0,2578660.0,1233270.0&WIDTH=900&HEIGHT=500&FORMAT=image/png
#http://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=ch.swisstopo.images-swissimage&STYLES=default&CRS=EPSG:2056&BBOX=2569660.0,1228270.0,2578660.0,1233270.0&WIDTH=900&HEIGHT=500&FORMAT=image/png

FORMAT = 'png'

NOM_DOSSIER_IMG = 'tex/__back_image'

def empriseVueHaut(bd,origine):

    dimension = bd.GetFrame()
    largeur = dimension["cr"]-dimension["cl"]
    hauteur = dimension["cb"]-dimension["ct"]

    mini =  bd.SW(c4d.Vector(0,hauteur,0)) + origine
    maxi = bd.SW(c4d.Vector(largeur,0,0)) + origine

    return  mini,maxi,largeur,hauteur

def display_wms_swisstopo(layer):
    
    #le doc doit être en mètres
    doc = c4d.documents.GetActiveDocument()

    usdata = doc[c4d.DOCUMENT_DOCUNIT]
    scale, unit = usdata.GetUnitScale()
    if  unit!= c4d.DOCUMENT_UNIT_M:
        rep = c4d.gui.QuestionDialog(DOC_NOT_IN_METERS_TXT)
        if not rep : return
        unit = c4d.DOCUMENT_UNIT_M
        usdata.SetUnitScale(scale, unit)
        doc[c4d.DOCUMENT_DOCUNIT] = usdata

    #si le document n'est pas enregistré on enregistre
    path_doc = doc.GetDocumentPath()

    while not path_doc:
        rep = c4d.gui.QuestionDialog(NOT_SAVED_TXT)
        if not rep : return
        c4d.documents.SaveDocument(doc, "", c4d.SAVEDOCUMENTFLAGS_DIALOGSALLOWED, c4d.FORMAT_C4DEXPORT)
        c4d.CallCommand(12098) # Enregistrer le projet
        path_doc = doc.GetDocumentPath()

    dossier_img = os.path.join(path_doc,NOM_DOSSIER_IMG)

    origine = doc[CONTAINER_ORIGIN]
    if not origine:
        doc[CONTAINER_ORIGIN] = O_DEFAUT
        origine = doc[CONTAINER_ORIGIN]
    bd = doc.GetActiveBaseDraw()
    camera = bd.GetSceneCamera(doc)
    if not camera[c4d.CAMERA_PROJECTION]== c4d.Ptop:
        c4d.gui.MessageDialog("""Ne fonctionne qu'avec une caméra en projection "haut" """)
        return
    
    #pour le format de la date regarder : https://docs.python.org/fr/3/library/datetime.html#strftime-strptime-behavior
    dt = datetime.now()
    suffixe_time = dt.strftime("%y%m%d_%H%M%S")

    fn = f'ortho{suffixe_time}.png'
    fn_img = os.path.join(dossier_img,fn)
    
    if not os.path.isdir(dossier_img):
            os.makedirs(dossier_img)
    
    mini,maxi,width_img,height_img = empriseVueHaut(bd,origine)
    #print (mini.x,mini.z,maxi.x,maxi.z)
    bbox = f'{mini.x},{mini.z},{maxi.x},{maxi.z}'
    
    url = f'http://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS={layer}&STYLES=default&CRS=EPSG:2056&BBOX={bbox}&WIDTH={width_img}&HEIGHT={height_img}&FORMAT=image/png'
    #print(url)
    
    
    
    try:
        x = urllib.request.urlopen(url)
    
        with open(fn_img,'wb') as saveFile:
            saveFile.write(x.read())
            
    except Exception as e:
        print(str(e))
        
    #on récupère l'ancienne image
    old_fn = os.path.join(dossier_img,bd[c4d.BASEDRAW_DATA_PICTURE])

    bd[c4d.BASEDRAW_DATA_PICTURE] = fn
    bd[c4d.BASEDRAW_DATA_SIZEX] = maxi.x-mini.x
    bd[c4d.BASEDRAW_DATA_SIZEY] = maxi.z-mini.z


    bd[c4d.BASEDRAW_DATA_OFFSETX] = (maxi.x+mini.x)/2 -origine.x
    bd[c4d.BASEDRAW_DATA_OFFSETY] = (maxi.z+mini.z)/2-origine.z
    #bd[c4d.BASEDRAW_DATA_SHOWPICTURE] = False

    #suppression de l'ancienne image
    #TODO : s'assurer que c'est bien une image générée NE PAS SUPPRIMER N'IMPORTE QUOI !!!
    if os.path.exists(old_fn):
        try : os.remove(old_fn)
        except : pass
    c4d.EventAdd(c4d.EVENT_FORCEREDRAW)
    

class DisplayOrtho(c4d.plugins.CommandData):
    def Execute(self, doc) :
        display_wms_swisstopo(LYR_ORTHO)
        return True

class DisplayCN10(c4d.plugins.CommandData):
    def Execute(self, doc) :
        display_wms_swisstopo(LYR_CN10)
        return True
class DisplayCN25(c4d.plugins.CommandData):
    def Execute(self, doc) :
        display_wms_swisstopo(LYR_CN25)
        return True

class DisplayCN50(c4d.plugins.CommandData):
    def Execute(self, doc) :
        display_wms_swisstopo(LYR_CN50)
        return True

def icone(nom) :
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", nom)
    bmp.InitWith(fn)
    return bmp
    
if __name__=='__main__':
    c4d.plugins.RegisterCommandPlugin(id=ID_ORTHO, str="#$00"+"orthophoto",
                                      info=0, help="", dat=DisplayOrtho(),
                                      icon=icone("ortho.png"))
    c4d.plugins.RegisterCommandPlugin(id=ID_CN10, str="#$01"+"carte nationale 10'000",
                                      info=0, help="", dat=DisplayCN10(),
                                      icon=icone("cn10.png"))

    c4d.plugins.RegisterCommandPlugin(id=ID_CN25, str="#$02"+"carte nationale 25'000",
                                      info=0, help="", dat=DisplayCN25(),
                                      icon=icone("cn25.png"))
    c4d.plugins.RegisterCommandPlugin(id=ID_CN50, str="#$03"+"carte nationale 50'000",
                                      info=0, help="", dat=DisplayCN50(),
                                      icon=icone("cn50.png"))