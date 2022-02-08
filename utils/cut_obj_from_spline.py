import c4d

# Welcome to the world of Python


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

def volumeFromSpline(sp, alt_base = 0, alt_haut = 5000):
    doc = c4d.documents.BaseDocument()
    #si ce n'est pas une spline
    if not sp.GetRealSpline():
        return None
    clone = sp.GetClone()

    #calcul du point le plus haut de la spline
    alt_max_sp = max([(p*sp.GetMg()).y for p in sp.GetRealSpline().GetAllPoints()])

    #connector
    connect = c4d.BaseObject(c4d.Oconnector)
    mg = c4d.Matrix(sp.GetMg())

    #translation pour que la base soit bien à alt_base
    pos = mg.off
    pos.y-= alt_max_sp-alt_base
    mg.off=pos
    connect.SetMg(mg)

    #extrusion
    extr = c4d.BaseObject(c4d.Oextrude)
    extr[c4d.EXTRUDEOBJECT_DIRECTION] = c4d.EXTRUDEOBJECT_DIRECTION_Y
    extr[c4d.EXTRUDEOBJECT_EXTRUSIONOFFSET] = alt_haut
    extr.InsertUnder(connect)
    extr.SetMl(c4d.Matrix())
    clone.InsertUnder(extr)
    clone.SetMl(c4d.Matrix())
    
    doc.InsertObject(connect)
    doc_poly = doc.Polygonize()

    res = doc_poly.GetFirstObject().GetClone()

    c4d.documents.KillDocument(doc)
    c4d.documents.KillDocument(doc_poly)

    return res

def decoupeMNTfromVolume(mnt,volume_decoupe):
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

    boole = c4d.BaseObject(c4d.Oboole)
    boole[c4d.BOOLEOBJECT_HIGHQUALITY] = False
    boole[c4d.BOOLEOBJECT_TYPE] = c4d.BOOLEOBJECT_TYPE_INTERSECT


    mnt.GetClone().InsertUnder(boole)

    volume_decoupe.InsertUnderLast(boole)

    doc.InsertObject(boole)

    doc_poly = doc.Polygonize()

    res = doc_poly.GetFirstObject().GetDown().GetClone()

    c4d.documents.KillDocument(doc)
    c4d.documents.KillDocument(doc_poly)

    return res


# Main function
def main():
    mnt = op
    sp = op.GetNext()
    volume_decoupe = volumeFromSpline(sp)

    if volume_decoupe:
        res = decoupeMNTfromVolume(mnt,volume_decoupe)
        if res :
            doc.InsertObject(res)
            c4d.EventAdd()

# Execute main()
if __name__=='__main__':
    main()