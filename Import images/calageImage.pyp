
import math
import os
import time

import c4d

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
    ID_PHASE = 1007
    ID_DRAG_XRAY = 1103
    ID_RADIO_GRPE = 1006

    ID_CHKBOX_XRAY = 1101
    ID_CHKBOX_MAT_HIGHDEF = 1102

    MODE_ROTATION_SCALE = 1
    MODE_ROTATION = 2
    MODE_SCALE = 3

    TXT_ROTATION_SCALE = '  Echelle et rotation'
    TXT_ROTATION = '  Rotation'
    TXT_SCALE    = '  Echelle'

    TXT_XRAY_NAME = 'Transparent'
    TXT_XRAY_MAT_HIGHDEF = 'Texture haute définition'

    def __init__(self, tool):
        self.tool = tool
        self.parameters = tool.data
        self.doc = None
        self.obj = None

    def CreateLayout(self):
        """
        This Method is called automatically when Cinema 4D Create the Layout (display) of the GeDialog.
        """
        self.doc = c4d.documents.GetActiveDocument()
        self.obj = self.doc.GetActiveObject()

        self.AddStaticText(self.ID_PHASE, c4d.BFH_SCALEFIT, name=self.phase_label())
        if self.GroupBegin(id=1000, flags=c4d.BFH_SCALEFIT, cols=1, rows=1):
            self.GroupBorderSpace(10, 10, 10, 10)
            self.AddRadioGroup(self.ID_RADIO_GRPE, flags=c4d.BFH_LEFT, columns=1, rows=3)

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

        if self.GroupBegin(id=1100, flags=c4d.BFH_SCALEFIT, cols=1, rows=0):
            self.GroupBorderSpace(10, 0, 10, 0)

            self.AddCheckbox(id=self.ID_CHKBOX_XRAY, flags=c4d.BFH_LEFT, initw=0, inith=0, name = self.TXT_XRAY_NAME)
            self.AddCheckbox(self.ID_DRAG_XRAY, c4d.BFH_LEFT, 0, 0,
                             name="Transparence pendant le glissement")
            self.SetBool(self.ID_DRAG_XRAY, self.parameters["drag_xray"])
            self.AddCheckbox(id=self.ID_CHKBOX_MAT_HIGHDEF, flags=c4d.BFH_LEFT, initw=0, inith=0, name = self.TXT_XRAY_MAT_HIGHDEF)
            self.GroupEnd()

            self.maj_dlg()

        return True

    def phase_label(self):
        if not self.parameters["phase2"]:
            return "Phase 1/2 · Déplacement"
        mode = {1: "Échelle et rotation", 2: "Rotation", 3: "Échelle"}
        return "Phase 2/2 · " + mode[self.parameters["mode"]]

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
            self.SetString(self.ID_PHASE, self.phase_label())
            c4d.EventAdd()

        if id == self.ID_DRAG_XRAY:
            self.parameters['drag_xray'] = self.GetBool(id)

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
    
    
    def Message(self, msg, result):
        if (msg.GetId() == c4d.BFM_INPUT
                and msg.GetInt32(c4d.BFM_INPUT_DEVICE) == c4d.BFM_INPUT_KEYBOARD
                and msg.GetInt32(c4d.BFM_INPUT_CHANNEL) == c4d.KEY_TAB
                and not msg.GetInt32(c4d.BFM_INPUT_QUALIFIER)):
            if msg.GetInt32(c4d.BFM_INPUT_VALUE):
                self.tool.set_phase(not self.parameters["phase2"])
            return True
        return super().Message(msg, result)

    def CoreMessage(self, id, msg):
        if id == PLUGIN_ID:
            self.SetString(self.ID_PHASE, self.phase_label())
            return True


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

def redraw_drag():
    c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_NO_THREAD |
                  c4d.DRAWFLAGS_NO_ANIMATION)


class CalageImage(c4d.plugins.ToolData):
    def __init__(self):
        self.data = {"mode": 1, "phase2": False, "drag_xray": True}
        self.dlg = None

    def set_phase(self, second):
        self.data["phase2"] = second
        c4d.SpecialEventAdd(PLUGIN_ID)
        if self.dlg is not None:
            self.dlg.SetString(self.dlg.ID_PHASE, self.dlg.phase_label())

    def InitTool(self, doc, data, bt):
        self.set_phase(False)
        return True

    def KeyboardInput(self, doc, data, bd, win, msg):
        key = msg.GetInt32(c4d.BFM_INPUT_CHANNEL)
        if key not in (c4d.KEY_ESC, c4d.KEY_TAB):
            return False
        self.set_phase(key == c4d.KEY_TAB and not self.data["phase2"])
        redraw_drag()
        c4d.EventAdd()
        return True

    def Draw(self, doc, data, bd, bh, bt, flags):
        bd = doc.GetActiveBaseDraw()
        bd.SetMatrix_Screen()
        bd.SetPen(c4d.Vector(0.956862745098039,0.615686274509804,0.231372549019608))

        if self.data["phase2"]:
            mode = self.data['mode']
            
            if mode == SettingsDialog.MODE_ROTATION_SCALE:
                bd.DrawHUDText( 5, 20, "cliquez-glissez pour tourner et mettre à l'échelle l'objet")
            elif mode == SettingsDialog.MODE_ROTATION:
                bd.DrawHUDText( 5, 20, "cliquez-glissez pour tourner l'objet")
            elif mode == SettingsDialog.MODE_SCALE:
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

        buttons = {c4d.BFM_INPUT_MOUSELEFT: c4d.KEY_MLEFT,
                   c4d.BFM_INPUT_MOUSERIGHT: c4d.KEY_MRIGHT}
        button = buttons.get(msg[c4d.BFM_INPUT_CHANNEL])
        op = doc.GetActiveObject()
        if not button or op is None:
            return False
        if not op.CheckType(c4d.Opoint):
            if c4d.gui.QuestionDialog("Rendre l’objet sélectionné modifiable pour le caler ?"):
                doc.StartUndo()
                try:
                    make_editable(op, doc)
                finally:
                    doc.EndUndo()
                c4d.EventAdd()
            return True

        x, y = msg[c4d.BFM_INPUT_X], msg[c4d.BFM_INPUT_Y]
        original = op.GetMg()
        # Project at the object's depth, including in perspective views.
        depth = bd.WS(original.off).z
        start = bd.SW(c4d.Vector(x, y, depth))
        point = start
        second = self.data["phase2"]
        mode = self.data["mode"]
        arm = start - original.off
        radius = math.hypot(arm.x, arm.z)
        if second and radius < 1e-9:
            return True
        old_xray = op[c4d.ID_BASEOBJECT_XRAY]
        temporary = self.data["drag_xray"] and not old_xray
        last_draw = 0
        win.MouseDragStart(button, int(x), int(y), c4d.MOUSEDRAGFLAGS_DONTHIDEMOUSE)
        doc.StartUndo()
        try:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
            try:
                if temporary:
                    op[c4d.ID_BASEOBJECT_XRAY] = True
                    redraw_drag()
                while True:
                    result, dx, dy, _ = win.MouseDrag()
                    if result != c4d.MOUSEDRAGRESULT_CONTINUE:
                        break
                    if not (dx or dy):
                        continue
                    x += dx
                    y += dy
                    point = bd.SW(c4d.Vector(x, y, depth))
                    matrix = c4d.Matrix(original)
                    if second:
                        direction = point - original.off
                        length = math.hypot(direction.x, direction.z)
                        if length < 1e-9:
                            continue
                        scale = length/radius if mode != SettingsDialog.MODE_ROTATION else 1
                        angle = (math.atan2(arm.x, arm.z) - math.atan2(direction.x, direction.z)
                                 if mode != SettingsDialog.MODE_SCALE else 0)
                        rotation = c4d.utils.MatrixRotY(angle)
                        matrix.v1 = rotation.MulV(original.v1) * scale
                        matrix.v2 = rotation.MulV(original.v2) * scale
                        matrix.v3 = rotation.MulV(original.v3) * scale
                    else:
                        matrix.off = original.off + (point-start)
                    op.SetMg(matrix)
                    now = time.monotonic()
                    if now - last_draw >= 1/30:
                        redraw_drag()
                        last_draw = now
            finally:
                ended = win.MouseDragEnd()
                if temporary:
                    op[c4d.ID_BASEOBJECT_XRAY] = old_xray
            if ended == c4d.MOUSEDRAGRESULT_ESCAPE or result == c4d.MOUSEDRAGRESULT_ESCAPE:
                op.SetMg(original)
            else:
                if not second:
                    pivot = op.GetMg()
                    pivot.off = point
                    move_axis_global(op, pivot)
                self.set_phase(not second)
        finally:
            doc.EndUndo()
            c4d.EventAdd()
        return True

    def AllocSubDialog(self, bc):
        """
        Called by Cinema 4D To allocate the Tool Dialog Option.
        :param bc: Currently not used.
        :type bc: c4d.BaseContainer
        :return: The allocated sub dialog.
        """

        self.dlg = SettingsDialog(self)
        return self.dlg


if __name__ == "__main__":
     bmp = c4d.bitmaps.BaseBitmap()
     dir, file = os.path.split(__file__)
     fn = os.path.join(dir, "res", "calageImage.tif")
     bmp.InitWith(fn)
     c4d.plugins.RegisterToolPlugin(id=PLUGIN_ID,str="#$03Calage d'image",info=0,
                        icon=bmp,help="Déplacer une image, puis ajuster sa rotation ou son échelle.",dat=CalageImage())