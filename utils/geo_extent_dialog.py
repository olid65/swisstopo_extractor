import json
import os

import c4d
import shapefile
from utils import swisstopo_background as bg

CONTAINER_ORIGIN = 1026473
ID_RECTANGLE_TOOL = 1058813
LOCATIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "noms_lieux.json")


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


class GeoExtentDialog(c4d.gui.GeDialog):
    N_MIN = 1015
    N_MAX = 1016
    E_MIN = 1017
    E_MAX = 1018

    GEO_STATUS = 1038
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

    TXT_NO_ORIGIN = "Le document n'est pas géoréférencé !"
    TXT_ORIGIN_NOT_ON_GROUND = "L'origine du document n'est pas sur le sol !"
    TXT_NOT_VIEW_TOP = "Vous devez activer une vue de haut !"
    TXT_NO_SELECTION = "Vous devez sélectionner un objet !"
    TXT_MULTI_SELECTION = "Vous devez sélectionner un seul objet !"

    TXT_NO_PLUGIN_SWISSTOPO_DISPLAY = """Le plugin "affichage swisstopo" n'est pas intallé !"""
    TXT_NO_PLUGIN_RECTANGLE = "Le plugin de dessin de rectangle n'est pas installé !"

    TITLE_GEOLOC = "1. Géolocalisation et affichage d'arrière plan"
    TITLE_EMPRISE = "2. Définissez l'emprise de l'extraction"
    TITLE_LAYER_CHOICE = "3. Choisissez les couches"
    TITLE_LIST_TO_DOWNLOAD = "4. Téléchargez"

    MARGIN = 10
    LARG_COORD = 130

    dico_lieux = None
    lst_lieux = None


    def CreateLayout(self):
        #lecture du fichier des lieux
        if os.path.isfile(LOCATIONS_FILE):
            with open(LOCATIONS_FILE, encoding = 'utf-8') as f:
                self.dico_lieux = json.load(f)
            if self.dico_lieux:
                self.lst_lieux = list(self.dico_lieux)


        self.SetTitle(self.dialog_title)
        # MAIN GROUP
        self.GroupBegin(500, flags=c4d.BFH_SCALEFIT, cols=1, rows=0)
        self.GroupBorderSpace(self.MARGIN*2, self.MARGIN*2, self.MARGIN*2, self.MARGIN*2)

        # GEOLOCALISATION
        self.AddStaticText(400, flags=c4d.BFH_LEFT, initw=0, inith=0, name=self.TITLE_GEOLOC, borderstyle=c4d.BORDER_WITH_TITLE_BOLD)

        self.AddStaticText(self.GEO_STATUS, flags=c4d.BFH_SCALEFIT, initw=500, name=' ')

        self.GroupBegin(0, flags=c4d.BFH_CENTER, cols=1, rows=0)
        self.GroupBorderSpace(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)

        self.AddComboBox(self.COMBO_LOCALISATION, flags=c4d.BFH_CENTER, initw=200, inith=0, specialalign=False, allowfiltering=True)
        #
        self.AddChild(self.COMBO_LOCALISATION,0,'--choisissez un lieu--')
        if self.dico_lieux:
            for i,k in enumerate(self.dico_lieux.keys()):
                self.AddChild(self.COMBO_LOCALISATION,i+1,k)

        self.GroupBegin(0, c4d.BFH_CENTER, cols=3, rows=1)
        self.GroupBorderSpace(0, self.MARGIN, 0, 0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Affichage : ")
        self.AddRadioButton(self.BTON_ORTHO, flags=c4d.BFH_MASK, initw=0, inith=0, name="orthophoto")
        self.AddRadioButton(self.BTON_CN, flags=c4d.BFH_MASK, initw=0, inith=0, name="carte nationale")
        self.GroupEnd()
        bg.add_transparency(self, align=c4d.BFH_CENTER)
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
        self.AddStaticText(1003, name="Ouest :", flags=c4d.BFH_MASK, initw=50)
        self.AddEditNumber(self.E_MIN, flags=c4d.BFH_MASK, initw=self.LARG_COORD, inith=0)
        self.AddButton(self.BTON_E_MIN, flags=c4d.BFH_MASK, initw=0, inith=0, name="copier")
        self.AddStaticText(1005, name="", flags=c4d.BFH_MASK, initw=200)
        self.AddStaticText(1004, name="Est :", flags=c4d.BFH_MASK, initw=50)
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

        self.add_extraction_sections()
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetTimer(200)
        self.refresh_background_choice()
        self.display_doc = None
        self.sync_document()
        return True

    def sync_document(self, force=False):
        doc = c4d.documents.GetActiveDocument()
        if doc is None:
            return
        changed = self.display_doc is None or not self.display_doc.IsAlive() or doc != self.display_doc
        if changed:
            self.display_doc = doc
            self.mini = self.maxi = self.spline_cut = None
            for field in (self.N_MIN, self.N_MAX, self.E_MIN, self.E_MAX):
                self.SetMeter(field, 0.0)
            self.document_changed()

        origin = doc[CONTAINER_ORIGIN]
        coords = (origin.x, origin.z) if origin is not None else None
        if not (changed or force) and coords == self.display_coords:
            return
        self.display_coords = coords
        selection = 0
        status = "Document non géoréférencé"
        if coords is not None:
            x, z = coords
            status = f"Document géoréférencé · X {x:.2f}   Z {z:.2f}"
            if self.lst_lieux:
                def distance_squared(name):
                    east, north = self.dico_lieux[name]
                    return (east - x) ** 2 + (north - z) ** 2

                nearest = min(self.lst_lieux, key=distance_squared)
                east, north = self.dico_lieux[nearest]
                if abs(east - x) < 0.005 and abs(north - z) < 0.005:
                    selection = self.lst_lieux.index(nearest) + 1
                    status = "Document géoréférencé"
                else:
                    status += f" · Lieu le plus proche : {nearest}"
        self.SetString(self.GEO_STATUS, status)
        self.SetInt32(self.COMBO_LOCALISATION, selection)

    def CoreMessage(self, id, msg):
        if id == c4d.EVMSG_CHANGE and getattr(self, "display_doc", None) is not None:
            self.sync_document()
        return super().CoreMessage(id, msg)

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
        self.extent_changed()

    def document_changed(self):
        pass

    def selection_changed(self, obj):
        pass

    def extent_changed(self):
        pass

    def Command(self, id, msg):
        try:
            return self.handle_command(id, msg)
        except Exception as error:
            import traceback
            traceback.print_exc()
            c4d.gui.MessageDialog(f"Extraction impossible : {error}")
            return False

    def handle_command(self, id, msg):
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

            self.sync_document(force=True)

        if id in bg.TRANSPARENCY_CONTROLS:
            bg.change_transparency(self, id)
            return True

        if id in (self.BTON_ORTHO, self.BTON_CN):
            bg.toggle(bg.ID_ORTHO if id == self.BTON_ORTHO else bg.ID_CN10)
            self.refresh_background_choice()
            return True

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

            self.extent_changed()

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
            if origine.y != 0:
                c4d.gui.MessageDialog(self.TXT_ORIGIN_NOT_ON_GROUND)
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
            self.selection_changed(obj)


        # DEPUIS LA VUE DE HAUT
        if id == self.BTON_FROM_VIEW:
            doc = c4d.documents.GetActiveDocument()
            origine = doc[CONTAINER_ORIGIN]
            if not origine:
                c4d.gui.MessageDialog(self.TXT_NO_ORIGIN)
                return True
            if origine.y != 0:
                c4d.gui.MessageDialog(self.TXT_ORIGIN_NOT_ON_GROUND)
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
            try:
                origine = doc[CONTAINER_ORIGIN]
                if not origine:
                    origine = (mini + maxi) / 2
                    # pas réussi à faire un undo pour le doc !
                    doc[CONTAINER_ORIGIN] = origine

                plane = self.planeFromBbox(mini, maxi, origine)
                doc.AddUndo(c4d.UNDOTYPE_NEW, plane)
                doc.InsertObject(plane)
            finally:
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
            c4d.CopyStringToClipboard(str(self.GetFloat(self.N_MAX)))

        if id == self.BTON_E_MIN:
            c4d.CopyStringToClipboard(str(self.GetFloat(self.E_MIN)))

        if id == self.BTON_E_MAX:
            c4d.CopyStringToClipboard(str(self.GetFloat(self.E_MAX)))

        return True

    def refresh_background_choice(self):
        doc = c4d.documents.GetActiveDocument()
        bd = doc.GetActiveBaseDraw()
        bg.refresh_transparency(self, doc, bd)
        current = bg.selected(doc, bd)
        self.SetBool(self.BTON_ORTHO, current == bg.ID_ORTHO)
        self.SetBool(self.BTON_CN, current == bg.ID_CN10)

    def Timer(self, msg):
        bg.tick()
        self.refresh_background_choice()
