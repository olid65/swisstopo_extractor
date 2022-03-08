
import c4d,os

#be sure to use a unique ID obtained from www.plugincafe.com
PLUGIN_ID = 1038258

def get_last_texture_tag(op):
    tex_tags = [tag for tag in op.GetTags() if tag.CheckType(c4d.Ttexture)]    
    if tex_tags:
        return tex_tags[-1]    
    return None

def previewsize_last_tex_tag(op, previewsize = c4d. MATERIAL_PREVIEWSIZE_NO_SCALE):
    tag = get_last_texture_tag(op)
    if tag:
        mat = tag[c4d.TEXTURETAG_MATERIAL]
        if mat :
            #doc.AddUndo(c4d.UNDOTYPE_CHANGE_SMALL,mat)
            mat[c4d.MATERIAL_PREVIEWSIZE] = previewsize

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

###################################################################################
#DIALOG

class SettingsDialog(c4d.gui.SubDialog):
    """
    Dialog to display option in the ToolData, in this case the Sphere size.
    """
    parameters = {}
    ID_RADIO_GRPE = 1006

    ID_CHKBOX_XRAY = 1101
    ID_CHKBOX_MAT_HIGHDEF = 1102

    MODE_ROTATION_SCALE = 1
    MODE_ROTATION = 2
    MODE_SCALE = 3

    TXT_ROTATION_SCALE = '  Echelle et rotation'
    TXT_ROTATION = '  Rotation'
    TXT_SCALE    = '  Echelle'

    TXT_XRAY_NAME = '  Transparent'
    TXT_XRAY_MAT_HIGHDEF = '  Texture haute définition'

    def __init__(self, arg):
        # Checks if the argument passed is a dictionary
        if not isinstance(arg, dict):
            raise TypeError("arg is not a dict.")

        self.parameters = arg
        
        self.doc = None
        self.obj = None

    def CreateLayout(self):
        """
        This Method is called automatically when Cinema 4D Create the Layout (display) of the GeDialog.
        """
        self.doc = c4d.documents.GetActiveDocument()
        self.obj = self.doc.GetActiveObject()

        self.bc = self.doc[PLUGIN_ID]
        #on récupère les données dans le doc
        if self.bc :
            pass

        # sinon on récupère les données par défaut
        # et on crée un nouveau BaseContainer dans le doc
        else:
            pass

        # Creates a Group to align 2 items
        if self.GroupBegin(id=1000, flags=c4d.BFH_SCALEFIT, cols=1, rows=1):
            self.GroupBorderSpace(10, 10, 10, 10)
            self.AddRadioGroup(self.ID_RADIO_GRPE, flags=0, columns=1, rows=3)

            self.AddChild(self.ID_RADIO_GRPE, self.MODE_ROTATION_SCALE, self.TXT_ROTATION_SCALE)
            self.AddChild(self.ID_RADIO_GRPE, self.MODE_ROTATION, self.TXT_ROTATION)
            self.AddChild(self.ID_RADIO_GRPE, self.MODE_SCALE, self.TXT_SCALE)

            # Defines the default values
            self.SetInt32(id=self.ID_RADIO_GRPE, value=self.parameters['mode'])
            self.GroupEnd()

            self.AddSeparatorH(initw=80, flags=c4d.BFH_FIT)

            # self.AddRadioText(1, flags=c4d.BFH_SCALEFIT, initw=80, inith=0, name=self.TXT_ROTATION_SCALE)
            # self.AddRadioText(2, flags=c4d.BFH_SCALEFIT, initw=80, inith=0, name=self.TXT_ROTATION)
            # self.AddRadioText(3, flags=c4d.BFH_SCALEFIT, initw=80, inith=0, name=self.TXT_SCALE)

        if self.GroupBegin(id=1100, flags=c4d.BFH_SCALEFIT, cols=1, rows=2):
            #self.GroupBorderSpace(10, 10, 10, 10)

            self.AddCheckbox(id=self.ID_CHKBOX_XRAY, flags =0, initw=150, inith=20, name = self.TXT_XRAY_NAME)
            self.AddCheckbox(id=self.ID_CHKBOX_MAT_HIGHDEF, flags =0, initw=150, inith=20, name = self.TXT_XRAY_MAT_HIGHDEF)
            self.GroupEnd()

            self.maj_dlg()

        self.GroupEnd()
        return True

    def Command(self, id, msg):
        """
          This Method is called automatically when the user clicks on a gadget and/or changes its value this function will be called.
          It is also called when a string menu item is selected.
         :param messageId: The ID of the gadget that triggered the event.
         :type messageId: int
         :param bc: The original message container
         :type bc: c4d.BaseContainer
         :return: False if there was an error, otherwise True.
         """
        # When the user change the Gadget with the ID 1002 (the input number field)
        if id == self.ID_RADIO_GRPE:
            self.parameters['mode'] = self.GetInt32(id=self.ID_RADIO_GRPE)

        if id == self.ID_CHKBOX_XRAY:
            self.obj = self.doc.GetActiveObject()
            self.obj[c4d.ID_BASEOBJECT_XRAY] = self.GetBool(self.ID_CHKBOX_XRAY)
            c4d.EventAdd()
        
        if id == self.ID_CHKBOX_MAT_HIGHDEF:
            self.obj = self.doc.GetActiveObject()
            if self.GetBool(self.ID_CHKBOX_MAT_HIGHDEF):
                previewsize_last_tex_tag(self.obj, previewsize = c4d. MATERIAL_PREVIEWSIZE_NO_SCALE)
            else:
                previewsize_last_tex_tag(self.obj, previewsize = c4d. MATERIAL_PREVIEWSIZE_DEF)
            c4d.EventAdd()


        return True
    
    
    def CoreMessage(self, id, msg):

        #pour modifier les paramètre des checkboxes si l'objet a changé
        if id == c4d.EVMSG_CHANGE:
            self.doc = c4d.documents.GetActiveDocument()
            obj = self.doc.GetActiveObject()
            if obj != self.obj:
                self.obj = obj
                self.maj_dlg()
                
        return True

    
    def maj_dlg(self):
        """mise à jour des cases à cocher xray et définition texture si l'objet change"""
        self.obj = self.doc.GetActiveObject()
        if self.obj :
            self.SetBool(self.ID_CHKBOX_XRAY, self.obj[c4d.ID_BASEOBJECT_XRAY])
        
            tag_tex = get_last_texture_tag(self.obj)
            if tag_tex:
                mat = tag_tex[c4d.TEXTURETAG_MATERIAL]
                if mat :

                    if mat[c4d.MATERIAL_PREVIEWSIZE] == c4d. MATERIAL_PREVIEWSIZE_DEF:
                        self.SetBool(self.ID_CHKBOX_MAT_HIGHDEF, False)
                    else:
                        self.SetBool(self.ID_CHKBOX_MAT_HIGHDEF, True)



def move_axis_global(obj, new_axis):    
    mat = ~new_axis * obj.GetMg()
    if obj.CheckType(c4d.Opoint):
        points = [p * mat for p in obj.GetAllPoints()]
        obj.SetAllPoints(points)
        obj.Message(c4d.MSG_UPDATE)
    for child in obj.GetChildren():
        child.SetMl(mat * child.GetMl())
    obj.SetMg(new_axis)

def getMatrix_v2_vertical(p1,p2, off = c4d.Vector(0), scale = c4d.Vector(1)):
    #on met y a zero
    p1.y = 0
    p2.y = 0
    v1 = (p2-p1).GetNormalized()*scale.x
    v2 = c4d.Vector(0,1,0)*scale.y
    v3 = v1.Cross(v2).GetNormalized()*scale.z
    
    return c4d.Matrix(off,v1,v2,v3)

######################################################################
# TOOLDATA

class CalageImage(c4d.plugins.ToolData):
    """Inherit from ToolData to create your own tool"""
    mode_scale = False

    def __init__(self):
        self.data = {'mode': 1}
        self.dlg = None
        self.obj = None

    def InitTool(self, doc, data, bt):
        self._phase2 = False
        self.pos_axe_virtuel = None
        return True
       

    def KeyboardInput(self, doc, data, bd, win, msg):
        key = msg.GetLong(c4d.BFM_INPUT_CHANNEL)
        
        #avec la touche esc on revient à la phase 1 (déplacement)    
        if key==c4d.KEY_ESC:
            self._phase2 = False

        # avec tab on switch d'un mode à l'autre
        if key ==c4d.KEY_TAB :
            self._phase2 = not self._phase2

        return False

    def Draw(self, doc, data, bd, bh, bt, flags):
        bd = doc.GetActiveBaseDraw()
        bd.SetMatrix_Screen()
        bd.SetPen(c4d.Vector(0.956862745098039,0.615686274509804,0.231372549019608))

        if self._phase2:
            mode = self.dlg.parameters['mode']
            
            if mode == self.dlg.MODE_ROTATION_SCALE:
                bd.DrawHUDText( 5, 20, "cliquez-glissez pour tourner et mettre à l'échelle l'objet")
            elif mode == self.dlg.MODE_ROTATION:
                bd.DrawHUDText( 5, 20, "cliquez-glissez pour tourner l'objet")
            elif mode == self.dlg.MODE_SCALE:
                bd.DrawHUDText( 5, 20, "cliquez-glissez pour mettre à l'échelle l'objet")
        else:
            bd.DrawHUDText( 5, 20, "cliquez-glissez pour positionner l'objet")



        bd.SetMatrix_Matrix(None, c4d.Matrix())
        return c4d.TOOLDRAW_HIGHLIGHTS

    def GetState(self, doc):
        """
        Called by Cinema 4D to know if the tool can be used currently
        :param doc: The current active document.
        :type doc: c4d.documents.BaseDocument
        :return: True if the tool can be used, otherwise False.
        """
        if doc.GetMode() != c4d.Mmodel:
            #self.dlg.SetString(self.dlg.ID_TXT_INFO, 'Fonctionne uniquement en mode modèle')
            return False

        obj = doc.GetActiveObject()
        # si il n'y a pas un objet polygonal sélectionné
        if not obj :
            #self.dlg.SetString(self.dlg.ID_TXT_INFO, "Il n'y a pas d'objet sélectionné")
            return False

        #si l'objet n'est pas un objet point ou n'a pas de chache on désactive
        if not obj.CheckType(c4d.Opoint) :
            cache = obj.GetCache()
            if not cache or not cache.GetPointCount():
                return False
            #self.dlg.SetString(self.dlg.ID_TXT_INFO, "L'objet sélectionné doit être polygonal")
            #return False

        return c4d.CMD_ENABLED

    def MouseInput(self, doc, data, bd, win, msg):

        doc.StartUndo()
        op = doc.GetActiveObject()
        if not op : return False

        #si l'objet est paramétrique il faut le rendre éditable
        if not op.CheckType(c4d.Opoint) :
            if c4d.gui.QuestionDialog("L'objet sélectionné va être édité, voulez-vous continuer ?"):
                op = make_editable(op,doc)
                c4d.EventAdd()

            return True


        x = msg[c4d.BFM_INPUT_X]
        y = msg[c4d.BFM_INPUT_Y]

        device = 0
        if msg[c4d.BFM_INPUT_CHANNEL]==c4d.BFM_INPUT_MOUSELEFT:
            device = c4d.KEY_MLEFT

        if msg[c4d.BFM_INPUT_CHANNEL]==c4d.BFM_INPUT_MOUSERIGHT:
             device = c4d.KEY_MRIGHT
        ##########################################################################################
        #Récupération des données souris

        dx = 0.0
        dy = 0.0

        win.MouseDragStart(button=device, mx=int(x), my=int(y),
                                 flags=c4d.MOUSEDRAGFLAGS_DONTHIDEMOUSE)
        result, tx, ty, channel = win.MouseDrag()

        mg = op.GetMg()
        pos_dprt = mg.off
        delta = pos_dprt - bd.SW(c4d.Vector(x,y,0))

        doc.AddUndo(c4d.UNDOTYPE_CHANGE,op)

        if self.dlg:
            mode = self.dlg.parameters['mode']
        else:
            mode = 1

        if mode == self.dlg.MODE_ROTATION_SCALE:
            change_rot = True
            change_scale = True
        elif mode == self.dlg.MODE_ROTATION:
            change_rot = True
            change_scale = False
        if mode == self.dlg.MODE_SCALE:
            change_rot = False
            change_scale = True

        if self._phase2:
            #rotation de l'axe lors du second drag
            pos_dprt2 = bd.SW(c4d.Vector(x,y,0))
            matrix = getMatrix_v2_vertical(mg.off,pos_dprt2, mg.off)
            move_axis_global(op, matrix)
            dist_origin = c4d.Vector.GetDistance(pos_dprt2,matrix.off)


        while result==c4d.MOUSEDRAGRESULT_CONTINUE:
            dx += tx
            dy += ty
            result, tx, ty, channel = win.MouseDrag()
            pt = bd.SW(c4d.Vector(x+dx,y+dy,0))
            pos = pt +delta

            if self._phase2:
                dist = c4d.Vector.GetDistance(pt,matrix.off)
                if change_scale:
                    scale = c4d.Vector(dist/dist_origin)
                else:
                    scale = c4d.Vector(1)

                if change_rot :
                    new_m = getMatrix_v2_vertical(matrix.off, pt, matrix.off, scale)
                else:
                    new_m = c4d.Matrix()
                    new_m.off = matrix.off
                    new_m.v1 = matrix.v1*scale.x
                    new_m.v2 = matrix.v2*scale.x
                    new_m.v3 = matrix.v3*scale.x

                op.SetMg(new_m)
                
            else :
                mg.off = pos
                op.SetMg(mg)
            
            c4d.DrawViews(c4d.DRAWFLAGS_FORCEFULLREDRAW,bd)
            c4d.EventAdd()

        if result == c4d.MOUSEDRAGRESULT_FINISHED:
            # si on est au bout du premier drag on modifie l'axe
            if not self._phase2:
                mg.off = pt
                move_axis_global(op, mg)
            self._phase2 = not self._phase2

        #si la touche SHIFT ou CTRL ne sont pas enfoncee on deselectionne tout
        if not (msg[c4d.BFM_INPUT_QUALIFIER]==c4d.QSHIFT  or  msg[c4d.BFM_INPUT_QUALIFIER]==c4d.QCTRL): pass

        c4d.DrawViews(c4d.DRAWFLAGS_FORCEFULLREDRAW,bd)
        c4d.EventAdd()
        

        return True

    def AllocSubDialog(self, bc):
        """
        Called by Cinema 4D To allocate the Tool Dialog Option.
        :param bc: Currently not used.
        :type bc: c4d.BaseContainer
        :return: The allocated sub dialog.
        """

        self.dlg = SettingsDialog(getattr(self, "data", {'mode': 1}))
        return self.dlg


if __name__ == "__main__":
     bmp = c4d.bitmaps.BaseBitmap()
     dir, file = os.path.split(__file__)
     fn = os.path.join(dir, "res", "calageImage.tif")
     bmp.InitWith(fn)
     c4d.plugins.RegisterToolPlugin(id=PLUGIN_ID,str="#$03Calage d'image",info=0,
                        icon=bmp,help="blabla",dat=CalageImage())