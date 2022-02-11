import c4d
import json
import urllib.request, urllib.error, urllib.parse


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

def write_jsonfile(data,fn_dst):
    try:
        with open(fn_dst,'w') as f:
            f.write(json.dumps(data))
    except:
        return False
    return True

#########################################################################
#MAIN FUNCTIONS
#########################################################################

#EXTRACTION DES ARBRES ISOLES (points 3D qui représentent le sommet de la couronne)

def url_geojson_trees(bbox_or_spline,origine):
    """ si une spline est dans bbox_or_spline renvoie les élément à l'intérieur du polygone,
        si c'est' un tuple de 4 float (bbox) renvoie les élément à l'intérieur de la bbox"""
    url_base = 'https://hepiadata.hesge.ch/arcgis/rest/services/suisse/TLM_C4D_couverture_sol/FeatureServer/0'
    xmin=ymin=xmax=ymax = None
    try:  sp = bbox_or_spline.GetRealSpline()
    except : sp = None
    if not sp:
        try:
            xmin,ymin,xmax,ymax = bbox_or_spline
            float(xmin),float(ymin),float(xmax),float(ymax)
        except: pass

    if not sp and not xmin:
        raise TypeError("bbox_or_spline must be a tuple of 4 floats or a SplineObject")

    #par défaut on met les paramètres selon la bbox (enveloppe)
    params = {
                "geometry" : f"{xmin},{ymin},{xmax},{ymax}",
                "geometryType": "esriGeometryEnvelope",
                "returnGeometry":"true",
                "returnZ": "true",
                "spatialRel":"esriSpatialRelIntersects",
                "f":"geojson"
              }
    #si on a une spline on change ces deux paramètres
    if sp:
        params["geometry"] = spline2json(sp,origine)
        params["geometryType"] = "esriGeometryPolygon"

    url = get_url(url_base,params)
    return url

def geojson_trees(bbox_or_spline,origine,fn_dst):
    """ si une spline est dans bbox_or_spline renvoie les élément à l'intérieur du polygone,
        si c'est' un tuple de 4 float (bbox) renvoie les élément à l'intérieur de la bbox"""
    url = url_geojson_trees(bbox_or_spline,origine)
    data = get_json_from_url(url)

    error = data.get("error",None)
    if error:
        print (Warning(f"geojson_trees : code : {error['code']}, {error['message']},{error['details']}"))
        return False

    if data:
        return write_jsonfile(data,fn_dst)

    return False

#EXTRACTION DES FORETS (surfaces polygonales selon valeurs de la liste catégories du champ OBJEKTART)

def url_geojson_forest(bbox_or_spline,origine):
    """ si une spline est dans bbox_or_spline renvoie les élément à l'intérieur du polygone,
        si c'est' un tuple de 4 float (bbox) renvoie les élément à l'intérieur de la bbox"""

    url_base = 'https://hepiadata.hesge.ch/arcgis/rest/services/suisse/TLM_C4D_couverture_sol/FeatureServer/1'
    xmin=ymin=xmax=ymax = None
    try:  sp = bbox_or_spline.GetRealSpline()
    except : sp = None
    if not sp:
        try:
            xmin,ymin,xmax,ymax = bbox_or_spline
            float(xmin),float(ymin),float(xmax),float(ymax)
        except: pass

    if not sp and not xmin:
        raise TypeError("bbox_or_spline must be a tuple of 4 floats or a SplineObject")

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

    #par défaut on met les paramètres selon la bbox (enveloppe)
    params = {
                "geometry" : f"{xmin},{ymin},{xmax},{ymax}",
                "geometryType": "esriGeometryEnvelope",
                "returnGeometry":"true",
                "outFields":"OBJEKTART",
                "orderByFields" : "OBJEKTART",
                "where" : f"{sql}",
                "returnZ": "true",
                "spatialRel":"esriSpatialRelIntersects",
                "f":"geojson"
              }

    #si on a une spline on change ces deux paramètres
    if sp:
        params["geometry"] = spline2json(sp,origine)
        params["geometryType"] = "esriGeometryPolygon"

    url = get_url(url_base,params)
    return url

def geojson_forest(bbox_or_spline,origine,fn_dst):
    """ si une spline est dans bbox_or_spline renvoie les élément à l'intérieur du polygone,
            si c'est' un tuple de 4 float (bbox) renvoie les élément à l'intérieur de la bbox"""
    url = url_geojson_forest(bbox_or_spline,origine)
    data = get_json_from_url(url)

    error = data.get("error",None)
    if error:
        print (Warning(f"geojson_trees : code : {error['code']}, {error['message']},{error['details']}"))
        return False

    if data:
        return write_jsonfile(data,fn_dst)

    return False

# Main function
def main():

    fn_dst_trees = '/Users/olivierdonze/Documents/TEMP/test_geojson_trees_swisstopo/trees.geojson'
    fn_dst_forest = '/Users/olivierdonze/Documents/TEMP/test_geojson_trees_swisstopo/forest.geojson'
    origine = doc[CONTAINER_ORIGIN]

    use_spline = False

    bbox = empriseObject(op,origine)

    #si on utilise la spline sélectionnée pour découper on envoie la spline comme premier argument
    if use_spline:
        print(geojson_trees(op,origine,fn_dst_trees))
        print(geojson_forest(op,origine,fn_dst_forest))

    #sinon on envoie la bbox
    else:
        print(geojson_trees(bbox,origine,fn_dst_trees))
        print(geojson_forest(bbox,origine,fn_dst_forest))


    return




    url_base_forest = 'https://hepiadata.hesge.ch/arcgis/rest/services/suisse/TLM_C4D_couverture_sol/FeatureServer/1'


    if use_spline:
        #Points selon spline sélectionnée
        res = geojson_trees_from_spline(op,url_base_trees,origine,fn_dst_trees)
        print(res)

        #Polygoness selon spline sélectionnée
        res = geojson_forest_from_spline(op,url_base_forest,origine,fn_dst_forest)
        print(res)

    else:
        #Points selon bbox
        res = geojson_trees_from_bbox(xmin,ymin,xmax,ymax,url_base_trees,origine,fn_dst_trees)
        print(res)

        #Polygoness selon bbox
        res = geojson_forest_from_bbox(xmin,ymin,xmax,ymax,url_base_forest,origine,fn_dst_forest)
        print(res)

# Execute main()
if __name__=='__main__':
    main()