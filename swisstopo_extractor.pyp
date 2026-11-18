import c4d, os, sys

sys.path.append(os.path.dirname(__file__))
import extractor
from utils.swisstopo_display import DisplayCommand
from utils import swisstopo_background as bg


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
    c4d.plugins.RegisterCommandPlugin(id=PLUGIN_ID_SWISSTOPOEXTRACTOR, str="swisstopo maquette 3D",
                                      info=0, help="", dat=SwisstopoExtractor(),
                                      icon=icone("swisstopo.png"))
    c4d.plugins.RegisterCommandPlugin(id=bg.ID_ORTHO, str="swisstopo affichage",
                                      info=0, help="Choisir le fond de la vue de haut",
                                      dat=DisplayCommand(), icon=icone("swisstopo_affichage.png"))


    from utils import swisstopo_images

    class SwisstopoImages(c4d.plugins.CommandData):
        def Execute(self, doc):
            swisstopo_images.main()
            return True

    c4d.plugins.RegisterCommandPlugin(
        id=1074448, str="swisstopo images", info=0,
        help="Extraire une image swisstopo", dat=SwisstopoImages(),
        icon=icone("swisstopo_images.png"))
