# -*- coding: utf8 -*-

import c4d,os
import time
import numpy as nmpy
import math
#be sure to use a unique ID obtained from www.plugincafe.com
PLUGIN_ID = 1058813      

EPAISSEUR_PT = 3


def rectangle_from_3_points(p1,p2,p3):
    rect = c4d.BaseObject(c4d.Osplinerectangle)
    rect[c4d.PRIM_PLANE] = c4d.PRIM_PLANE_XZ
    
    length =  (p2-p1).GetLength()
    #height = c4d.utils.PointLineSegmentDistance(p1,p2,p3)[0]

    perpendiculaire = c4d.utils.PointLineDistance(p1, (p2-p1), p3)
    height = perpendiculaire.GetLength()

    
    rect[c4d.PRIM_RECTANGLE_WIDTH] = length
    rect[c4d.PRIM_RECTANGLE_HEIGHT] = height
    
    direction = (p2-p1).GetNormalized()
    
    mg = c4d.Matrix()
    
    mg.v1 = direction
    mg.v2 = c4d.Vector(0,1,0)
    mg.v3 = perpendiculaire.GetNormalized()
    
    mg.off = p1+mg.v1*length/2 + mg.v3*height/2
    rect.SetMg(mg)
    
    return rect

    
def pt_ortho(p1,p2):
    """renvoie p2 aligné sur p1 selon la 
       proximité de l'axe vertical ou horizontal"""
    v = p2-p1
    v.x = abs(v.x)  
    v.y = abs(v.y) 
    if v.x<v.y:
        p2.x = p1.x        
    elif v.x>v.y:
        p2.y = p1.y
    
    return p2

class Rectangle3Points(c4d.plugins.ToolData):
    """Inherit from ToolData to create your own tool"""

    p1=p2=None
    ps1=ps2=ps3=None
    rect = None

    mode_ortho = True
    

    def KeyboardInput(self, doc, data, bd, win, msg):
        

        key = msg.GetLong(c4d.BFM_INPUT_CHANNEL)

        #marche pas !!!???
        #print(msg.GetInt32(c4d.BFM_INPUT_QUALIFIER))
        if msg[c4d.BFM_INPUT_QUALIFIER]&c4d.QSHIFT:
            print('shift')
            
        if key==c4d.KEY_ESC:
            self.p1 = None
            self.p2 = None
            self.ps1 = None
            self.ps2 = None
            self.ps3 = None
            return True
        
        return True

    def GetCursorInfo(self, doc, data, bd, x, y, bc):

         #si la touche shift est enfoncée on désactive le mode ortho
        if bc[c4d.BFM_INPUT_QUALIFIER]==c4d.QSHIFT:
            self.mode_ortho = False
        else:
            self.mode_ortho = True

        if self.p1 :
            if self.p2:
                self.ps3 = c4d.Vector(x,y,0)
            else:
                if self.mode_ortho:
                    self.ps2 = pt_ortho(self.ps1,c4d.Vector(x,y,0))
                else:
                    self.ps2 = c4d.Vector(x,y,0)

            c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW|c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION)
        return True


    def MouseInput(self, doc, data, bd, win, msg):

        
        x = msg[c4d.BFM_INPUT_X]
        y = msg[c4d.BFM_INPUT_Y]

        #si la touche shift est enfoncée on désactive le mode ortho
        if msg[c4d.BFM_INPUT_QUALIFIER]&c4d.QSHIFT:
            self.mode_ortho = False
        else:
            self.mode_ortho = True

        device = 0
        if msg[c4d.BFM_INPUT_CHANNEL]==c4d.BFM_INPUT_MOUSELEFT:
            if self.p1:
                if self.p2:
                    #self.ps3 = = c4d.Vector(x,y,0)
                    #self.p3 = bd.SW(self.ps2)
                    doc.StartUndo()
                    p3 = bd.SW(c4d.Vector(x,y,0))
                    rect = rectangle_from_3_points(self.p1,self.p2,p3)
                    doc.InsertObject(rect)
                    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,rect)
                    doc.SetActiveObject(rect)
                    doc.EndUndo()
                    c4d.EventAdd()
                    self.p1 = None
                    self.ps1 = None
                    self.p2 = None
                    self.ps2 = None  
                    self.ps3 = None                  
                else:
                    if self.mode_ortho:
                        self.ps2 = pt_ortho(self.ps1,c4d.Vector(x,y,0))
                    else:
                        self.ps2 = c4d.Vector(x,y,0)
                    self.p2 = bd.SW(self.ps2)
            else:
                self.ps1 = c4d.Vector(x,y,0)
                self.p1 = bd.SW(self.ps1)
            device = c4d.KEY_MLEFT
        
            c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW|c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION)
        return True

    def Draw(self, doc, data, bd, bh, bt, flags):

        bd = doc.GetActiveBaseDraw()
        bd.SetMatrix_Screen()
        bd.SetPen(c4d.Vector(0.956862745098039,0.615686274509804,0.231372549019608))
        if self.ps1:           
            #bd.DrawPoint2D(self.ps1)
            if self.ps2:        
                bd.DrawLine2D(self.ps1, self.ps2)

                if self.ps3:

                    #pour la perpendiculaire on récupère le vecteur par PointLineDistance
                    #qu'on ajoute ensuite aux points de départ et d'arrivée
                    perpendiculaire = c4d.utils.PointLineDistance(self.ps1, (self.ps2-self.ps1), self.ps3)
                    p3 = self.ps2 + perpendiculaire
                    p4 = self.ps1 + perpendiculaire

                    bd.DrawLine2D(self.ps2, p3)
                    bd.DrawLine2D(p3, p4)
                    bd.DrawLine2D(p4, self.ps1)

        else:
            rect = doc.GetActiveObject()
            if rect and rect.CheckType(c4d.Osplinerectangle):
                width = rect[c4d.PRIM_RECTANGLE_WIDTH]
                height = rect[c4d.PRIM_RECTANGLE_HEIGHT]
                cache = rect.GetCache()
                mg = rect.GetMg()
                for p in cache.GetAllPoints():
                    ps = bd.WS(p*mg)
                    bd.DrawHandle2D(ps,type=c4d.DRAWHANDLE_BIG)


        bd.SetMatrix_Matrix(None, c4d.Matrix())


        return c4d.TOOLDRAW_HIGHLIGHTS



if __name__ == "__main__":
     bmp = c4d.bitmaps.BaseBitmap()
     dir, file = os.path.split(__file__)
     fn = os.path.join(dir, "res", "rectangle_tool.png")
     bmp.InitWith(fn)
     c4d.plugins.RegisterToolPlugin(id=PLUGIN_ID,str="Rectangle par 3 points",info=0,
                        icon=bmp,help="Blablabla",dat=Rectangle3Points())