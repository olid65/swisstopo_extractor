"""Cadrer les faces du terrain actif dans une vue en perspective."""
import c4d


def terrain_vertices(terrain, matrix):
    points = terrain.GetAllPoints()
    used = bytearray(len(points))
    for face in terrain.GetAllPolygons():
        for index in (face.a, face.b, face.c, face.d):
            if not used[index]:
                used[index] = 1
                yield matrix * points[index]


def fitted_camera(terrain, view, camera):
    frame = view.GetFrame()
    w, h = frame["cr"] - frame["cl"], frame["cb"] - frame["ct"]
    if min(w, h) < 2:
        return None
    matrix = camera.GetMg()
    inverse = ~matrix
    # Sample the inset frame at unit camera depth to include lens shift and aspect.
    tl = inverse * view.SW(c4d.Vector(w*.05, h*.05, 1))
    br = inverse * view.SW(c4d.Vector(w*.95, h*.95, 1))
    left, right = tl.x/tl.z, br.x/br.z
    bottom, top = br.y/br.z, tl.y/tl.z
    if right <= left or top <= bottom:
        return None
    upper_x = upper_y = near = float("inf")
    lower_x = lower_y = -float("inf")
    # Each vertex constrains the camera translation against four frustum planes.
    for p in terrain_vertices(terrain, inverse * terrain.GetMg()):
        upper_x = min(upper_x, p.x-left*p.z)
        lower_x = max(lower_x, p.x-right*p.z)
        upper_y = min(upper_y, p.y-bottom*p.z)
        lower_y = max(lower_y, p.y-top*p.z)
        near = min(near, p.z)
    if near == float("inf"):
        return None
    z = min((upper_x-lower_x)/(right-left), (upper_y-lower_y)/(top-bottom), near-.01)
    x = (upper_x + left*z + lower_x + right*z)/2
    y = (upper_y + bottom*z + lower_y + top*z)/2
    result = c4d.Matrix(matrix)
    result.off = matrix * c4d.Vector(x,y,z)
    return result


def frame_terrain(doc, terrain):
    if c4d.documents.GetActiveDocument() != doc:
        c4d.documents.SetActiveDocument(doc)
    view = doc.GetActiveBaseDraw()
    if view.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] != c4d.Pperspective:
        for index in range(min(4, doc.GetBaseDrawCount())):
            view = doc.GetBaseDraw(index)
            if view.GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] == c4d.Pperspective:
                c4d.CallCommand(13635 + index)
                break
        if doc.GetActiveBaseDraw().GetSceneCamera(doc)[c4d.CAMERA_PROJECTION] != c4d.Pperspective:
            c4d.gui.MessageDialog("Aucune vue en perspective active pour cadrer le terrain.")
            return

    view = doc.GetActiveBaseDraw()
    camera = view.GetSceneCamera(doc)
    framed = fitted_camera(terrain, view, camera)
    if framed is None:
        return
    if camera == view.GetEditorCamera():
        camera.SetMg(framed)
    else:
        doc.StartUndo()
        try:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, camera)
            camera.SetMg(framed)
        finally:
            doc.EndUndo()
    c4d.DrawViews(c4d.DRAWFLAGS_ONLY_ACTIVE_VIEW | c4d.DRAWFLAGS_FORCEFULLREDRAW |
                  c4d.DRAWFLAGS_NO_THREAD)
    c4d.EventAdd()
