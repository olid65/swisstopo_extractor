#!/usr/bin/python
# -*- coding: utf-8 -*-

import c4d, math, os
from glob import glob


CONTAINER_ORIGIN =1026473

SELECTION_NAME_TOITS = 'toits'
SELECTION_NAME_FACADES ='facades'
SELECTION_NAME_BASES ='bases'

class Bbox(object):
    def __init__(self,mini,maxi):

        self.min = mini
        self.max = maxi
        self.centre = (self.min+self.max)/2
        self.largeur = self.max.x - self.min.x
        self.hauteur = self.max.z - self.min.z
        self.taille = self.max-self.min

    def intersect(self,bbx2):
        """video explicative sur http://www.youtube.com/watch?v=8b_reDI7iPM"""
        return ( (self.min.x+ self.taille.x)>= bbx2.min.x and
                self.min.x <= (bbx2.min.x + bbx2.taille.x) and
                (self.min.z + self.taille.z) >= bbx2.min.z and
                self.min.z <= (bbx2.min.z + bbx2.taille.z))
        
    def xInside(self,x):
        """retourne vrai si la variable x est entre xmin et xmax"""
        return x>= self.min.x and x<= self.max.x
    
    def zInside(self,y):
        """retourne vrai si la variable x est entre xmin et xmax"""
        return y>= self.min.z and y<= self.max.z
        
    def isInsideX(self,bbox2):
        """renvoie 1 si la bbox est complètement à l'intérier
           renoive 2 si elle est à cheval
           et 0 si à l'extérieur"""
        minInside = self.xInside(bbox2.xmin)
        maxInside = self.xInside(bbox2.xmax)
        if minInside and maxInside : return 1
        if minInside or maxInside : return 2
        #si bbox1 est plus grand
        if bbox2.xmin < self.min.x and bbox2.xmax > self.max.x : return 2
        return 0
    
    def isInsideZ(self,bbox2):
        """renvoie 1 si la bbox est complètement à l'intérier
           renoive 2 si elle est à cheval
           et 0 si à l'extérieur"""
        minInside = self.zInside(bbox2.ymin)
        maxInside = self.zInside(bbox2.ymax)
        if minInside and maxInside : return 1
        if minInside or maxInside : return 2
        #si bbox1 est plus grand
        if bbox2.ymin < self.min.z and bbox2.ymax > self.max.z : return 2
        return 0
    
    def ptIsInside(self,pt):
        """renvoie vrai si point c4d est à l'intérieur"""
        return  self.xInside(pt.x) and self.zInside(pt.z)

    def getRandomPointInside(self, y = 0):
        x = self.min.x + random.random()*self.largeur
        z = self.min.z + random.random()*self.hauteur
        return c4d.Vector(x,y,z)
    
    def GetSpline(self,origine = c4d.Vector(0)):
        """renvoie une spline c4d de la bbox"""
        res = c4d.SplineObject(4,c4d.SPLINETYPE_LINEAR)
        res[c4d.SPLINEOBJECT_CLOSED] = True
        res.SetAllPoints([c4d.Vector(self.min.x,0,self.max.z)-origine,
                           c4d.Vector(self.max.x,0,self.max.z)-origine,
                           c4d.Vector(self.max.x,0,self.min.z)-origine,
                           c4d.Vector(self.min.x,0,self.min.z)-origine])
        res.Message(c4d.MSG_UPDATE)
        return res
    def __str__(self):
        return ('X : '+str(self.min.x)+'-'+str(self.max.x)+'->'+str(self.max.x-self.min.x)+'\n'+
                'Y : '+str(self.min.z)+'-'+str(self.max.z)+'->'+str(self.max.z-self.min.z))

    def GetCube(self,haut = 200):
        res = c4d.BaseObject(c4d.Ocube)
        taille = c4d.Vector(self.largeur,haut,self.hauteur)
        res.SetAbsPos(self.centre)
        return res
    
    @staticmethod
    def fromObj(obj,origine = c4d.Vector()):
        """renvoie la bbox 2d de l'objet"""
        mg = obj.GetMg()
    
        rad = obj.GetRad()
        centre = obj.GetMp()
        
        #4 points de la bbox selon orientation de l'objet
        pts = [ c4d.Vector(centre.x+rad.x,centre.y+rad.y,centre.z+rad.z) * mg,
                c4d.Vector(centre.x-rad.x,centre.y+rad.y,centre.z+rad.z) * mg,
                c4d.Vector(centre.x-rad.x,centre.y-rad.y,centre.z+rad.z) * mg,
                c4d.Vector(centre.x-rad.x,centre.y-rad.y,centre.z-rad.z) * mg,
                c4d.Vector(centre.x+rad.x,centre.y-rad.y,centre.z-rad.z) * mg,
                c4d.Vector(centre.x+rad.x,centre.y+rad.y,centre.z-rad.z) * mg,
                c4d.Vector(centre.x-rad.x,centre.y+rad.y,centre.z-rad.z) * mg,
                c4d.Vector(centre.x+rad.x,centre.y-rad.y,centre.z+rad.z) * mg]
    
        mini = c4d.Vector(min([p.x for p in pts]),min([p.y for p in pts]),min([p.z for p in pts])) + origine
        maxi = c4d.Vector(max([p.x for p in pts]),max([p.y for p in pts]),max([p.z for p in pts])) + origine
    
        return Bbox(mini,maxi)
    
    @staticmethod
    def fromView(basedraw,origine = c4d.Vector()):
        dimension = basedraw.GetFrame()
        largeur = dimension["cr"]-dimension["cl"]
        hauteur = dimension["cb"]-dimension["ct"]
    
        mini =  basedraw.SW(c4d.Vector(0,hauteur,0)) + origine
        maxi = basedraw.SW(c4d.Vector(largeur,0,0)) + origine
        return Bbox(mini,maxi)
    
def get_swissbuildings3D_dxfs(path):
    """renvoie une liste de fichier dxf contenus dans
       un sous-dossier qui contient le mot swissbuildings3d"""
    lst_dxf = None

    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs:
            if name == 'swissbuildings3d' :
                lst_dxf = [fn_dxf for fn_dxf in glob(os.path.join(root, name,'*.dxf'))]
    return lst_dxf

def import_swissbuildings3D_from_list_dxf(lst_dxfs,doc, origin = None):
    #mise en cm des options d'importation DXF
    plug = c4d.plugins.FindPlugin(1001035, c4d.PLUGINTYPE_SCENELOADER)
    if plug is None:
        print ("pas de module d'import DXF")
        return
    op = {}

    if plug.Message(c4d.MSG_RETRIEVEPRIVATEDATA, op):

        import_data = op.get("imexporter",None)

        if not import_data:
            return False

        scale = import_data[c4d.DXFIMPORTFILTER_SCALE]
        scale.SetUnitScale(1,c4d.DOCUMENT_UNIT_M)

        import_data[c4d.DXFIMPORTFILTER_SCALE] = scale

        import_data[c4d.DXFIMPORTFILTER_LAYER] = c4d.DXFIMPORTFILTER_LAYER_NONE

    first_obj = doc.GetFirstObject()

    for fn in lst_dxfs:
        c4d.documents.MergeDocument(doc, fn, c4d.SCENEFILTER_OBJECTS,None)
        obj = doc.GetFirstObject()
        if not obj : continue
        mg = obj.GetMg()
        if not origin :
            doc[CONTAINER_ORIGIN] =mg.off
            origin = doc[CONTAINER_ORIGIN]
        mg.off-=origin
        obj.SetMg(mg)

def refCPoly(cpoly,id):
    """rajoute id aux valeurs a,b,c,d du polygon"""
    cpoly.a+=id
    cpoly.b+=id
    cpoly.c+=id
    cpoly.d+=id
    return cpoly

def connect(lst_poly, nom = None):
    """connecte tous les polys entre eux et renvoie
       un polygon object avec l'axe au centre à la base du batiment
       ATTENTION lancer la commande OPTIMIZE APRES"""
    pts = []
    polys = []
    
    pos = 0
    for poly in lst_poly:
        mg = poly.GetMg()
        pts+=[p*mg for p in poly.GetAllPoints()]
        polys += [refCPoly(p,pos) for p in poly.GetAllPolygons()]
        pos+=poly.GetPointCount()
    res = c4d.PolygonObject(len(pts),len(polys))
    res.SetAllPoints(pts)
    for i,p in enumerate(polys): res.SetPolygon(i,p)
    res.Message(c4d.MSG_UPDATE)
    centre = res.GetMp()
    rad = res.GetRad()
    centre.y-=rad.y
    pts = [p-centre for p in pts]
    res.SetAllPoints(pts)
    mg = res.GetMg()
    mg.off = centre
    res.SetMg(mg)
    if nom : res.SetName(nom)
    res.Message(c4d.MSG_UPDATE)
    return res

def getBatiHorsBbox(bbx,obj, lst = []):
    while obj:
        if obj.CheckType(c4d.Opolygon):
            bbx2 = Bbox.fromObj(obj)
            if not bbx2.intersect(bbx):
                lst.append(obj)
        getBatiHorsBbox(bbx,obj.GetDown(), lst)
        obj = obj.GetNext()
    return lst

def getPolyObj(obj, lst = []):
    while obj:
        if obj.CheckType(c4d.Opolygon):
            lst.append(obj)
        getPolyObj(obj.GetDown(), lst)
        obj = obj.GetNext()
    return lst  


def getPtsPoly(poly,obj):
    return obj.GetPoint(poly.a),obj.GetPoint(poly.b),obj.GetPoint(poly.c),obj.GetPoint(poly.d)

def recup_norm(poly, obj) :
    a,b,c,d = getPtsPoly(poly,obj)
    normale = (a - c).Cross(b - d)
    normale.Normalize()
    return normale

def isInMin(poly,obj, miny):
    a,b,c,d = getPtsPoly(poly,obj)
    return a.y==miny and b.y==miny and c.y==miny

def touchMin(poly,obj, miny):
    """renvoie vrai si au moins un des points est un point minimum"""
    a,b,c,d = getPtsPoly(poly,obj)
    return a.y==miny or b.y==miny or c.y==miny
    

def classementPolygone(op):
    
    tag_base = c4d.SelectionTag(c4d.Tpolygonselection)
    tag_base.SetName(SELECTION_NAME_BASES)
    bs_base = tag_base.GetBaseSelect()
    
    tag_facade = c4d.SelectionTag(c4d.Tpolygonselection)
    tag_facade.SetName(SELECTION_NAME_FACADES)
    bs_facade = tag_facade.GetBaseSelect()
    
    tag_toit = c4d.SelectionTag(c4d.Tpolygonselection)
    tag_toit.SetName(SELECTION_NAME_TOITS)
    bs_toit = tag_toit.GetBaseSelect()
    #on récupère le tyype d'objet
    #dans le cas des Bâtiment ouvert et Toits flottants qu'on ne prenne pas la base
    typ_obj = op.GetName()
    
    #si on a un type "Bâtiment ouvert" ou "Toit flottant" on considère
    #que c'est tout de la toiture
    #if typ_obj=='Bâtiment ouvert' or typ_obj == 'Toit flottant':
        #for i in xrange(op.GetPolygonCount()):
            #bs_toit.Select(i)
    
    #on prend le minimum en y pour détecter le plancher
    y = [p.y for p in op.GetAllPoints()]
    miny = min(y)
    
    
    #maxy = max(y)
    
    #calcul des normales
    for i,p in enumerate(op.GetAllPolygons()):
        norm =recup_norm(p, op)
        norm.y = round(norm.y,3)
        
        #BASE
        if  norm == c4d.Vector(0,-1,0) and isInMin(p,op, miny):
            bs_base.Select(i)
            
        #FACADES
        elif norm.y ==0:#and touchMin(p,op, miny):
            bs_facade.Select(i)
        
        #TOITS
        else:
            bs_toit.Select(i)
        
    if bs_base.GetCount():
        op.InsertTag(tag_base)
    if bs_toit.GetCount():
        op.InsertTag(tag_toit)
    if bs_facade.GetCount():
        op.InsertTag(tag_facade)
        

def importSwissBuildings(path, doc, cube_mnt):
    cube_mnt = cube_mnt.GetClone()
    cube_mnt.SetMg(c4d.Matrix(cube_mnt.GetMg()))
    
    origine = doc[CONTAINER_ORIGIN]
    
    
    doc = c4d.documents.BaseDocument()
    #document en mètre
    usdata = doc[c4d.DOCUMENT_DOCUNIT]
    scale, unit = usdata.GetUnitScale()
    if  unit!= c4d.DOCUMENT_UNIT_M:
        #rep = c4d.gui.QuestionDialog(DOC_NOT_IN_METERS_TXT)
        #if not rep : return
        unit = c4d.DOCUMENT_UNIT_M
        usdata.SetUnitScale(scale, unit)
        doc[c4d.DOCUMENT_DOCUNIT] = usdata
    #doc = c4d.documents.LoadDocument('temp', c4d.SCENEFILTER_NONE, thread=None)
    
    bbx = Bbox.fromObj(cube_mnt)    
    
    lst_dxfs = get_swissbuildings3D_dxfs(path)
    import_swissbuildings3D_from_list_dxf(lst_dxfs,doc, origin = origine)

    lst_swissbuildings =[]
    obj = doc.GetFirstObject()
    while obj :
        if 'swissbuildings3d' in obj.GetName():
            lst_swissbuildings.append(obj)
            obj = obj.GetNext()
        else: break
    
    buildings = c4d.BaseObject(c4d.Onull)
    buildings.SetName('swissbuildings3D')
    for obj in lst_swissbuildings:
        obj.InsertUnderLast(buildings)    
        
    #SUPPRESSION DES BATIMENTS HORS BBOX
    lst_supp = getBatiHorsBbox(bbx,buildings, lst = [])
    for obj in lst_supp:
        obj.Remove()
    
    #CONNEXION DES BATIMENTS RESTANTS
    lst_bat = getPolyObj(buildings, lst = [])
    batis = connect(lst_bat, nom = 'swissbuildings3D')
    
    #CONNEXION DES BATIMENTS RESTANTS
    #lst_bat = getPolyObj(buildings, lst = [])
    #batis = connect(lst_bat, nom = 'swissbuildings3D')


    boole = c4d.BaseObject(c4d.Oboole)
    boole[c4d.BOOLEOBJECT_HIGHQUALITY] = False
    boole[c4d.BOOLEOBJECT_TYPE] = c4d.BOOLEOBJECT_TYPE_INTERSECT

    cube_mnt.InsertUnder(boole)

    batis.InsertUnder(boole)

    doc.InsertObject(boole)

    doc_poly = doc.Polygonize()
    
    res = doc_poly.GetFirstObject().GetDown().GetClone()
    
    c4d.documents.KillDocument(doc)    
    c4d.documents.KillDocument(doc_poly)  
    classementPolygone(res)
    return res

def main():
    path = '/Users/olivierdonze/Documents/TEMP/test_dwnld_swisstopo/PLO/swisstopo'
    doc = c4d.documents.GetActiveDocument()
    cube_mnt = op
    buildings = importSwissBuidings(path, doc, cube_mnt)
    
    doc.InsertObject(buildings)
    c4d.EventAdd()

if __name__=='__main__':
    main()
