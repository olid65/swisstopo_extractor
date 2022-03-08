import c4d
import os
from math import pi


PLUGIN_ID = 1059170

#Sélectionner d'abord l'objet plan puis l'objet sur lequel on veut mettre le matériau
#s'il n'y a pas déjà une propriété matériau avec ce matériau, crée la propriété
#ajuste selon le plan (si la propriété existe, la modifie)
#ne fonctionnne que pour les plans en vue de haut !



#TODO : il y a encore des soucis si l'objet source est en enfant d'un autre objet
#régler ces histoires de matrices de rotation pour l'instant c'est du bricolage!!!!!!
#voir ligne 93

PRECISION = 0.001

def poly2plane(op):
    #on regarde s'il y a 4 points'
    if op.GetPointCount()!= 4:
        return None

    pts = [p*op.GetMg() for p in op.GetAllPoints()]

    #attention un objet plan a les points qui ne tourne pas logiquement
    #il faut prendre le polygone pour avoir le bon sens
    poly = op.GetPolygon(0)

    #on vérifie qu'il y a bien des angles droit
    v1 = pts[poly.b]-pts[poly.a]
    v2 = pts[poly.c]-pts[poly.b]
    v3 = pts[poly.d]-pts[poly.c]
    v4 = pts[poly.a]-pts[poly.d]

    height = v1.GetLength()
    width = v2.GetLength()

    if abs(c4d.utils.GetAngle(v2,v1) - pi/2) > PRECISION : return False
    if abs(c4d.utils.GetAngle(v3,v2) - pi/2) > PRECISION  : return False
    if abs(c4d.utils.GetAngle(v4,v3) - pi/2) > PRECISION  : return False
    if abs(c4d.utils.GetAngle(v1,v4) - pi/2) > PRECISION  : return False

    #calcul du centre
    lst_x = [p.x for p in pts]
    lst_y = [p.y for p in pts]
    lst_z = [p.z for p in pts]

    x = (max(lst_x)+min(lst_x))/2
    y = (max(lst_y)+min(lst_y))/2
    z = (max(lst_z)+min(lst_z))/2
    off = c4d.Vector(x,y,z)

    v3 = v1.GetNormalized()
    v1 = v2.GetNormalized()
    v2 = v1.Cross( v3)

    plane = c4d.BaseObject(c4d.Oplane)
    plane.SetMg(c4d.Matrix(off,v1,v2,v3))

    plane[c4d.PRIM_PLANE_WIDTH] = width
    plane[c4d.PRIM_PLANE_HEIGHT] = height

    #copie des tags de texture
    pred = None
    for tag in op.GetTags():
        if tag.CheckType(c4d.Ttexture):
            tag_clone = tag.GetClone()
            plane.InsertTag(tag_clone, pred = pred)
            pred = tag_clone
    return plane


# Main function
def transfert_mat(plane, obj_dst, doc):
    #si on n'a pas un plan on regarde si on a un objet polygonal rectangle qu'on transforme en plan
    if not plane.CheckType(c4d.Oplane):
        test = False
        if plane.CheckType(c4d.Opolygon):
            plane = poly2plane(plane)
            if plane : test = True
        if not test:
            c4d.gui.MessageDialog("Le premier objet sélectionné doit être un objet plan ou un polygone rectangle à 4 points")
            return None
    if not plane[c4d.PRIM_AXIS] == c4d.PRIM_AXIS_YP:
        c4d.gui.MessageDialog("Le plan n'est pas en orientation +Y")
        return


    #on prend le dernier tag texture
    tag = None
    for tg in plane.GetTags():
        if tg.CheckType(c4d.Ttexture):
            tag = tg

    if not tag :
        c4d.gui.MessageDialog("Il n'y a pas de propriété matériau sur le premier objet sélectionné")
        return
    mat = tag[c4d.TEXTURETAG_MATERIAL]

    tag_dst = None

    #on regarde s'il y a déjà un tag matériau en mode planaire avec le matériau
    for t in obj_dst.GetTags():
        if t.CheckType(c4d.Ttexture) and \
            t[c4d.TEXTURETAG_MATERIAL] == mat and \
            t[c4d.TEXTURETAG_PROJECTION]== c4d.TEXTURETAG_PROJECTION_FLAT:
            tag_dst = t
            doc.AddUndo(c4d.UNDOTYPE_CHANGE,tag_dst)
    #sinon on crée un tag matériau
    if not tag_dst:
        tag_dst = c4d.BaseTag(c4d.Ttexture)
        tag_dst[c4d.TEXTURETAG_MATERIAL] = mat
        tag_dst[c4d.TEXTURETAG_PROJECTION]= c4d.TEXTURETAG_PROJECTION_FLAT
        pred = None
        if obj_dst.GetTags():
            pred = obj_dst.GetTags()[-1]
        obj_dst.InsertTag(tag_dst,pred)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,tag_dst)

    #réglage du tag

    ml = c4d.Matrix(plane.GetMg() *~obj_dst.GetUpMg()* ~obj_dst.GetMl())
    tag_dst.SetMl(ml)

    #tag_dst.SetRot(c4d.Vector())

    tag_dst[c4d.TEXTURETAG_TILE] = False
    tag_dst[c4d.TEXTURETAG_ROTATION,c4d.VECTOR_Y] = -pi/2


    tag_dst[c4d.TEXTURETAG_SIZE,c4d.VECTOR_X] = plane[c4d.PRIM_PLANE_WIDTH]/2
    tag_dst[c4d.TEXTURETAG_SIZE,c4d.VECTOR_Y] = plane[c4d.PRIM_PLANE_HEIGHT]/2

    #rot = plane.GetMg().v1 * ~obj_dst.GetMl()
    rotx = plane.GetAbsRot().x - obj_dst.GetAbsRot().x

    #tag_dst[c4d.TEXTURETAG_ROTATION,c4d.VECTOR_X] = ml.v1.x

    pos = plane.GetMg().off *~obj_dst.GetUpMg()* ~obj_dst.GetMl()
    tag_dst[c4d.TEXTURETAG_POSITION] = pos

    #tag_dst[c4d.TEXTURETAG_POSITION]

    c4d.EventAdd()
    
    
# Main function
def main():
    try :
        plane, obj_dst = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
    except:
        c4d.gui.MessageDialog("Vous devez sélectioner deux objets, l'objet plan avec le matériau, puis l'objet de destination")
        return
    transfert_mat(plane, obj_dst)

class MaterialTransfer(c4d.plugins.CommandData):
    def Execute(self, doc):
        doc.StartUndo()
        try :
            plane, obj_dst = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
        except:
            c4d.gui.MessageDialog("Vous devez sélectioner deux objets, l'objet plan avec le matériau, puis l'objet de destination")
            return
        transfert_mat(plane, obj_dst,doc)
        doc.EndUndo()
        return True

def icone(nom) :
    bmp = c4d.bitmaps.BaseBitmap()
    dir, file = os.path.split(__file__)
    fn = os.path.join(dir, "res", nom)
    bmp.InitWith(fn)
    return bmp

# main
if __name__ == "__main__":
    # Registers the plugin
    c4d.plugins.RegisterCommandPlugin(id=PLUGIN_ID,
                                      str="#$04Transfert de matériau d'un plan sur un terrain",
                                      info=0,
                                      help="Sélectionner d'abord le plan et ensuite le terrain en appuyant sur CTRL/CMD",
                                      dat=MaterialTransfer(),
                                      icon=icone("od_material_transfer.tif"))
