# -*- coding: utf-8 -*-

# Modifié le 27 octobre 2017:
#  gestion des fichiers à 7 lignes d'entête avec dx et dy au lieu de cellsize'

import c4d, re
import os.path

CONTAINER_ORIGIN = 1026473


def insert_geotag(obj, origine):
    geotag = c4d.BaseTag(1026472)
    geotag[CONTAINER_ORIGIN] = origine
    obj.InsertTag(geotag)


def polygonise(obj, nb_rows, nb_cols):
    id_poly = 0
    id_pt = 0
    for r in range(nb_rows):
        for c in range(nb_cols):
            if c < (nb_cols - 1) and r < (nb_rows - 1):
                try:
                    #id_pt, id_pt + nb_cols, id_pt + 1 + nb_cols, id_pt + 1
                    # id_pt, id_pt + 1, id_pt + 1 + nb_cols, id_pt + nb_cols

                    obj.SetPolygon(id_poly, c4d.CPolygon(id_pt, id_pt + 1, id_pt + 1 + nb_cols, id_pt + nb_cols))
                except:
                    print (id_poly, '->', (id_pt, id_pt + nb_cols, id_pt + 1 + nb_cols, id_pt + 1))
                id_poly += 1
            id_pt += 1


def terrainFromASC(fn):
    """Attention le doc doit être en mètres"""
    name = os.path.basename(fn).split('.')[0]

    nb = 0
    header = {}
    # lecture de l'entête pour savoir si on a 5 ou 6 lignes ( il y a des fichiers qui n'ont pas la ligne nodata)
    # ou encore 7 lignes commes qgis avec valeurs différentes pour dx, dy
    with open(fn, 'r') as file:
        virgule = False
        while 1:
            s = file.readline()
            split = s.split()
            # si la première partie de split commence par un chiffre ou par le signe moins on break
            if re.match(r'^[0-9]', split[0]) or re.match(r'^-', split[0]): break
            k, v = split
            # si on a une virgule dans v c'est que le fichier est en virgule
            # ça arrive quand les paramètres régionaux de Windows ont , comme cararctère décimal
            if v.find(","):
                virgule = True

            if virgule:
                v = v.replace(",", ".")

            header[k.lower()] = v  # QGIS met le NODATA_value en partie en majuscule !!!
            nb += 1

    ncols = int(header['ncols'])
    nrows = int(header['nrows'])
    xcorner = float(header['xllcorner'].replace(',','.'))
    ycorner = float(header['yllcorner'].replace(',','.'))

    # on teste si on a une valeur cellsize
    if header.get('cellsize', None):
        cellsize = float(header['cellsize'].replace(',','.'))
        dx = cellsize
        dy = cellsize
    # sinon on récupère dx et dy
    else:
        dx = float(header['dx'].replace(',','.'))
        dy = float(header['dy'].replace(',','.'))

    nodata = 0.
    if nb == 6 or nb == 7:
        try:
            nodata = float(header['nodata_value'].replace(',','.'))
        except:
            nodata = 0.

    # lecture des altitudes
    with open(fn, 'r') as file:
        # on saute l'entête
        for i in range(nb): file.readline()

        nb_pts = ncols * nrows
        nb_poly = (ncols - 1) * (nrows - 1)
        poly = c4d.PolygonObject(nb_pts, nb_poly)
        poly.SetName(name)
        origine = c4d.Vector(xcorner, 0, ycorner + nrows * dy)

        pos = c4d.Vector(0)
        i = 0
        for r in range(nrows):
            for val in file.readline().split():
                if virgule:
                    val = val.replace(",", ".")

                y = float(val)
                if y == nodata: y = 0.0
                pos.y = y
                poly.SetPoint(i, pos)
                pos.x += dx
                i += 1
            pos.x = 0
            pos.z -= dy

    polygonise(poly, nrows, ncols)
    insert_geotag(poly, origine)
    tag = c4d.BaseTag(c4d.Tphong)
    tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
    poly.InsertTag(tag)

    poly.Message(c4d.MSG_UPDATE)
    return poly


def main(fn=None):
    doc = c4d.documents.GetActiveDocument()
    # DOCUMENT EN METRE
    data = doc[c4d.DOCUMENT_DOCUNIT]
    data.SetUnitScale(1, c4d.DOCUMENT_UNIT_M)
    doc[c4d.DOCUMENT_DOCUNIT] = data

    if not fn:
        fn = c4d.storage.LoadDialog()
    # fn = '/Users/donzeo/Documents/Mandats/Concours_RADE_2017/C4D/SIG/MNT_2013_50cm.asc'

    if not fn: return
    if not os.path.splitext(fn)[1] == '.txt' and not os.path.splitext(fn)[1] == '.asc':
        c4d.gui.MessageDialog("Ce n'est pas un fichier de terrain (.txt ou .asc)")
        return
    # fn = '/Volumes/HD_OD/Eoliennes_Mollendruz/SIG/ARC_leman_def/test100MNT.asc'

    terrain = terrainFromASC(fn)

    doc.InsertObject(terrain)
    doc.SetActiveObject(terrain)
    c4d.CallCommand(12151) # Zoom sur l'objet actif
    c4d.EventAdd()
    return


if __name__ == '__main__':
    main()
