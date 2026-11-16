import os
import sys
import c4d

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils import swisstopo_background as bg

class BackgroundDialog(c4d.gui.GeDialog):
    def CreateLayout(self):
        self.SetTitle("swisstopo affichage")
        self.GroupBegin(0, c4d.BFH_CENTER, cols=1, rows=0)
        self.GroupBegin(0, c4d.BFH_CENTER, cols=2, rows=1)
        self.AddStaticText(0, c4d.BFH_LEFT | c4d.BFV_TOP, name="Affichage : ")
        self.GroupBegin(0, c4d.BFH_LEFT, cols=1, rows=0)
        for identifier, (name, _) in bg.LAYERS.items():
            self.AddRadioButton(identifier, c4d.BFH_LEFT, name=name)
        self.GroupEnd()
        self.GroupEnd()
        bg.add_transparency(self, align=c4d.BFH_CENTER)
        self.GroupEnd()
        return True

    def InitValues(self):
        self.SetTimer(200)
        self.refresh()
        return True

    def refresh(self):
        doc = c4d.documents.GetActiveDocument()
        bd = doc.GetActiveBaseDraw()
        bg.refresh_transparency(self, doc, bd)
        current = bg.selected(doc, bd)
        for identifier in bg.LAYERS:
            self.SetBool(identifier, identifier == current)

    def Timer(self, msg):
        bg.tick()
        self.refresh()

    def Command(self, identifier, msg):
        if identifier in bg.TRANSPARENCY_CONTROLS:
            bg.change_transparency(self, identifier)
        elif identifier in bg.LAYERS:
            bg.toggle(identifier)
            self.refresh()
        return True


palette = BackgroundDialog()


class DisplayCommand(c4d.plugins.CommandData):
    def __init__(self, layer):
        super().__init__()
        self.layer = layer

    def Execute(self, doc):
        if bg.select(self.layer):
            palette.Open(c4d.DLG_TYPE_ASYNC)
        return True

def icone(nom) :
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", nom)
    bmp.InitWith(fn)
    return bmp
    
if __name__=='__main__':
    c4d.plugins.RegisterCommandPlugin(id=bg.ID_ORTHO, str="#$00"+"orthophoto",
                                      info=0, help="", dat=DisplayCommand(bg.ID_ORTHO),
                                      icon=icone("ortho.png"))
    c4d.plugins.RegisterCommandPlugin(id=bg.ID_CN10, str="#$01"+"carte nationale 10'000",
                                      info=0, help="", dat=DisplayCommand(bg.ID_CN10),
                                      icon=icone("cn10.png"))

    c4d.plugins.RegisterCommandPlugin(id=bg.ID_CN25, str="#$02"+"carte nationale 25'000",
                                      info=0, help="", dat=DisplayCommand(bg.ID_CN25),
                                      icon=icone("cn25.png"))
    c4d.plugins.RegisterCommandPlugin(id=bg.ID_CN50, str="#$03"+"carte nationale 50'000",
                                      info=0, help="", dat=DisplayCommand(bg.ID_CN50),
                                      icon=icone("cn50.png"))