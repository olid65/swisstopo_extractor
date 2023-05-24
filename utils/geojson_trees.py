import c4d
import json
import os.path
import sys
from pprint import pprint

#sys.path.append('/Users/olivierdonze/Library/Preferences/Maxon/Maxon Cinema 4D R25_EBA43BEE/library/scripts/swisstopo/utils')
#import geojson
#from geojson import Feature, Point, FeatureCollection

# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

CONTAINER_ORIGIN = 1026473

CATEGORIES ={'Gebueschwald':'Forêt buissonnante',
             'Wald':'Forêt',
             'Wald offen': 'Forêt claisemée',
             'Gehoelzflaeche':'Zone boisée',
             }

def createSpline(pts,segments, name):
    pcnt = len(pts)
    sp = c4d.SplineObject(pcnt,c4d.SPLINETYPE_LINEAR)
    sp[c4d.SPLINEOBJECT_CLOSED] = True
    sp.SetAllPoints(pts)
    sp.SetName(name)

    #ajout des segments s'il y en a plus que 1
    if len(segments)>1:
        sp.ResizeObject(pcnt, len(segments))
        for i,cnt in enumerate(segments):
            sp.SetSegment(i,cnt,closed = True)
    sp.Message(c4d.MSG_UPDATE)
    return sp

###########################################################
# LECTURE FICHIERS JSON
############################################################

def pointObjectFromGeojson(fn,origine, color = c4d.Vector4d(0.0, 1.0, 0.0, 1.0)):
    """ renvoie un objet polygonal avec uniquement les points du fichier geojson
        avec un vertex color tag qui affiche toujours les points selon color"""
    basename = os.path.basename(fn)
    with open(fn) as f:
        data = json.load(f)
        error = data.get('error',None)
        if error:
            print(f"'{os.path.basename(fn)}' n'a pas été téléchargé correctement")
            print(f"code : {error['code']} {error['message']}")
            for detail in error['details']:
                print(f"--> {detail}")
            return None


        pts = []
        features = data.get('features',None)
        if not features:
            print(f"No 'features' in {basename}")
            return None

        for feat in features:
            x,y,z = feat['geometry']['coordinates']
            pts.append(c4d.Vector(x,z,y)-origine)


        nb_pts = len(pts)
        pos = sum(pts)/nb_pts
        pts = [p-pos for p in pts]

        res = c4d.PolygonObject(nb_pts,0)
        res.SetAllPoints(pts)
        res.SetName(basename)

        #vertex_color_tag = c4d.VertexColorTag(nb_pts)
        #vertex_color_tag[c4d.ID_VERTEXCOLOR_DRAWPOINTS] = True

        #data = vertex_color_tag.GetDataAddressW()
        #for idx in range(nb_pts):
            #c4d.VertexColorTag.SetPoint(data, None, None, idx, color)
        #res.InsertTag(vertex_color_tag)

        res.SetAbsPos(pos)

        return res

def splinesFromGeojson(fn,origine):

    basename = os.path.basename(fn)
    with open(fn) as f:
        data = json.load(f)
        error = data.get('error',None)
        if error:
            print(f"'{os.path.basename(fn)}' n'a pas été téléchargé correctement")
            print(f"code : {error['code']} {error['message']}")
            for detail in error['details']:
                print(f"--> {detail}")
            return None

        features = data.get('features',None)
        if not features:
            print(f"No 'features' in {basename}")
            return None

        res = []
        segments = []
        pts = []
        cat = None

        for feat in features:

            if not cat :
                cat = feat['properties']['objektart']

            #vu que lq requête trie par OBJEKTART
            #si la catégorie change on crée la spline
            #et on efface les listes
            if cat!= feat['properties']['objektart']:
                sp = createSpline(pts,segments, name = CATEGORIES[cat])
                res.append(sp)

                #on vide les listes
                pts.clear()
                segments.clear()
                cat = feat['properties']['objektart']

            geom = feat['geometry']
            for ring in geom['coordinates']:
                for i,(x,y,z) in enumerate(ring):
                    #ATTENTION JE N'AI PAS UTILISE LE Z POUR POUVOIR DECOUPER LES SPLINES ENSUITE
                    pts.append(c4d.Vector(x,0,y)-origine)
                segments.append(i+1)

        #por la dernière catégorie
        sp = createSpline(pts,segments,name = CATEGORIES[cat])
        res.append(sp)

        return res

    return None

def decoupeSpline(sp,sp_cut):
    splinemask = c4d.BaseObject(1019396 )#spline_mask
    splinemask[c4d.MGSPLINEMASKOBJECT_MODE]=c4d.MGSPLINEMASKOBJECT_MODE_AND
    splinemask[c4d.MGSPLINEMASKOBJECT_AXIS] =c4d.MGSPLINEMASKOBJECT_AXIS_XZ
    splinemask[c4d.MGSPLINEMASKOBJECT_CREATECAP] = False

    sp_clone = sp.GetClone()
    sp_clone.SetMg(c4d.Matrix(sp.GetMg()))

    sp_cut_clone = sp_cut.GetClone()
    sp_cut_clone.SetMg(c4d.Matrix(sp_cut.GetMg()))
    

    sp_cut_clone.InsertUnder(splinemask)
    sp_clone.InsertUnder(splinemask)


    doc_temp = c4d.documents.BaseDocument()
    doc_temp.InsertObject(splinemask)

    doc_poly = doc_temp.Polygonize()

    res = doc_poly.GetFirstObject()

    if res :
        res = res.GetClone()
        res.SetMg(c4d.Matrix(res.GetMg()))
        res.SetName(sp.GetName())
        #mise à 0 des altitudes des points
        pts = [c4d.Vector(p.x,0,p.z) for p in res.GetAllPoints()]
        res.SetAllPoints(pts)
        res.Message(c4d.MSG_UPDATE)



    c4d.documents.KillDocument(doc_poly)
    c4d.documents.KillDocument(doc_temp)
    return res





# Main function
def main():
    sp_cut = op
    if not sp_cut.GetRealSpline():
        sp_cut = None

    fn_trees = '/Users/olivierdonze/Documents/TEMP/test_dwnld_swisstopo/Trient2/swisstopo/trees.geojson'
    #fn = '/Users/olivierdonze/Documents/TEMP/test_geojson_trees_swisstopo/exemple_404.geojson'

    fn_forest = '/Users/olivierdonze/Documents/TEMP/test_dwnld_swisstopo/Trient2/swisstopo/forest.geojson'

    origine = doc[CONTAINER_ORIGIN]
    if not origine:
        print("Pas d'origine")
        return

    #ARBRES ISOLES
    isol_trees = pointObjectFromGeojson(fn_trees,origine)

    if isol_trees:
        doc.InsertObject(isol_trees)


    #FORETS

    # import du fichier geojson sous forme de splines
    # une spline par catégorie du champs objektart
    # (les données geojson doivent être triée selon ce champ lors du téléchargement)
    forets = splinesFromGeojson(fn_forest,origine)
    if not forets:
        print("Pas de forêt")
        return

    null_foret = c4d.BaseObject(c4d.Onull)
    null_foret.SetName(os.path.basename(fn_forest))

    #decoupage selon la spline sélectionnée
    if sp_cut:
        for sp in forets:
            sp_res = decoupeSpline(sp,sp_cut)
            if sp_res:
                sp_res.InsertUnder(null_foret)
    else:
        for sp in forets:
            sp_res.InsertUnder(null_foret)
    doc.InsertObject(null_foret)






    c4d.EventAdd()







# Execute main()
if __name__=='__main__':
    main()