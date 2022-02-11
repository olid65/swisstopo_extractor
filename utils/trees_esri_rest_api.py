import c4d
import json
import urllib.request, urllib.error, urllib.parse
from pprint import pprint


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

CONTAINER_ORIGIN = 1026473


def spline2json(sp,origine):
    """pour géométrie JSON à mettre sous geometry de la requête
       et indiquer sous geometryType=esriGeometryPolygon"""
    res = {}
    res["spatialReference"] = {"wkid" : 2056}
    mg = sp.GetMg()
    sp = sp.GetRealSpline()
    if not sp: return None
    pts = [p*mg+origine for p in sp.GetAllPoints()]

    nb_seg = sp.GetSegmentCount()
    if not nb_seg:
        res["rings"] = [[[p.x,p.z] for p in pts]]

    else:
        res["rings"] = []
        id_pt = 0
        for i in range(nb_seg):
            cnt = sp.GetSegment(i)['cnt']
            res["rings"].append([[p.x,p.z] for p in pts[id_pt:id_pt+cnt]])
            id_pt+=cnt
    return json.dumps(res)

def empriseObject(obj, origine):
    mg = obj.GetMg()

    rad = obj.GetRad()
    centre = obj.GetMp()

    # 4 points de la bbox selon orientation de l'objet
    pts = [c4d.Vector(centre.x + rad.x, centre.y + rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y + rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y - rad.y, centre.z + rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y - rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y - rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y + rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x - rad.x, centre.y + rad.y, centre.z - rad.z) * mg,
           c4d.Vector(centre.x + rad.x, centre.y - rad.y, centre.z + rad.z) * mg]

    mini = c4d.Vector(min([p.x for p in pts]), min([p.y for p in pts]), min([p.z for p in pts])) + origine
    maxi = c4d.Vector(max([p.x for p in pts]), max([p.y for p in pts]), max([p.z for p in pts])) + origine

    return mini.x,mini.z,maxi.x,maxi.z


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

##########################################################################################

def get_json_from_url(url):
    req = urllib.request.Request(url=url)
    try :
        resp = urllib.request.urlopen(req)

    except urllib.error.HTTPError as e:
        print(f'HTTPError: {e.code}')
        return None

    except urllib.error.URLError as e:
        # Not an HTTP-specific error (e.g. connection refused)
        # ...
        print(f'URLError: {e.reason}')
        return None

    else:
        # 200
        data = json.loads(resp.read().decode("utf-8"))
        return data

    return None

def get_url(url_base,params):
    #Il faut un /query? à la fin de l'url de base
    end = '/query?'
    if url_base[-len(end):]!= end:
        #s'il y a déjà le slash à la fin'
        if url_base[-1] == '/':
            url_base+= end[1:]
        else:
            url_base+=end
    #encodage de l'url pour éviter les espaces et cararctères spéciaux
    query_string = urllib.parse.urlencode( params )
    return url_base + query_string

##########################################################################
#GEOMETRIES DEPUIS RESULTAT JSON

def pointobj_from_json_data(data,origine):
    """pour les layers de type esriGeometryPoint
       retourne un PointObject avec les points 3D ou 2D si pas de z"""
    pts = []
    for feat in data['features']:
        geom = feat['geometry']

        pts.append(c4d.Vector(geom['x'],geom.get('z',0),geom['y'])-origine)

    res = c4d.PolygonObject(len(pts),0)
    res.SetAllPoints(pts)
    res.Message(c4d.MSG_UPDATE)
    return res

def closedsplines_from_json_data(data,origine,categories):
    """pour les layers de type esriGeometryPoint
       retourne un PointObject avec les points 3D ou 2D si pas de z"""
    #stockage du nombre de points par segement

    res = c4d.BaseObject(c4d.Onull)
    res.SetName('couverture_sol')
    segments = []
    pts = []
    cat = None

    for feat in data['features']:
        if not cat :
            cat = feat['attributes']['objektart']

        #vu que lq requête trie par OBJEKTART
        #si la catégorie change on crée la spline
        #et on efface les listes
        if cat!= feat['attributes']['objektart']:
            sp = createSpline(pts,segments, name = categories[cat])
            sp.InsertUnderLast(res)

            #on vide les listes
            pts.clear()
            segments.clear()
            cat = feat['attributes']['objektart']

        geom = feat['geometry']
        for ring in geom['rings']:
            for i,(x,y,z) in enumerate(ring):
                #ATTENTION JE N'AI PAS UTILISE LE Z POUR POUVOIR DECOUPER LES SPLINES ENSUITE
                pts.append(c4d.Vector(x,0,y)-origine)
            segments.append(i+1)

    sp = createSpline(pts,segments,name = categories[cat])
    sp.InsertUnderLast(res)
    return res

def opensplines_from_json_data(data):
    pass


#########################################################################
#MAIN FUNCTIONS
#########################################################################

def pts_from_spline(sp,url_base,origine):
    poly_json = spline2json(sp,origine)
    if poly_json:
        params = {
                    "geometry": poly_json,
                    "geometryType": "esriGeometryPolygon",
                    "returnGeometry":"true",
                    "returnZ": "true",
                    "spatialRel":"esriSpatialRelIntersects",
                    "f":"json"
                }
        url = get_url(url_base,params)
        data = get_json_from_url(url)
        return pointobj_from_json_data(data,origine)
    return False

def pts_from_bbox(xmin,ymin,xmax,ymax,url_base,origine):
    params = {
                "geometry" : f"{xmin},{ymin},{xmax},{ymax}",
                "geometryType": "esriGeometryEnvelope",
                "returnGeometry":"true",
                "returnZ": "true",
                "spatialRel":"esriSpatialRelIntersects",
                "f":"json"
              }
    url = get_url(url_base,params)
    data = get_json_from_url(url)
    return pointobj_from_json_data(data,origine)

def polygons_from_spline(sp,url_base,origine):
    poly_json = spline2json(sp,origine)
    if poly_json:
        #catégories dans le champ OBJEKTART que l'on récupère'
        categories ={'Gebueschwald':'Forêt buissonnante',
                     'Wald':'Forêt',
                     'Wald offen': 'Forêt claisemée',
                     'Gehoelzflaeche':'Zone boisée',
                     }
        sql = ''
        for i,cat in enumerate(categories.keys()):

            if i>0 :
                sql+=' OR '
            sql+=f"OBJEKTART='{cat}'"
        #&outFields=OBJEKTART&orderByFields=OBJEKTART
        params = {
                    "geometry": poly_json,
                    "geometryType": "esriGeometryPolygon",
                    "returnGeometry":"true",
                    "outFields":"OBJEKTART",
                    "orderByFields" : "OBJEKTART",
                    "where" : f"{sql}",
                    "returnZ": "true",
                    "spatialRel":"esriSpatialRelIntersects",
                    "f":"json"
                }
        url = get_url(url_base,params)
        print(url)
        data = get_json_from_url(url)
        return closedsplines_from_json_data(data,origine,categories)
    return False

def polygons_from_bbox(xmin,ymin,xmax,ymax,url_base,origine):
    pass


# Main function
def main():

    origine = doc[CONTAINER_ORIGIN]

    url_base = 'https://hepiadata.hesge.ch/arcgis/rest/services/suisse/TLM_C4D_couverture_sol/FeatureServer/1'

    #Polygoness selon spline sélectionnée
    splines = polygons_from_spline(op,url_base,origine)
    if splines:
        doc.InsertObject(splines)
        c4d.EventAdd()
    return

    url_base = 'https://hepiadata.hesge.ch/arcgis/rest/services/suisse/TLM_C4D_couverture_sol/FeatureServer/0'
    #Points selon bbox de l'objet sélectionné
    xmin,ymin,xmax,ymax = empriseObject(op, origine)
    print(xmin,ymin,xmax,ymax)
    obj_pts = pts_from_bbox(xmin,ymin,xmax,ymax,url_base,origine)

    doc.InsertObject(obj_pts)
    c4d.EventAdd()
    return

    #Points selon spline sélectionnée
    obj_pts = pts_from_spline(op,url_base,origine)

    doc.InsertObject(obj_pts)
    c4d.EventAdd()


# Execute main()
if __name__=='__main__':
    main()