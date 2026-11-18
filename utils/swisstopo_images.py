import c4d
import os.path
import urllib.request
from utils import ortho_wms, swisstopo_background as bg
from utils.geo_extent_dialog import CONTAINER_ORIGIN, GeoExtentDialog


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

def creer_plan(nom,mat,width,height, projection= 'top'):
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

    return plan

def make_editable(op,doc):
    pred = op.GetPred()
    doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ,op)
    res = c4d.utils.SendModelingCommand(command=c4d.MCOMMAND_MAKEEDITABLE,
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

def creer_mat(fn, doc, alpha = False):
    nom = os.path.basename(fn)
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

class SwissImagesDlg(GeoExtentDialog):
    dialog_title = "swisstopo images"

    LIST_WEB_SERVICES = [
                         {'name':'Carte Dufour première édition (entre 1844 et 1864)','layer':'ch.swisstopo.hiks-dufour', 'short_name': 'Dufour', 'min_cm': 50},
                         {'name':'Carte Siegfried première édition (entre 1870 et 1926)','layer':'ch.swisstopo.hiks-siegfried', 'short_name': 'Siegfried', 'min_cm': 100},
                         {'name':'Orthophoto 1946','layer':'ch.swisstopo.swissimage-product_1946', 'short_name': 'ortho_46', 'min_cm': 100},
                         {'name':'Orthophoto 10cm','layer':'ch.swisstopo.images-swissimage', 'short_name': 'ortho_actuelle', 'min_cm': 10},
                         {'name':"Carte nationale grise 1:10'000",'layer':'ch.swisstopo.landeskarte-grau-10', 'short_name': 'cn10_gris', 'min_cm': 25},
                         {'name':"Carte nationale couleur 1:10'000",'layer':'ch.swisstopo.landeskarte-farbe-10', 'short_name': 'cn10_clr', 'min_cm': 25},
                         {'name':"Carte nationale couleur 1:25'000",'layer':'ch.swisstopo.pixelkarte-farbe-pk25.noscale', 'short_name': 'cn25_clr', 'min_cm': 50},
                         {'name':"Carte nationale couleur 1:50'000",'layer':'ch.swisstopo.pixelkarte-farbe-pk50.noscale', 'short_name': 'cn50_clr', 'min_cm': 50},
                         {'name':"Carte nationale couleur échelle auto",'layer':'ch.swisstopo.pixelkarte-farbe', 'short_name': 'cn_clr_auto', 'min_cm': 25},
                         {'name':"Carte nationale grise échelle auto",'layer':'ch.swisstopo.pixelkarte-grau', 'short_name': 'cn_gris_auto', 'min_cm': 25},
                         {'name':"Atlas géologique AG25",'layer':'ch.swisstopo.geologie-geologischer_atlas', 'short_name': 'atlas_geol', 'min_cm': 50},
                        ]

    # Published LV95 WMTS pyramid bounds, in cm/pixel. SWISSIMAGE uses the 10 cm grid.
    MAX_CM = 400000

    ID_LST_CHOIX_IMG = 2100
    ID_BTON_DISPLAY = 2101
    ID_TAILLE_MAILLE = 2102
    DIMENSIONS = 2103
    ID_BTON_REQUEST = 2106
    TXT_FILE_EXIST = "Il semble que le fichier mage existe déjà, voulez vous continuer ?"
    TXT_DOWNLOAD_PROBLEM = "Problème lors du téléchargement de l'image"
    TXT_FILE_CREATION_PROBLEM = "Problème lors de la création du fichier image"

    def add_extraction_sections(self):
        self.AddStaticText(0, c4d.BFH_LEFT, name=self.TITLE_LAYER_CHOICE,
                           borderstyle=c4d.BORDER_WITH_TITLE_BOLD)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.GroupSpace(0, self.MARGIN)
        self.AddComboBox(self.ID_LST_CHOIX_IMG, c4d.BFH_SCALEFIT)
        for index, service in enumerate(self.LIST_WEB_SERVICES, 1):
            self.AddChild(self.ID_LST_CHOIX_IMG, index, service["name"])
        self.AddRadioButton(self.ID_BTON_DISPLAY, c4d.BFH_CENTER, name="Afficher dans la vue de haut")
        self.GroupEnd()
        self.AddSeparatorH(initw=150, flags=c4d.BFH_FIT)
        self.AddStaticText(0, c4d.BFH_LEFT, name=self.TITLE_LIST_TO_DOWNLOAD,
                           borderstyle=c4d.BORDER_WITH_TITLE_BOLD)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=1)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.GroupSpace(0, self.MARGIN)
        self.GroupBegin(0, c4d.BFH_LEFT, cols=2)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Résolution (cm/pixel)")
        self.AddEditNumberArrows(self.ID_TAILLE_MAILLE, c4d.BFH_LEFT, initw=85)
        self.GroupEnd()
        self.AddStaticText(self.DIMENSIONS, c4d.BFH_SCALEFIT, initw=440, name=" ")
        self.AddButton(self.ID_BTON_REQUEST, c4d.BFH_CENTER, initw=300, inith=25, name="Importer l’image")
        self.GroupEnd()

    def InitValues(self):
        self.preferred_cm = None
        self.SetInt32(self.ID_LST_CHOIX_IMG, 1)
        return super().InitValues()

    def service(self):
        return self.LIST_WEB_SERVICES[self.GetInt32(self.ID_LST_CHOIX_IMG) - 1]

    def document_changed(self):
        self.extent_changed()

    def extent_changed(self, edited=False):
        service = self.service()
        lo, hi = self.getBbox()
        bounds = lo.x, lo.z, hi.x, hi.z
        valid = hi.x > lo.x and hi.z > lo.z
        minimum = service["min_cm"]
        if valid:
            minimum = ortho_wms.grid(bounds, 0, minimum)[0]
        if edited:
            value = self.GetInt32(self.ID_TAILLE_MAILLE)
            self.preferred_cm = value if value > minimum else None
        usable = valid and minimum <= self.MAX_CM
        cm = min(self.MAX_CM, max(minimum, self.preferred_cm or 0))
        self.SetInt32(self.ID_TAILLE_MAILLE, cm, min(minimum, self.MAX_CM), self.MAX_CM, 1)
        self.Enable(self.ID_TAILLE_MAILLE, usable)
        self.Enable(self.ID_BTON_REQUEST, usable)
        if usable:
            self.grid = ortho_wms.grid(bounds, cm, minimum)
            _, width, height = self.grid
            label = f"{width:,} × {height:,} pixels".replace(",", " ")
        else:
            self.grid = None
            label = "Définissez une emprise" if not valid else "Emprise trop grande"
        self.SetString(self.DIMENSIONS, f"{label}   ·   {minimum:,} à {self.MAX_CM:,} cm/pixel".replace(",", " "))

    def active_background(self):
        doc = c4d.documents.GetActiveDocument()
        return bg.selected(doc, doc.GetActiveBaseDraw())

    def refresh_background_choice(self):
        super().refresh_background_choice()
        active = self.active_background()
        self.SetBool(self.ID_BTON_DISPLAY, isinstance(active, str))
        if isinstance(active, str) and self.service()["layer"] != active:
            for index, service in enumerate(self.LIST_WEB_SERVICES, 1):
                if service["layer"] == active:
                    self.SetInt32(self.ID_LST_CHOIX_IMG, index)
                    self.extent_changed()
                    break

    def handle_command(self, id, msg):
        layer = self.service()["layer"]
        if id == self.ID_BTON_DISPLAY:
            active = self.active_background()
            bg.toggle(active if isinstance(active, str) else layer)
            self.refresh_background_choice()
        elif id == self.ID_LST_CHOIX_IMG:
            if isinstance(self.active_background(), str):
                bg.select(layer)
            self.refresh_background_choice()
            self.extent_changed()
        elif id == self.ID_BTON_REQUEST:
            if self.grid:
                self.extract_IMG()
        elif id == self.ID_TAILLE_MAILLE:
            self.extent_changed(edited=True)
        else:
            return super().handle_command(id, msg)
        return True

    def extract_IMG(self):

        doc = c4d.documents.GetActiveDocument()
        sr = '2056'
        format = 'png'
        #test
        mini, maxi = self.getBbox()
        xmin,ymin,xmax,ymax = mini.x,mini.z,maxi.x,maxi.z
        if doc[CONTAINER_ORIGIN] is None:
            c4d.gui.MessageDialog(self.TXT_NO_ORIGIN)
            return
        cm, width, height = self.grid
        xmax = xmin + width * cm / 100
        ymin = ymax - height * cm / 100
        choix_list = self.GetInt32(self.ID_LST_CHOIX_IMG)
        #print(self.LIST_WEB_SERVICES(choix_list-1)['url_base'])
        service = self.LIST_WEB_SERVICES[choix_list-1]
        layer = service['layer']
        

        short_name =service['short_name'] 
        name = service['name'] #.lower().replace(' ','_')
        name_img = f'{short_name}_{round(xmin)}_{round(ymin)}_{round(xmax)}_{round(ymax)}_{cm}cm.{format}'

        pth_dir = tex_folder(doc, subfolder = 'swisstopo_images')
        if not pth_dir:
            c4d.gui.MessageDialog("Enregistrez le document avant d’importer une image.")
            return
        fn_img = os.path.join(pth_dir,name_img)

        if os.path.isfile(fn_img):
            if not c4d.gui.QuestionDialog(self.TXT_FILE_EXIST):
                return None

        #url = f'{url_base}export?bbox={xmin},{ymin},{xmax},{ymax}&format={format}&size={width},{height}&f=image&bboxSR={sr}&imageSR={sr}'#.format(bbox,size,bboxSR,imageSR)
        url = f'https://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS={layer}&STYLES=default&CRS=EPSG:2056&BBOX={xmin},{ymin},{xmax},{ymax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/png'

        try :
            x = urllib.request.urlopen(url)
        
        except :
            c4d.gui.MessageDialog(self.TXT_DOWNLOAD_PROBLEM)
            return None

        try:
            with open(fn_img,'wb') as saveFile:
                saveFile.write(x.read())
        except :
            c4d.gui.MessageDialog(self.TXT_FILE_CREATION_PROBLEM)
            return None

        if not os.path.isfile(fn_img):
            return None
        
        doc.StartUndo()

        #création du matériau
        mat = creer_mat(fn_img, doc, alpha = False)
        doc.InsertMaterial(mat)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mat)

        plan = creer_plan(name,mat,(xmax-xmin),(ymax-ymin), projection= 'top')
        centre = c4d.Vector((xmax+xmin)/2,0,(ymax+ymin)/2) - doc[CONTAINER_ORIGIN]
        plan.SetAbsPos(centre)
        doc.InsertObject(plan)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,plan)

        plan_edit = make_editable(plan,doc)

        doc.EndUndo()
        c4d.EventAdd()
        

        return True





def main():
    global dlg
    dlg = SwissImagesDlg()
    dlg.Open(c4d.DLG_TYPE_ASYNC)

# Execute main()
if __name__=='__main__':
    main()
