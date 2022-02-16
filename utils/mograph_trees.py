import c4d
from random import random
from math import pi

# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

# SELECTIONNER L'OBJET POINTS DES SOMMETS DES ARBRES
# PROVENANT DU GEOJSON
# LE MNT DOIT ETRE PLACE JUSTE APRES

#IL FAUT EGALEMENT UN ARBRES SOURCES SELON NOM CI-DESSOUS

#ARBRES_SOURCES = doc.SearchObject('sources_vegetation')

DELTA_ALT = 100

RAPORT_HAUTEUR_DIAMETRE_MIN = 0.3

ID_CLONER = 1018544
ID_TAG_INFLUENCE_MOGRAPH = 440000231
ID_PLAIN_EFFECTOR = 1021337
ID_RANDOM_EFFECTOR = 1018643

NOM_OBJ_POINTS = "Arbres isolés"
NOM_CLONER = NOM_OBJ_POINTS + "_cloneur"
NOM_TAG_DIAMETRES = "diametres"
NOM_TAG_HAUTEURS = "hauteurs"
NOM_POINT_OBJECT = "points_" + NOM_OBJ_POINTS
NOM_EFFECTOR_DIAMETRES = "effecteur_" + NOM_TAG_DIAMETRES
NOM_EFFECTOR_HAUTEURS = "effecteur_" + NOM_TAG_HAUTEURS
NOM_EFFECTOR_RANDOM = "effecteur_rotation_aleatoire"

SUFFIX_EXTRACT = "_extrait"

NULL_NAME = NOM_OBJ_POINTS

HAUT_SRCE = 10.  # on part avec une source qui fait 10m de haut
DIAM_SRCE = 10.  # idem pour le diametre

FACTEUR_HAUT = 1.
FACTEUR_DIAMETRE = 0.5

#CLONE_QUANTITY = 1000

RAYON_SPHERE_DEFAULT = 6

def getMinMaxY(obj):
    """renvoie le minY et le maxY en valeur du monde d'un objet"""
    mg = obj.GetMg()
    alt = [(pt * mg).y for pt in obj.GetAllPoints()]
    return min(alt) - DELTA_ALT, max(alt) + DELTA_ALT

def changeAltAbs(pt, mg, alt):
    """modifie l'altitude selon le monde d'un points"""
    pt = pt * mg
    pt.y = alt
    return pt * ~mg

def area2Dpoly(pts):
    """calcule la surface planaire (x,z) d'un polygone
       d'après https://www.mathopenref.com/coordpolygonarea2.html"""
    area = 0
    j = len(pts) - 1
    for i in range(len(pts)):
        area += (pts[j].x + pts[i].x) * (pts[j].z - pts[i].z)
        j = i
    return area / 2.

def area2Dpolyobj(poly_obj):
    """calcule la surface 2D (xz) d'un objet polygonal"""
    area = 0
    mg = poly_obj.GetMg()
    pts = [p * mg for p in poly_obj.GetAllPoints()]
    polys = poly_obj.GetAllPolygons()

    for poly in polys:
        p1 = pts[poly.a]
        p2 = pts[poly.b]
        p3 = pts[poly.c]
        p4 = pts[poly.d]

        if p3 == p4:
            area += area2Dpoly([p1, p2, p3])
        else:
            area += area2Dpoly([p1, p2, p3, p4])
    return area


def pointsOnSurface(op,mnt):
    mg_op = op.GetMg()
    op = op.GetClone()
    op.SetMg(mg_op)
    grc = c4d.utils.GeRayCollider()
    grc.Init(mnt)

    mg_mnt = mnt.GetMg()
    invmg_mnt = ~mg_mnt
    invmg_op = ~op.GetMg()

    minY,maxY = getMinMaxY(mnt)

    ray_dir = ((c4d.Vector(0,0,0)*invmg_mnt) - (c4d.Vector(0,1,0)*invmg_mnt)).GetNormalized()
    length = maxY-minY
    for i,p in enumerate(op.GetAllPoints()):
        p = p*mg_op
        dprt = c4d.Vector(p.x,maxY,p.z)*invmg_mnt
        intersect = grc.Intersect(dprt,ray_dir,length)
        if intersect :
            pos = grc.GetNearestIntersection()['hitpos']
            op.SetPoint(i,pos*mg_mnt*invmg_op)

    op.Message(c4d.MSG_UPDATE)
    return op

def create_effector(name, select=None, typ=ID_PLAIN_EFFECTOR):
    res = c4d.BaseObject(typ)
    res.SetName(name)
    if select:
        res[c4d.ID_MG_BASEEFFECTOR_SELECTION] = select
    return res


##############################################################################
# MOGRAPH ARBRES ISOLES

def trees_mograph_cloner(doc, point_object, hauteurs, diametres, objs_srces, centre=None, name=None):
    # tag = doc.GetActiveTag()
    # return

    res = c4d.BaseObject(c4d.Onull)
    if not name: name = NULL_NAME
    res.SetName(name)

    if centre:
        creerGeoTag(res, doc, centre)

    cloner = c4d.BaseObject(ID_CLONER)
    cloner.SetName(NOM_CLONER)
    cloner[c4d.ID_MG_MOTIONGENERATOR_MODE] = 0  # mode objet
    cloner[c4d.MG_OBJECT_LINK] = point_object
    cloner[c4d.MG_POLY_MODE_] = 0  # mode point
    cloner[c4d.MG_OBJECT_ALIGN] = False
    cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] = 2  # multiinstances
    cloner[c4d.MGCLONER_MODE] = 2  # repartition aleatoire des clones

    # insertion des objets source
    if objs_srces:
        for o in objs_srces.GetChildren():
            clone = o.GetClone()
            clone.InsertUnderLast(cloner)

    tagHauteurs = c4d.BaseTag(440000231)
    cloner.InsertTag(tagHauteurs)
    tagHauteurs.SetName(NOM_TAG_HAUTEURS)
    # ATTENTION bien mettre des float dans la liste sinon cela ne marche pas !
    scale_factor_haut = lambda x: float(x) / HAUT_SRCE - 1.
    c4d.modules.mograph.GeSetMoDataWeights(tagHauteurs, [scale_factor_haut(h) for h in hauteurs])
    # tagHauteurs.SetDirty(c4d.DIRTYFLAGS_DATA) #plus besoin depuis la r21 !

    tagDiametres = c4d.BaseTag(440000231)
    cloner.InsertTag(tagDiametres)
    tagDiametres.SetName(NOM_TAG_DIAMETRES)
    scale_factor_diam = lambda x: float(x * 2) / DIAM_SRCE - 1.
    c4d.modules.mograph.GeSetMoDataWeights(tagDiametres, [scale_factor_diam(d) for d in diametres])
    # tagDiametres.SetDirty(c4d.DIRTYFLAGS_DATA) #plus besoin depuis la r21 !

    # Effecteur simple hauteurs
    effector_heights = create_effector(NOM_EFFECTOR_HAUTEURS, select=tagHauteurs.GetName())
    effector_heights[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = False
    effector_heights[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
    effector_heights[c4d.ID_MG_BASEEFFECTOR_SCALE, c4d.VECTOR_Y] = FACTEUR_HAUT

    # Effecteur simple diametres
    effector_diam = create_effector(NOM_EFFECTOR_DIAMETRES, select=tagDiametres.GetName())
    effector_diam[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = False
    effector_diam[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
    effector_diam[c4d.ID_MG_BASEEFFECTOR_SCALE] = c4d.Vector(FACTEUR_DIAMETRE, 0, FACTEUR_DIAMETRE)

    # Effecteur random
    effector_random = create_effector(NOM_EFFECTOR_RANDOM, typ=ID_RANDOM_EFFECTOR)
    effector_random[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = False
    effector_random[c4d.ID_MG_BASEEFFECTOR_ROTATE_ACTIVE] = True
    effector_random[c4d.ID_MG_BASEEFFECTOR_ROTATION, c4d.VECTOR_X] = pi * 2

    ie_data = cloner[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST]
    ie_data.InsertObject(effector_heights, 1)

    ie_data.InsertObject(effector_diam, 1)
    ie_data.InsertObject(effector_random, 1)
    cloner[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST] = ie_data

    cloner.Message(c4d.MSG_UPDATE)
    cloner.InsertUnder(res)
    effector_heights.InsertUnder(res)
    effector_diam.InsertUnder(res)
    effector_random.InsertUnder(res)
    point_object.InsertUnder(res)

    effector_heights.Message(c4d.MSG_MENUPREPARE, doc)
    effector_diam.Message(c4d.MSG_MENUPREPARE, doc)
    effector_random.Message(c4d.MSG_MENUPREPARE, doc)

    return res

def mograph_system_trees(trees_sommets, mnt, arbres_sources, doc):
    arbres_pts_base = pointsOnSurface(trees_sommets,mnt)
    arbres_pts_base.SetName('arbres_isoles_swisstopo_collets')
    
    #TODO : que faire quand la hauteur == 0
    hauteurs = [pt_sommet.y-pt_base.y for pt_sommet,pt_base in zip(trees_sommets.GetAllPoints(),arbres_pts_base.GetAllPoints())]

    #fonction lambda pour limiter la hauteur à 30m
    f = lambda x: x if x < 30 else 30
    hauteurs = list(map(f,hauteurs))

    rapport = RAPORT_HAUTEUR_DIAMETRE_MIN + random()*RAPORT_HAUTEUR_DIAMETRE_MIN
    diametres = [haut*rapport for haut in hauteurs]


    res = trees_mograph_cloner(doc, arbres_pts_base, hauteurs, diametres, arbres_sources, centre=None, name=None)
    return res

#####################################################################################################
# MOGRAPH FORET
#####################################################################################################

def volumeFromSpline(sp, minY, maxY):
    sp_clone = sp.GetClone()
    mg = sp.GetMg()
    # on met les points de la spline au minY
    pts = [changeAltAbs(p, mg, minY) for p in sp.GetAllPoints()]
    sp.SetAllPoints(pts)
    sp.Message(c4d.MSG_UPDATE)

    # extrusion
    extr = c4d.BaseObject(c4d.Oextrude)
    extr[c4d.EXTRUDEOBJECT_DIRECTION] = c4d.EXTRUDEOBJECT_DIRECTION_Y
    extr[c4d.EXTRUDEOBJECT_EXTRUSIONOFFSET] = maxY - minY
    #extr[c4d.EXTRUDEOBJECT_HIERARCHIC] = True
    sp.InsertUnder(extr)
    return extr

def cutMNTfromSpline(mnt, spline):
    """retourne une découpe de l'objet polygonal mnt selon la spline"""

    # calculation of altitude min and max from terrain (avec security margin)
    minY, maxY = getMinMaxY(mnt)

    # volume from spline for extraction
    extr = volumeFromSpline(spline, minY, maxY)

    # boolean
    boolObj = c4d.BaseObject(c4d.Oboole)
    boolObj[c4d.BOOLEOBJECT_TYPE] = c4d.BOOLEOBJECT_TYPE_INTERSECT
    boolObj[c4d.BOOLEOBJECT_HIGHQUALITY] = False

    extr.InsertUnder(boolObj)
    mnt.GetClone().InsertUnder(boolObj)

    # temporary file
    temp_doc = c4d.documents.BaseDocument()

    mnt_extract = None
    # TODO : manage exceptions if not ...
    if temp_doc:
        temp_doc.InsertObject(boolObj)
        temp_doc_polygonize = temp_doc.Polygonize()
        bool_res = temp_doc_polygonize.GetFirstObject()

        if bool_res:
            mnt_extract = bool_res.GetDown()

            if mnt_extract:
                mnt_extract.SetName(mnt.GetName() + SUFFIX_EXTRACT)
    
    res = mnt_extract.GetClone()
    c4d.documents.KillDocument(temp_doc)
    return res

def clonerFromPolyObject(poly_object, density, objs_to_clone=None):
    """renvoie un null contenant un cloner mograph en mode objet en mode quantité
       sur l'objet polygonal poly_object et un effecteur random avec rotation h aléatoire à 360°"""

    res = c4d.BaseObject(c4d.Onull)
    res.SetName('cloneur_mograph')
    
    #calcul de la quantité d'arbres en fonction de la surface
    surface = area2Dpolyobj(poly_object)
    nb_clones = surface*density

    # cloneur
    cloner = c4d.BaseObject(1018544)
    cloner[c4d.ID_MG_MOTIONGENERATOR_MODE] = c4d.ID_MG_MOTIONGENERATOR_MODE_OBJECT
    cloner[c4d.MGCLONER_MODE] = c4d.MGCLONER_MODE_RANDOM
    cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] = c4d.MGCLONER_VOLUMEINSTANCES_MODE_RENDERMULTIINSTANCE
    cloner[c4d.MG_OBJECT_LINK] = poly_object
    cloner[c4d.MG_POLY_MODE_] = c4d.MG_POLY_MODE_SURFACE
    cloner[c4d.MG_OBJECT_ALIGN] = False
    cloner[c4d.MG_POLYSURFACE_COUNT] = nb_clones
    cloner.InsertUnder(res)

    if objs_to_clone:
        for o in objs_to_clone:
            clone = o.GetClone()
            clone.InsertUnderLast(cloner)

    else:
        nobj = c4d.BaseObject(c4d.Onull)
        sphere = c4d.BaseObject(c4d.Osphere)
        sphere[c4d.PRIM_SPHERE_RAD] = RAYON_SPHERE_DEFAULT
        sphere.InsertUnder(nobj)
        sphere.SetRelPos(c4d.Vector(0, RAYON_SPHERE_DEFAULT, 0))

        nobj.InsertUnder(cloner)

    # random effector
    rdm_effector = c4d.BaseObject(1018643)
    in_ex_data = cloner[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST]
    in_ex_data.InsertObject(rdm_effector, 1)
    cloner[c4d.ID_MG_MOTIONGENERATOR_EFFECTORLIST] = in_ex_data

    rdm_effector[c4d.ID_MG_BASEEFFECTOR_POSITION_ACTIVE] = False
    rdm_effector[c4d.ID_MG_BASEEFFECTOR_ROTATE_ACTIVE] = True
    rdm_effector[c4d.ID_MG_BASEEFFECTOR_ROTATION, c4d.VECTOR_X] = pi * 2

    rdm_effector[c4d.ID_MG_BASEEFFECTOR_SCALE_ACTIVE] = True
    rdm_effector[c4d.ID_MG_BASEEFFECTOR_UNIFORMSCALE] = True
    rdm_effector[c4d.ID_MG_BASEEFFECTOR_POSITIVESCALE] = True
    rdm_effector[c4d.ID_MG_BASEEFFECTOR_USCALE] = 0.5

    rdm_effector.InsertUnder(res)
    return res

def arbresSurface(splines, mnt, name, arbres_source, density):
    res = c4d.BaseObject(c4d.Onull)
    res.SetName(name)

    mnt_extract = cutMNTfromSpline(mnt, splines)
    mnt_extract[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
    mnt_extract[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF

    if mnt_extract:
        mnt_extract = mnt_extract.GetClone()
        mnt_extract.InsertUnder(res)
        cloner = clonerFromPolyObject(mnt_extract, density, objs_to_clone=arbres_source.GetChildren())
        cloner.InsertUnderLast(res)
    return res

def mograph_system_forest(splines_forest, mnt, arbres_sources, doc, density = 0.02, name = 'Forêts'):
    
    res = c4d.BaseObject(c4d.Onull)
    res.SetName(name)
    
    for spline_foret in splines_forest:
        mo_forest =  arbresSurface(spline_foret.GetClone(), mnt, spline_foret.GetName(), arbres_sources, density)
        mo_forest.InsertUnder(res)
    
    return res


# Main function
def main():
    
    splines_forest = op.GetChildren()
    mnt = op.GetNext()
    #arbres_sources = ARBRES_SOURCES
    
    forest = mograph_system_forest(splines_forest, mnt, arbres_sources, density = 0.02)
    doc.InsertObject(forest)    
    c4d.EventAdd()
    
    return
    #TEST ARBRES ISOLES SELECTIONNER
    # SELECTIONNER L'OBJET POINTS DES SOMMETS DES ARBRES
    # PROVENANT DU GEOJSON
    # LE MNT DOIT ETRE PLACE JUSTE APRES
    trees_sommets = op
    mnt = op.GetNext()
    #arbres_sources = ARBRES_SOURCES
    trees = mograph_system_trees(trees_sommets, mnt, arbres_sources)
    doc.InsertObject(trees)
    c4d.EventAdd()
    return
# Execute main()
if __name__=='__main__':
    main()