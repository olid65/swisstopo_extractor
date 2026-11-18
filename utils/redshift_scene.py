"""Redshift materials and geolocated daylight for a swisstopo model."""
import math
import os
from datetime import datetime

import c4d
import maxon

RENDERER = 1036219
SUN_SKY = 1036754
SPACE = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")
CORE = "com.redshift3d.redshift4c4d.nodes.core."


def material(doc, name, image=None):
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(name)
    graph = mat.GetNodeMaterialReference().CreateEmptyGraph(SPACE)
    with graph.BeginTransaction() as transaction:
        shader = graph.AddChild(maxon.Id(), maxon.Id(CORE + "standardmaterial"))
        output = graph.AddChild(maxon.Id(), maxon.Id("com.redshift3d.redshift4c4d.node.output"))
        shader.GetOutputs().FindChild(CORE + "standardmaterial.outcolor").Connect(
            output.GetInputs().FindChild("com.redshift3d.redshift4c4d.node.output.surface"))
        shader.GetInputs().FindChild(CORE + "standardmaterial.refl_weight").SetPortValue(0.0)
        color = shader.GetInputs().FindChild(CORE + "standardmaterial.base_color")
        if image:
            texture = graph.AddChild(maxon.Id(), maxon.Id(CORE + "texturesampler"))
            file_port = texture.GetInputs().FindChild(CORE + "texturesampler.tex0")
            relative = os.path.relpath(image, doc.GetDocumentPath()).replace(os.sep, "/")
            file_port.FindChild("path").SetPortValue(maxon.Url(relative))
            texture.GetOutputs().FindChild(CORE + "texturesampler.outcolor").Connect(color)
        else:
            color.SetPortValue(maxon.Color(1, 1, 1))
        transaction.Commit()
    doc.InsertMaterial(mat)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)
    return mat


def environment(doc, origin, bounds, altitude, to_wgs84):
    west, south, east, north = bounds
    x, z = (west+east)/2, (south+north)/2
    lon, lat = to_wgs84(x, z)
    sky = c4d.BaseObject(SUN_SKY)
    sky.SetName("Ciel physique Redshift")
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_SUN_DISK_INTENSITY] = 0.3
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_MULTIPLIER] = 0.5
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_SUN_POSITION_MODE] = (
        c4d.REDSHIFT_SKY_PHYSICALSKY_SUN_POSITION_MODE_TIME_AND_DATE)
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_GEOLOCATION_LATITUDE] = math.radians(lat)
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_GEOLOCATION_LONGITUDE] = math.radians(lon)
    clock = sky[c4d.REDSHIFT_SKY_PHYSICALSKY_DATETIME]
    clock.SetDateTime(datetime(2022, 6, 21, 17))
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_DATETIME] = clock
    sky[c4d.REDSHIFT_SKY_PHYSICALSKY_DATETIME_TIMEZONE] = 2

    plane = c4d.BaseObject(c4d.Oplane)
    plane.SetName("Sol Redshift")
    side = max(100000, 20 * max(east-west, north-south))
    plane[c4d.PRIM_AXIS] = c4d.PRIM_AXIS_YP
    plane[c4d.PRIM_PLANE_WIDTH] = plane[c4d.PRIM_PLANE_HEIGHT] = side
    plane[c4d.PRIM_PLANE_SUBW] = plane[c4d.PRIM_PLANE_SUBH] = 1
    plane.SetAbsPos(c4d.Vector(x-origin.x, altitude, z-origin.z))
    plane.MakeTag(c4d.Ttexture).SetMaterial(material(doc, "Sol RS"))
    group = c4d.BaseObject(c4d.Onull)
    group.SetName("environnement Redshift")
    plane.InsertUnder(group)
    sky.InsertUnder(group)
    doc.InsertObject(group)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, group)
