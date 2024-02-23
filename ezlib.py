import ezdxf
from ezdxf import math
import FreeCAD
import Draft
import Part
import importDXF
import DraftVecUtils
import DraftGeomUtils
from FreeCAD import Console as FCC
from time import time

def ezprocessdxf(dxfdoc, sel_layer, mydoc=None):
    FCC.PrintMessage("mydoc : " + mydoc.Name + "\n")
    ezreadPreferences()
    dxfmsp = dxfdoc.modelspace()

    tmpdoc = ezdxf.new()
    tmpmsp = tmpdoc.modelspace()
    
    # FreeCAD layers
    global layers
    layers = []

    ezlayers = []
    for lay_name in sel_layer:
        ezlayers.append(dxfdoc.layers.get(lay_name))

    # Traverse through each layer in dxfdoc
    for ezlay in ezlayers: 
        shapes = []

        # Query for LWPOLYLINE
        polylines = dxfmsp.query('LWPOLYLINE[layer=="' + ezlay.dxf.name + '"]')
        if polylines:
            FCC.PrintMessage("Drawing " + str(len(polylines)) + " polylines...\n")

        num = 0
        
        for polyline in polylines:
            shape = ezdrawPolyline(polyline, num)
            newob = ezaddObject(shape, mydoc, "Polyline", ezlay)

            #if polyline.is_closed:
                #shape = ezdrawPolyline(polyline, num)
                #newob = ezaddObject(shape, mydoc, "Polyline", ezlay)
            #else:
                #shape = ezdrawPolyline(polyline, num)
                #shapes.append(shape)


        #if shapes:
            #shapes = ezjoin(shapes)
            #if (mydoc):
                #for shape in shapes:
                    #newob = ezaddObject(shape, mydoc, "Polyline", ezlay)

def ezjoin(shapes): 
    # Join lines, polylines and arcs if needed, where shapes is a list of shape
    if dxfJoin and shapes:

        FCC.PrintMessage("Joining geometry...\n")
        start = time()
        edges = []
        for s in shapes:
            edges.extend(s.Edges)
        shapes = DraftGeomUtils.findWires(edges)
        end = time()
        FCC.PrintMessage("t = {}s\n".format(end- start))
    return shapes

def ezvec(pt, z0):
    v = FreeCAD.Vector(round(pt[0], importDXF.prec()),
                   round(pt[1], importDXF.prec()),
                   round(z0, importDXF.prec()))
    if dxfScaling != 1:
        v.multiply(dxfScaling)
    return v

def ezdrawPolyline(polyline, forceShape=False, num=None):
    if len(polyline) > 1: # not a "point"
        edges = []
        curves = False
        verts = []
        for p in range(len(polyline)-1):
            # p1, p2 for each polyline's (line) segment point
            p1 = polyline[p]
            p2 = polyline[p+1]
            z0 = polyline.dxf.elevation
            # point : (x, y, start_width, end_width, bulge)
            v1 = ezvec(p1, z0)
            v2 = ezvec(p2, z0)
            verts.append(v1)
            if polyline[p][-1]: # has bulge
                curves = True
                cv = importDXF.calcBulge(v1, polyline[p][-1], v2)
                if DraftVecUtils.isColinear([v1, cv, v2]):
                    try:
                        edges.append(Part.LineSegment(v1, v2).toShape())
                    except Part.OCCError:
                        importDXF.warn(polyline, num)
                else:
                    try:
                        edges.append(Part.Arc(v1, cv, v2).toShape())
                    except Part.OCCError:
                        importDXF.warn(polyline, num)
            else:
                try:
                    edges.append(Part.LineSegment(v1, v2).toShape())
                except Part.OCCError:
                    importDXF.warn(polyline, num)

        verts.append(v2)
        if polyline.is_closed:
            p1 = polyline[-1]
            p2 = polyline[0]
            z0 = polyline.dxf.elevation
            v1 = ezvec(p1, z0)
            v2 = ezvec(p2, z0)
            cv = importDXF.calcBulge(v1, polyline[-1][-1], v2)
            if not DraftVecUtils.equals(v1, v2):
                if DraftVecUtils.isColinear([v1, cv, v2]):
                    try:
                        edges.append(Part.LineSegment(v1, v2).toShape())
                    except Part.OCCError:
                        importDXF.warn(polyline, num)
                else:
                    try:
                        edges.append(Part.Arc(v1, cv, v2).toShape())
                    except Part.OCCError:
                        importDXF.warn(polyline, num)
        if edges:
            try:
                width = polyline[0][2]
                if width and dxfRenderPolylineWidth:
                    w = Part.Wire(edges)
                    w1 = w.makeOffset(width/2)
                    if polyline.is_closed:
                        w2 = w.makeOffset(-width/2)
                        w1 = Part.Face(w1)
                        w2 = Part.Face(w2)
                        if w1.BoundBox.DiagonalLength > w2.BoundBox.DiagonalLength:
                            return w1.cut(w2)
                        else:
                            return w2.cut(w1)
                    else:
                        return Part.Face(w1)
                elif (dxfCreateDraft or dxfCreateSketch) and (not curves) and (not forceShape):
                    ob = Draft.makeWire(verts)
                    ob.Closed = polyline.is_closed
                    #ob.Placement = placementFromDXFOCS(polyline)
                    return ob
                else:
                    if polyline.is_closed and dxfFillMode:
                        w = Part.Wire(edges)
                        #w.Placement = placementFromDXFOCS(polyline)
                        return Part.Face(w)
                    else:
                        w = Part.Wire(edges)
                        #w.Placement = placementFromDXFOCS(polyline)
                        return w
            except Part.OCCError:
                importDXF.warn(polyline, num)
    return None
    

def ezlocateLayer(wantedLayer, mydoc, color=None, drawstyle=None):
    # layers is a global variable.
    # It should probably be passed as an argument.
    wantedLayerName = importDXF.decodeName(wantedLayer)
    for l in layers:
        if wantedLayerName == l.Label:
            return l
    if dxfUseDraftVisGroups:
        newLayer = Draft.make_layer(name=wantedLayer,
                                   line_color=color,
                                   draw_style=drawstyle)
    else:
        newLayer = mydoc.addObject("App::DocumentObjectGroup", wantedLayer)
    newLayer.Label = wantedLayerName
    layers.append(newLayer)
    return newLayer

def ezaddObject(shape, mydoc, name="Shape", layer=None):
    if isinstance(shape, Part.Shape):
        newob = mydoc.addObject("Part::Feature", name)
        newob.Shape = shape
    else:
        newob = shape
    if layer:
        lay_color = tuple( i/255 for i in ezdxf.colors.aci2rgb(layer.color))
        lay = ezlocateLayer(layer.dxf.name, mydoc, lay_color, "Solid")
        # For old style layers, which are just groups
        if hasattr(lay, "addObject"):
            lay.addObject(newob)
        # For new Draft Layers
        elif hasattr(lay, "Proxy") and hasattr(lay.Proxy, "addObject"):
            lay.Proxy.addObject(lay, newob)

        if not dxfUseDraftVisGroups:
            newob.ViewObject.LineColor = lay_color
            newob.ViewObject.PointColor = lay_color
    return newob

def ezreadPreferences():
    # reading parameters
    p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft")
    global dxfCreatePart, dxfCreateDraft, dxfCreateSketch
    global dxfDiscretizeCurves, dxfStarBlocks
    global dxfMakeBlocks, dxfJoin, dxfRenderPolylineWidth
    global dxfImportTexts, dxfImportLayouts
    global dxfImportPoints, dxfImportHatches, dxfUseStandardSize
    global dxfGetColors, dxfUseDraftVisGroups
    global dxfFillMode#, dxfBrightBackground, dxfDefaultColor
    global dxfUseLegacyImporter, dxfExportBlocks, dxfScaling
    global dxfUseLegacyExporter
    dxfCreatePart = p.GetBool("dxfCreatePart", True)
    dxfCreateDraft = p.GetBool("dxfCreateDraft", False)
    dxfCreateSketch = p.GetBool("dxfCreateSketch", False)
    dxfDiscretizeCurves = p.GetBool("DiscretizeEllipses", True)
    dxfStarBlocks = p.GetBool("dxfstarblocks", False)
    dxfMakeBlocks = p.GetBool("groupLayers", False)
    dxfJoin = p.GetBool("joingeometry", False)
    dxfRenderPolylineWidth = p.GetBool("renderPolylineWidth", False)
    dxfImportTexts = p.GetBool("dxftext", False)
    dxfImportLayouts = p.GetBool("dxflayouts", False)
    dxfImportPoints = p.GetBool("dxfImportPoints", False)
    dxfImportHatches = p.GetBool("importDxfHatches", False)
    dxfUseStandardSize = p.GetBool("dxfStdSize", False)
    dxfGetColors = p.GetBool("dxfGetOriginalColors", False)
    dxfUseDraftVisGroups = p.GetBool("dxfUseDraftVisGroups", True)
    dxfFillMode = p.GetBool("fillmode", True)
    dxfUseLegacyImporter = p.GetBool("dxfUseLegacyImporter", False)
    dxfUseLegacyExporter = p.GetBool("dxfUseLegacyExporter", False)
    #dxfBrightBackground = isBrightBackground()
    #dxfDefaultColor = getColor()
    dxfExportBlocks = p.GetBool("dxfExportBlocks", True)
    dxfScaling = p.GetFloat("dxfScaling", 1.0)
