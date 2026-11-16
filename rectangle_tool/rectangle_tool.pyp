# -*- coding: utf8 -*-

import c4d,os
import time
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

CORNERS = ((-1,-1), (1,-1), (1,1), (-1,1))
HIT_RADIUS = 8


def selected_rectangle(doc):
    rect = doc.GetActiveObject()
    if rect and rect.CheckType(c4d.Osplinerectangle) and rect[c4d.PRIM_PLANE] == c4d.PRIM_PLANE_XZ:
        return rect
    return None


def screen_corners(rect, bd):
    w = rect[c4d.PRIM_RECTANGLE_WIDTH] / 2
    h = rect[c4d.PRIM_RECTANGLE_HEIGHT] / 2
    mg = rect.GetMg()
    return [bd.WS(mg * c4d.Vector(x*w, 0, z*h)) for x, z in CORNERS]


def hit_handle(rect, bd, x, y):
    points = screen_corners(rect, bd)
    distances = [(p.x-x)**2 + (p.y-y)**2 for p in points]
    index = distances.index(min(distances))
    if distances[index] <= HIT_RADIUS**2:
        return CORNERS[index]
    best = HIT_RADIUS**2
    handle = None
    for i, a in enumerate(points):
        j = (i+1) % 4
        b = points[j]
        dx, dy = b.x-a.x, b.y-a.y
        length_sq = dx*dx + dy*dy
        if not length_sq:
            continue
        t = max(0, min(1, ((x-a.x)*dx + (y-a.y)*dy) / length_sq))
        distance = (a.x+t*dx-x)**2 + (a.y+t*dy-y)**2
        if distance <= best:
            best = distance
            handle = tuple((u+v)//2 for u,v in zip(CORNERS[i], CORNERS[j]))
    return handle


def local_cursor(bd, inverse, x, y):
    # Intersect the cursor ray with the rectangle's original local XZ plane.
    a = inverse * bd.SW(c4d.Vector(x,y,0))
    b = inverse * bd.SW(c4d.Vector(x,y,1000))
    ray = b-a
    if abs(ray.y) > 1e-10:
        return a - ray * (a.y / ray.y)
    return None


def snap_geometry(doc, exclude):
    stack = list(doc.GetObjects())
    while stack:
        obj = stack.pop()
        if obj == exclude or obj.GetEditorMode() == c4d.MODE_OFF:
            continue
        stack.extend(obj.GetChildren())
        cache = obj.GetDeformCache() or obj.GetCache()
        if cache is not None:
            stack.append(cache)
        elif isinstance(obj, c4d.PointObject):
            yield obj


def snap_cursor(doc, bd, x, y, exclude=None):
    """Return a screen position so the footprint stays on its drawing plane."""
    snap = c4d.modules.snap
    raw = c4d.Vector(x, y, 0)
    if not snap.IsSnapEnabled(doc):
        return raw
    radius = snap.GetSnapSettings(doc)[c4d.SNAP_SETTINGS_RADIUS]
    best = radius ** 2
    result = raw

    def consider(screen):
        nonlocal best, result
        distance = (screen.x-x)**2 + (screen.y-y)**2
        if distance <= best:
            best = distance
            result = c4d.Vector(screen.x, screen.y, 0)

    grid_point = snap.IsSnapEnabled(doc, c4d.SNAPMODE_GRIDPOINT)
    grid_line = snap.IsSnapEnabled(doc, c4d.SNAPMODE_GRIDLINE)
    if grid_point or grid_line:
        plane = snap.GetWorkplaneMatrix(doc, bd)
        local = local_cursor(bd, ~plane, x, y)
        step = bd.GetGridStep()[0]
        if local is not None and step > 0:
            gx = round(local.x / step) * step
            gz = round(local.z / step) * step
            if grid_line:
                consider(bd.WS(plane * c4d.Vector(gx, 0, local.z)))
                consider(bd.WS(plane * c4d.Vector(local.x, 0, gz)))
            if grid_point:
                consider(bd.WS(plane * c4d.Vector(gx, 0, gz)))

    points = snap.IsSnapEnabled(doc, c4d.SNAPMODE_POINT)
    edges = snap.IsSnapEnabled(doc, c4d.SNAPMODE_EDGE)
    if not (points or edges):
        return result
    for obj in snap_geometry(doc, exclude):
        mg = obj.GetMg()
        center, extent = obj.GetMp(), obj.GetRad()
        corners = [bd.WS(mg * (center + c4d.Vector(a*extent.x, b*extent.y, c*extent.z)))
                   for a in (-1,1) for b in (-1,1) for c in (-1,1)]
        if (x < min(p.x for p in corners)-radius or x > max(p.x for p in corners)+radius
                or y < min(p.y for p in corners)-radius or y > max(p.y for p in corners)+radius):
            continue
        projected = [bd.WS(mg * p) for p in obj.GetAllPoints()]
        if points:
            for point in projected:
                consider(point)
        if edges and isinstance(obj, c4d.PolygonObject):
            for poly in obj.GetAllPolygons():
                ids = (poly.a, poly.b, poly.c, poly.d)
                for index, first in enumerate(ids):
                    a, b = projected[first], projected[ids[(index+1)%4]]
                    if (x < min(a.x,b.x)-radius or x > max(a.x,b.x)+radius
                            or y < min(a.y,b.y)-radius or y > max(a.y,b.y)+radius):
                        continue
                    dx, dy = b.x-a.x, b.y-a.y
                    if dx or dy:
                        t = max(0, min(1, ((x-a.x)*dx + (y-a.y)*dy)/(dx*dx+dy*dy)))
                        consider(a + (b-a)*t)
    return result


def resize_rectangle(doc, bd, win, rect, handle, x, y):
    mg = rect.GetMg()
    inverse = ~mg
    start = local_cursor(bd, inverse, x, y)
    if start is None:
        return False
    width = rect[c4d.PRIM_RECTANGLE_WIDTH]
    height = rect[c4d.PRIM_RECTANGLE_HEIGHT]
    sx, sz = handle
    win.MouseDragStart(c4d.KEY_MLEFT, int(x), int(y), c4d.MOUSEDRAGFLAGS_DONTHIDEMOUSE)
    changed = False
    try:
        while True:
            result, dx, dy, _ = win.MouseDrag()
            if result != c4d.MOUSEDRAGRESULT_CONTINUE:
                break
            if not (dx or dy):
                continue
            x += dx
            y += dy
            # Snap the moving boundary, including the initial grab offset.
            grip = c4d.Vector(sx*width/2 if sx else start.x, 0,
                              sz*height/2 if sz else start.z)
            raw = local_cursor(bd, inverse, x, y)
            if raw is None:
                continue
            projected = bd.WS(mg * (grip + raw - start))
            target = snap_cursor(doc, bd, projected.x, projected.y, rect)
            cursor = local_cursor(bd, inverse, target.x, target.y)
            if cursor is None:
                continue
            delta = cursor-grip
            w = max(1e-6, width + sx*delta.x)
            h = max(1e-6, height + sz*delta.z)
            if not changed:
                doc.StartUndo()
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, rect)
                changed = True
            moved = c4d.Matrix(mg)
            moved.off = mg * c4d.Vector(sx*(w-width)/2, 0, sz*(h-height)/2)
            rect[c4d.PRIM_RECTANGLE_WIDTH] = w
            rect[c4d.PRIM_RECTANGLE_HEIGHT] = h
            rect.SetMg(moved)
            rect.Message(c4d.MSG_UPDATE)
            c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_NO_THREAD |
                          c4d.DRAWFLAGS_NO_ANIMATION)
    finally:
        cancelled = win.MouseDragEnd() == c4d.MOUSEDRAGRESULT_ESCAPE
        if changed:
            doc.EndUndo()
            if cancelled:
                doc.DoUndo()
            c4d.EventAdd()
    return True


class Rectangle3Points(c4d.plugins.ToolData):
    """Inherit from ToolData to create your own tool"""

    p1=p2=None
    ps1=ps2=ps3=None
    rect = None

    mode_ortho = True
    

    def KeyboardInput(self, doc, data, bd, win, msg):
        

        if msg.GetInt32(c4d.BFM_INPUT_CHANNEL) == c4d.KEY_ESC and self.p1 is not None:
            self.p1 = self.p2 = self.ps1 = self.ps2 = self.ps3 = None
            c4d.EventAdd()
            return True
        return False

    def GetCursorInfo(self, doc, data, bd, x, y, bc):

         #si la touche shift est enfoncée on désactive le mode ortho
        if bc[c4d.BFM_INPUT_QUALIFIER]==c4d.QSHIFT:
            self.mode_ortho = False
        else:
            self.mode_ortho = True

        if self.p1 is not None:
            screen = snap_cursor(doc, bd, x, y)
            if self.p2 is not None:
                self.ps3 = screen
            else:
                self.ps2 = pt_ortho(self.ps1, screen) if self.mode_ortho else screen

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

        if msg[c4d.BFM_INPUT_CHANNEL] != c4d.BFM_INPUT_MOUSELEFT:
            return False
        if self.p1 is None:
            rect = selected_rectangle(doc)
            if rect is not None:
                handle = hit_handle(rect, bd, x, y)
                if handle is not None:
                    return resize_rectangle(doc, bd, win, rect, handle, x, y)

        if msg[c4d.BFM_INPUT_CHANNEL]==c4d.BFM_INPUT_MOUSELEFT:
            screen = snap_cursor(doc, bd, x, y)
            if self.p1 is not None:
                if self.p2 is not None:
                    #self.ps3 = = screen
                    #self.p3 = bd.SW(self.ps2)
                    doc.StartUndo()
                    try:
                        p3 = bd.SW(screen)
                        rect = rectangle_from_3_points(self.p1,self.p2,p3)
                        doc.InsertObject(rect)
                        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ,rect)
                        doc.SetActiveObject(rect)
                    finally:
                        doc.EndUndo()
                    c4d.EventAdd()
                    self.p1 = None
                    self.ps1 = None
                    self.p2 = None
                    self.ps2 = None  
                    self.ps3 = None                  
                else:
                    if self.mode_ortho:
                        self.ps2 = pt_ortho(self.ps1,screen)
                    else:
                        self.ps2 = screen
                    self.p2 = bd.SW(self.ps2)
            else:
                self.ps1 = screen
                self.p1 = bd.SW(self.ps1)

        
            c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW|c4d.DRAWFLAGS_NO_THREAD|c4d.DRAWFLAGS_NO_ANIMATION)
        return True

    def Draw(self, doc, data, bd, bh, bt, flags):

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
            rect = selected_rectangle(doc)
            if rect is not None:
                points = screen_corners(rect, bd)
                for i, point in enumerate(points):
                    bd.DrawHandle2D(point, type=c4d.DRAWHANDLE_BIG)
                    midpoint = (point + points[(i+1) % 4]) * 0.5
                    bd.DrawHandle2D(midpoint, type=c4d.DRAWHANDLE_BIG)

        bd.SetMatrix_Matrix(None, c4d.Matrix())


        return c4d.TOOLDRAW_HIGHLIGHTS



if __name__ == "__main__":
     bmp = c4d.bitmaps.BaseBitmap()
     dir, file = os.path.split(__file__)
     fn = os.path.join(dir, "res", "rectangle_tool.png")
     bmp.InitWith(fn)
     c4d.plugins.RegisterToolPlugin(id=PLUGIN_ID,str="Rectangle par 3 points",info=0,
                        icon=bmp,help="Blablabla",dat=Rectangle3Points())