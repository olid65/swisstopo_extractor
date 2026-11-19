"""Extraction d'images swisstopo, collections et import Standard/Redshift."""
import c4d
from pathlib import Path
import os.path
import urllib.request
import urllib.parse
import math
import webbrowser
from utils import ortho_wms, swisstopo_background as bg
from utils.geo_extent_dialog import CONTAINER_ORIGIN, GeoExtentDialog
from utils.swisstopo_images_controls import LayerControls


def swisstopo_map_url(bounds, viewport=(1000, 700)):
    """Cadre estimé pour une carte web de 1000 x 700 pixels, avec 10 % de marge."""
    xmin, ymin, xmax, ymax = bounds
    if not all(math.isfinite(v) for v in bounds) or xmax <= xmin or ymax <= ymin:
        raise ValueError("Définissez une emprise valide avant d’ouvrir la carte.")
    # Pyramide LV95 du viewer officiel (SwissCoordinateSystem.ts).
    resolutions = (650, 500, 250, 100, 50, 20, 10, 5, 2.5, 2, 1, .5, .25, .1)
    resolution = max((xmax - xmin) / viewport[0], (ymax - ymin) / viewport[1]) * 1.1
    zoom = 0.0
    if resolution <= resolutions[-1]:
        zoom = float(len(resolutions) - 1)
    elif resolution < resolutions[0]:
        for index, (coarse, fine) in enumerate(zip(resolutions, resolutions[1:])):
            if coarse >= resolution >= fine:
                zoom = index + math.log(coarse / resolution) / math.log(coarse / fine)
                break
    return ("https://map.geo.admin.ch/#/map?lang=fr"
            f"&center={(xmin + xmax) / 2:.2f},{(ymin + ymax) / 2:.2f}"
            f"&z={zoom:.3f}")


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

def apply_map_material(doc, obj, material, bounds):
    """Projection de dessus dans le repère géographique, adaptée au repère de l'objet."""
    xmin, ymin, xmax, ymax = bounds
    world = c4d.utils.HPBToMatrix(c4d.Vector(0, -math.pi / 2, 0))
    world.off = c4d.Vector((xmin+xmax)/2, 0, (ymin+ymax)/2) - doc[CONTAINER_ORIGIN]
    world.v1 *= (xmax-xmin)/2
    world.v2 *= (ymax-ymin)/2
    tag = c4d.TextureTag()
    tag.SetMaterial(material)
    tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_FLAT
    tag[c4d.TEXTURETAG_TILE] = False
    tag.SetMl(~obj.GetMg() * world)
    tags = obj.GetTags()
    obj.InsertTag(tag, tags[-1] if tags else None)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
    return tag


def creer_mat_redshift(fn, doc):
    """Matériau non inséré : l'appelant gère l'insertion et l'annulation."""
    import maxon
    core = 'com.redshift3d.redshift4c4d.nodes.core.'
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(Path(fn).stem + ' RS')
    graph = mat.GetNodeMaterialReference().CreateEmptyGraph(
        maxon.Id('com.redshift3d.redshift4c4d.class.nodespace'))
    with graph.BeginTransaction() as transaction:
        shader = graph.AddChild(maxon.Id(), maxon.Id(core + 'standardmaterial'))
        output = graph.AddChild(maxon.Id(), maxon.Id('com.redshift3d.redshift4c4d.node.output'))
        texture = graph.AddChild(maxon.Id(), maxon.Id(core + 'texturesampler'))
        path = os.path.relpath(fn, doc.GetDocumentPath()).replace(os.sep, '/') if doc.GetDocumentPath() else fn
        texture.GetInputs().FindChild(core + 'texturesampler.tex0').FindChild('path').SetPortValue(maxon.Url(path))
        texture.GetOutputs().FindChild(core + 'texturesampler.outcolor').Connect(
            shader.GetInputs().FindChild(core + 'standardmaterial.base_color'))
        splitter = graph.AddChild(maxon.Id(), maxon.Id(core + 'rscolorsplitter'))
        texture.GetInputs().FindChild(core + 'texturesampler.alpha_is_luminance').SetPortValue(False)
        texture.GetOutputs().FindChild(core + 'texturesampler.outcolor').Connect(
            splitter.GetInputs().FindChild(core + 'rscolorsplitter.input'))
        splitter.GetOutputs().FindChild(core + 'rscolorsplitter.outa').Connect(
            shader.GetInputs().FindChild(core + 'standardmaterial.opacity_color'))
        shader.GetInputs().FindChild(core + 'standardmaterial.refl_weight').SetPortValue(0.0)
        shader.GetOutputs().FindChild(core + 'standardmaterial.outcolor').Connect(
            output.GetInputs().FindChild('com.redshift3d.redshift4c4d.node.output.surface'))
        transaction.Commit()
    return mat


def creer_mat(fn, doc, alpha = False):
    if doc.GetActiveRenderData()[c4d.RDATA_RENDERENGINE] == 1036219:
        return creer_mat_redshift(fn, doc)
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
    if Path(fn).suffix.lower() not in ('.jpg', '.jpeg'):
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

class BaseSwissImagesDlg(GeoExtentDialog):
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
    ID_BTON_WEB = 2107
    TXT_FILE_EXIST = "Il semble que le fichier mage existe déjà, voulez vous continuer ?"
    TXT_DOWNLOAD_PROBLEM = "Problème lors du téléchargement de l'image"
    TXT_FILE_CREATION_PROBLEM = "Problème lors de la création du fichier image"

    def add_extraction_sections(self):
        self.AddStaticText(0, c4d.BFH_LEFT, name=self.TITLE_LAYER_CHOICE,
                           borderstyle=c4d.BORDER_WITH_TITLE_BOLD)
        self.add_layer_controls()
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
        self.Enable(self.ID_BTON_WEB, valid)
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
        if id == self.ID_BTON_WEB:
            lo, hi = self.getBbox()
            try:
                url = swisstopo_map_url((lo.x, lo.z, hi.x, hi.z))
                selected_layers = ';'.join(r['layer'] for r in self.selected_services())
                if selected_layers:
                    url += '&layers=' + urllib.parse.quote(selected_layers, safe='.;')
                if not webbrowser.open(url, new=2):
                    c4d.gui.MessageDialog("Impossible d’ouvrir le navigateur. Adresse :\n" + url)
            except (ValueError, webbrowser.Error, OSError) as error:
                c4d.gui.MessageDialog(str(error))
        elif id == self.ID_BTON_DISPLAY:
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
        service = self.service()
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
        styles = ','.join('default' for _ in layer.split(','))
        url = f'https://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS={layer}&STYLES={styles}&CRS=EPSG:2056&BBOX={xmin},{ymin},{xmax},{ymax}&WIDTH={width}&HEIGHT={height}&FORMAT=image/png&TRANSPARENT=TRUE'

        # Ne remplacer un fichier existant qu'après réception d'un PNG valide.
        with urllib.request.urlopen(url, timeout=30) as response:
            image = response.read()
        if not image.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError("Le service WMS n’a pas renvoyé une image PNG pour " + name)
        temporary = Path(fn_img).with_suffix('.png.tmp')
        try:
            temporary.write_bytes(image)
            temporary.replace(fn_img)
        finally:
            if temporary.exists():
                temporary.unlink()

        doc.StartUndo()

        try:
            #création du matériau
            mat = creer_mat(fn_img, doc, alpha = False)
            doc.InsertMaterial(mat)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,mat)

            targets = getattr(self, 'import_targets', [])
            if targets:
                for target in targets:
                    if not target.IsAlive() or target.GetDocument() != doc:
                        raise ValueError('Un objet sélectionné n’est plus disponible.')
                    apply_map_material(doc, target, mat, (xmin, ymin, xmax, ymax))
            else:
                plan = creer_plan(name,mat,(xmax-xmin),(ymax-ymin), projection='top')
                centre = c4d.Vector((xmax+xmin)/2,0,(ymax+ymin)/2) - doc[CONTAINER_ORIGIN]
                plan.SetAbsPos(centre)
                doc.InsertObject(plan)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,plan)
                make_editable(plan,doc)

        finally:
            doc.EndUndo()
        c4d.EventAdd()
        

        return True





class SwissImagesDlg(LayerControls, BaseSwissImagesDlg):
    def CreateLayout(self):
        self.ScrollGroupBegin(2900, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
                              c4d.SCROLLGROUP_VERT | c4d.SCROLLGROUP_HORIZ,
                              initw=240, inith=180)
        result = super().CreateLayout()
        self.GroupEnd()
        return result


def dialog_screen_geometry():
    mouse = c4d.BaseContainer()
    x = y = 0
    if c4d.gui.GetInputState(c4d.BFM_INPUT_MOUSE, c4d.BFM_INPUT_MOUSELEFT, mouse):
        x, y = mouse[c4d.BFM_INPUT_X], mouse[c4d.BFM_INPUT_Y]
    screen = c4d.gui.GeGetScreenDimensions(int(x), int(y), False)
    width = screen['sx2'] - screen['sx1']
    height = screen['sy2'] - screen['sy1']
    w = max(240, min(660, int(width * .90)))
    h = max(180, min(1000, int(height * .88)))
    return dict(xpos=screen['sx1'] + (width-w)//2,
                ypos=screen['sy1'] + (height-h)//2,
                defaultw=w, defaulth=h)


def main():
    # Conserver le dialogue entre deux exécutions et fermer la version précédente.
    previous = getattr(c4d, "_swisstopo_images_dialog", None)
    if previous is not None:
        previous.SetTimer(0)
        if getattr(previous, 'picker', None):
            previous.picker.SetTimer(0)
            previous.picker.Close()
        previous.Close()
    dlg = SwissImagesDlg()
    c4d._swisstopo_images_dialog = dlg
    dlg.Open(c4d.DLG_TYPE_ASYNC, **dialog_screen_geometry())

# Execute main()
if __name__=='__main__':
    main()
