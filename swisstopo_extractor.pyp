import c4d, os, sys

sys.path.append(os.path.dirname(__file__))
import extractor


__version__ = 1.0
__date__    = "19/10/2021"

PLUGIN_ID_SWISSTOPOEXTRACTOR = 1058482

CONTAINER_ORIGIN =1026473



class SwisstopoExtractor(c4d.plugins.CommandData):
    dialog = None
    def Execute(self, doc) :
        if self.dialog is None:
            self.dialog = extractor.DlgBbox()

            # Opens the dialog
        return self.dialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID_SWISSTOPOEXTRACTOR, defaultw=250, defaulth=150)

def icone(nom) :
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", nom)
    bmp.InitWith(fn)
    return bmp
    
if __name__=='__main__':
    c4d.plugins.RegisterCommandPlugin(id=PLUGIN_ID_SWISSTOPOEXTRACTOR, str="swisstopo extractor",
                                      info=0, help="", dat=SwisstopoExtractor(),
                                      icon=icone("swisstopo.png"))