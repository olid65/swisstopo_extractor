import c4d

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


class DisplayCommand(c4d.plugins.CommandData):
    def __init__(self):
        super().__init__()
        self.dialog = BackgroundDialog()

    def Execute(self, doc):
        return self.dialog.Open(c4d.DLG_TYPE_ASYNC, pluginid=bg.ID_ORTHO)

    def RestoreLayout(self, secret):
        return self.dialog.Restore(pluginid=bg.ID_ORTHO, secret=secret)
