# -*- coding: utf-8 -*-


import c4d
import os,glob,math,shutil

CONTAINER_ORIGIN =1026473  

""" TODO :
    remplacer le geotag par un autre système ??? ou améliorer le geotag
    """

def listdirectory(path): 
    """retourne une liste de tous les dossiers en enfants de path"""
    res=[] 
    
    for root, dirs, files in os.walk(path): 
        for i in dirs: 
            res.append(os.path.join(root, i))
    return res

def is_in_doc_path(fn,doc):
    """retourne vrai si le fichier est au meme endroit que doc 
       ou dans tex ou dans un sous dossier de tex"""
    path_img,name_img = os.path.split(fn)
    path_doc = doc.GetDocumentPath()    
    if not path_doc : 
        return False
    if path_doc==path_img:
        return True
    path_tex = os.path.join(path_doc,'tex')
    if path_tex == path_img:
        return True
    lst_dir =listdirectory(path_tex)
    if path_img in lst_dir:
        return True
    return False

class Geopict ():

    """classe pour la gestion d'images g\or\f\renc\es"""

    def __init__(self,fn,fn_calage,doc):
        self.doc = doc
        self.fn = fn
        name = os.path.splitext(self.fn)[0]
        self.f_calage = fn_calage
        self.readCalage()
        self.calculRef()

            

    def readCalage(self):
        """fonction pour la lecture du fichier de calage"""
        try :
            with open(self.f_calage,'r') as f :
               self.val_pix = float(f.readline().split()[0])
               val2 = float(f.readline().split()[0])
               val3 = float(f.readline().split()[0])
               val4 = float(f.readline().split()[0])
               self.val_x = float(f.readline().split()[0])
               self.val_z = float(f.readline().split()[0])
               f.close()


        except IOError:
            print ("Il n'y a pas de fichier de calage")
            return False

            

        else :
            return True

            

    def calculRef(self):

        bmp = c4d.bitmaps.BaseBitmap()

        try:
            fn = self.fn
            bmp.InitWith(fn)
            self.size_px = bmp.GetSize()
            self.size = c4d.Vector(self.size_px[0]*self.val_pix,0,
                         self.size_px[1]*self.val_pix)
            #pour le min et max ne pas oublier que sur le fichier de calage la position est le centre du premier pixel
            self.min = c4d.Vector(self.val_x - self.val_pix/2.0,0.0,self.val_z + self.val_pix/2.0 -self.size.z)
            self.max = self.min+self.size
            self.centre = (self.min+self.max)/2.0
        except :

            print ("Probleme avec l'image")

            

    def creerTexture(self,relatif = False, win = False):
        self.mat = c4d.BaseMaterial(c4d.Mmaterial)
        self.doc.InsertMaterial(self.mat)
        self.doc.AddUndo(c4d.UNDOTYPE_NEW,self.mat)

        self.mat[c4d.MATERIAL_COLOR_MODEL] = c4d.MATERIAL_COLOR_MODEL_ORENNAYAR
        self.mat[c4d.MATERIAL_USE_REFLECTION] = False
        shd = c4d.BaseList2D(c4d.Xbitmap)
        #ATENTION au backslash suivi de t ou de p cela est consid\r\ comme tab ou 
        fn = self.fn
        if is_in_doc_path(fn,self.doc):
            shd[c4d.BITMAPSHADER_FILENAME] = os.path.basename(fn)
        else:
            shd[c4d.BITMAPSHADER_FILENAME] = fn
        self.mat[c4d.MATERIAL_COLOR_SHADER] = shd
        self.mat.InsertShader(shd)
        self.mat[c4d.MATERIAL_PREVIEWSIZE]=12#taille de pr\visualisation
        self.mat.SetName(os.path.basename(fn)[:-4])
        self.mat.Message(c4d.MSG_UPDATE)
        self.mat.Update(True, True)
        return self.mat

    def creerPlan(self):

        plan = c4d.BaseObject(c4d.Oplane)
        plan[c4d.PRIM_PLANE_WIDTH]=self.size.x
        plan[c4d.PRIM_PLANE_HEIGHT]=self.size.z
        plan[c4d.PRIM_PLANE_SUBW]=1
        plan[c4d.PRIM_PLANE_SUBH] =1
        
        origine = self.doc[CONTAINER_ORIGIN]
        if not origine:
            origine = self.centre
            self.doc[CONTAINER_ORIGIN]= origine
        plan.SetAbsPos(self.centre-origine)
        plan.SetName(os.path.basename(self.fn))
        self.creerTagTex(plan)
        self.creerGeoTag(plan)
        self.doc.InsertObject(plan)  
        self.doc.AddUndo(c4d.UNDOTYPE_NEW,plan)     

    def creerTagTex(self,obj,displayTag = True):
        if displayTag:
            tgdisp = c4d.BaseTag(c4d.Tdisplay)#tag affichage
            tgdisp[c4d.DISPLAYTAG_AFFECT_DISPLAYMODE]=True
            tgdisp[c4d.DISPLAYTAG_SDISPLAYMODE]=7 #Ombrage constant
            
            obj.InsertTag(tgdisp)
   

        tgtex = c4d.BaseTag(c4d.Ttexture)#tag affichage
        tgtex[c4d.TEXTURETAG_MATERIAL]=self.mat
        tgtex[c4d.TEXTURETAG_PROJECTION]=2 #projection planaire
        tgtex[c4d.TEXTURETAG_TILE]=False #r\p\titions
        tgtex[c4d.TEXTURETAG_SIZE]=c4d.Vector(self.size.x/2,self.size.z/2, 1)
        tgtex[c4d.TEXTURETAG_ROTATION]=c4d.Vector(0,-math.pi/2,0)
        
        tgtex[CONTAINER_ORIGIN] = self.centre

        #dernier tag
        last = None
        tags = obj.GetTags()
        if len(tags):
            last = tags[-1]

        obj.InsertTag(tgtex, last)
        return tgtex
        
    def creerGeoTag(self,obj):
        pos = obj.GetMg().off
        geoTag = c4d.BaseTag(1026472) #GeoTag
        origine = self.doc[CONTAINER_ORIGIN]
        if not origine:
            origine = self.centre
            self.doc[CONTAINER_ORIGIN]= origine
        geoTag[CONTAINER_ORIGIN] = origine + pos
        
        obj.InsertTag(geoTag)
        return geoTag


    def __str__(self):
        sp = 40
        txt = ('-'*sp*3+'\n'+
                "FICHIER DE CALAGE :\n"+
                ' '*sp+self.f_calage+'\n'+
                ' '*sp+'valeur du pixel : '+str(self.val_pix)+'\n'+
                ' '*sp+'coord x         : '+str(self.val_x)+'\n'+
                ' '*sp+'coord z         : '+str(self.val_z)+'\n'+
                '-'*sp*3+'\n'+

                "IMAGE :\n"+
                ' '*sp+self.fn+'\n'+
                ' '*sp+'taille (px)     : '+str(self.size_px)+'\n'+
                ' '*sp+'taille (m)      : '+str(self.size)+'\n'+
                ' '*sp+'min             : '+str(self.min)+'\n'+
                ' '*sp+'max             : '+str(self.max)+'\n'+
                ' '*sp+'centre          : '+str(self.centre)+'\n'+
                '-'*sp*3)
        return txt



def readTFW(fn):
    if fn :
        try :
            with open(fn,'r') as f :
               val_pix = float(f.readline().split()[0])
               val2 = float(f.readline().split()[0])
               val3 = float(f.readline().split()[0])
               val4 = float(f.readline().split()[0])
               val_x = float(f.readline().split()[0])
               val_z = float(f.readline().split()[0])
               f.close()


        except IOError:
            print ("Il n'y a pas de fichier")
            return False            

        else :
            return True

    else :
        return False
 
def isInMetre(doc):
    scale, unit = doc[c4d.DOCUMENT_DOCUNIT].GetUnitScale()
    if unit == c4d.DOCUMENT_UNIT_M :return True
    return False


def non_existant_fn(fn):
    """renvoie un nom de fichier incrementé qui n'existe pas"""
    i=1
    name,ext = os.path.splitext(fn)
    while os.path.exists(fn):
        fn = f'{name}_{i}{ext}'
        i+=1
    return fn

    
def main(fn = None, fn_calage = None, alerte = True):
    doc = c4d.documents.GetActiveDocument()
    #fn = '/Users/donzeo/Documents/TEMP/test_import_SITG_3/format_JPG_2_hepia_ortho_20141102_091001/ORTHOPHOTOS_2012_20cm.jpg'

    if not fn :
        fn = c4d.storage.LoadDialog(type =c4d.FILESELECTTYPE_IMAGES,title="Séléctionnez l'image :")

    if not fn : return
    extensions = ['.jpg','.tif','.png','.gif','.psd']
    if os.path.splitext(fn)[1] not in extensions : 
        c4d.gui.MessageDialog("Ce n'est pas un fichier image")
        return

    fn_ss_ext,ext = os.path.splitext(fn)
    
    #extension du fichier de calage
    ext_calage = ext[:2]+ext[-1]+'w'
    
    if not fn_calage:
        #on regarde si il y a un fichier de calage type .tfw
        
        if os.path.isfile(fn_ss_ext+ext_calage):
            fn_calage = fn_ss_ext+ext_calage
        #ou un autre de type .wld
        elif os.path.isfile(fn_ss_ext+'.wld'):
            fn_calage = fn_ss_ext+'.wld'
        #si aucun n'existe on quitte'
        else :
            c4d.gui.MessageDialog("il n'y a pas de fichier de calage .wld ou {0}, l'import est impossible".format(ext_calage))
            return
    
    #on verifie que le document est en metres
    if not isInMetre(doc):
        res = c4d.gui.QuestionDialog("""L'unité du document n'est pas le mètre, ce paramètre va être modifié\n\nVoulez-vous continuer? (pas d'annulation possible)""")
        if not res : return
        #doc.AddUndo(c4d.UNDOTYPE_CHANGE,doc) #-> ne fonctionne pas !
        us = doc[c4d.DOCUMENT_DOCUNIT]
        us.SetUnitScale(1, c4d.DOCUMENT_UNIT_M)
        doc[c4d.DOCUMENT_DOCUNIT] = us 
        
    #on regarde si le document est enregistré pour copier l'image dans le dossier tex     
    path_doc = doc.GetDocumentPath()   
    fn_doc = doc.GetDocumentName()  
    relatif = True  

    if path_doc == '':
        relatif = False
        if alerte :
            c4d.gui.MessageDialog(("""Attention, le document n'étant pas enregistré, le chemin à l'image sera absolu\n"""+
                                   """Pour créer un chemin relatif vous devrez passer par Fichier/enregistrer le projet"""))
    
    #copie de l'image si le document est enregistré
    if relatif:
        path_dst = os.path.join(path_doc,'tex')
        if not os.path.isdir(path_dst):
            os.makedirs(path_dst)
        dst = os.path.join(path_dst,os.path.basename(fn))

        # on prend un nom de fichier qui n'existe pas
        dst = non_existant_fn(dst)

        shutil.copyfile(fn, dst)
            
        fn = dst
 
    gp = Geopict(fn,fn_calage,c4d.documents.GetActiveDocument())
    gp.creerTexture(relatif)
    
    #si on a un objet sélectionné on plaque dessus
    op = doc.GetActiveObject()
    if op:
        #on regarde si il a un geotag
        if not op.GetTag(1026472,0):
            tg = gp.creerGeoTag(op)
            doc.AddUndo(c4d.UNDOTYPE_NEW,tg)
        tag = gp.creerTagTex(op, displayTag = False)
            
    else :
        gp.creerPlan()
          
    
if __name__=='__main__':
    main()
