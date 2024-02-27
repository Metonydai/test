import math
import ezdxf
from ezdxf.math import Vec2
from ezdxf.math import BoundingBox2d
import FreeCAD
import Draft
import Part
import importDXF
import DraftVecUtils
import DraftGeomUtils
from FreeCAD import Console as FCC
from time import time
from enum import Enum

class BVHBuildNode:
    def __init__(self):
        self.left = None
        self.right = None
        self.object = None
        self.bounds = BoundingBox2d()

class BVHAccel:
    class splitMethod(Enum):
        NAIVE = 0
        SAH = 1

    def __init__(self, ents, splitMethod = splitMethod.NAIVE):
        self.m_ents = ents
        #self.m_maxPrimsInNode = maxPrimsInNode
        self.m_splitMethod = splitMethod.NAIVE
        start = time()
        if len(self.m_ents) == 0:
            return BVHBuildNode()

        self.root = self._recursiveBuild(self.m_ents)
        stop = time()
        print("BVH Generation complete: \nTime Taken: {} secs\n".format(stop-start))

    def findNextEntity(self, entity_list):
        # For Next Entity, consider entity_list[-1]
        myEnt = entity_list[-1]
        node = self.root
        return self.getNextEntity(node, myEnt)
    
    def getNextEntity(self, node, myEnt):
        # check myEnt reverse: st, end
        if myEnt.reverse == False:
            st,end = 0,-1
        else:
            st,end = -1,0

        # Leaf node
        if node.object != None:
            # end connect start
            if node.object.Vertexes[0].isclose(myEnt.Vertexes[end]):
                return node.object
            
            # end connect end
            elif node.object.Vetexes[-1].isclose(myEnt.Vertexes[end]):
                node.object.reverse = True
                return node.object

            else:
                return None

        # Try myEnt end_point
        point_in_left = node.left.bounds.inside(myEnt.Vertexes[end])
        point_in_right = node.right.bounds.inside(myEnt.Vertexes[end])
        if point_in_left and !point_in_right:
            getNextEntity(node.left, myEnt)
        elif point_in_right and !point_in_left:
            getNextEntity(node.right, myEnt)
        elif point_in_left and point_in_right:
            if node.left.bounds.inside(myEnt.Vertexes[st]): # myEnt start_point in node.left
                getNextEntity(node.right, myEnt)
            else:
                getNextEntity(node.left, myEnt)

        return None

    def findPreviousEntity(self, reversed_polys):
        # For Previous Entity
        myEnt = reversed_polys[-1]
        node = self.root
        return self.getPreviousEntity(node, myEnt)
    
    def getPreviosEntity(self, node, myEnt):
        # check myEnt reverse: st, end 
        if myEnt.reverse == False:
            st,end = 0,-1
        else:
            st,end = -1,0

        # Leaf node
        if node.object != None:
            # end connect start
            if node.object.Vertexes[-1].isclose(myEnt.Vertexes[st]):
                return node.object
            
            # start connect start
            elif node.object.Vetexes[0].isclose(myEnt.Vertexes[st]):
                node.object.reverse = True
                return node.object

            else:
                return None

        # Try myEnt end_point
        point_in_left = node.left.bounds.inside(myEnt.Vertexes[st])
        point_in_right = node.right.bounds.inside(myEnt.Vertexes[st])
        if point_in_left and !point_in_right:
            getNextEntity(node.left, myEnt)
        elif point_in_right and !point_in_left:
            getNextEntity(node.right, myEnt)
        elif point_in_left and point_in_right:
            if node.left.bounds.inside(myEnt.Vertexes[end]): # myEnt end_point in node.left
                getCoincidentEntity(node.right, myEnt)
            else:
                getCoincidentEntity(node.left, myEnt)

        return None
    
    def _recursiveBuild(self, ents):
        node = BVHBuildNode()
        #bounds = BoundingBox2d()
        if (len(ents) == 1):
            node.bounds = ents[0].get_bounds()
            #node.object = ents[0].m_entity
            node.object = ents[0]
            node.left = None
            node.right = None
            return node

        elif (len(ents) == 2):
            node.left = self._recursiveBuild([ents[0]])
            node.right = self._recursiveBuild([ents[1]])
            node.bounds = node.left.bounds.union(node.right.bounds)
            return node
        
        else:
            centroidBounds = BoundingBox2d()
            for i in range(len(ents)):
                centroidBounds.extend([Centroid(ents[i].get_bounds())])
            dim = maxExtent(centroidBounds)
            if dim == 0:
                sorted(ents, key=lambda ent: Centroid(ent.get_bounds()).x)
            elif dim == 1:
                sorted(ents, key=lambda ent: Centroid(ent.get_bounds()).y)
            
            median = int((len(ents)+1)/2)

            leftentities = ents[0:median]
            rightentities = ents[median:]
            node.left = self._recursiveBuild(leftentities)
            node.right = self._recursiveBuild(rightentities)

            node.bounds = node.left.bounds.union(node.right.bounds)

        return node

def ezJoinPolys(entities): 
    bvh = BVHAccel(entities)
    sorted_polys = []
    for i range(len(entities)):
        if entities[i].joined:
            continue

        poly_is_closed = False
        polys = []
        polys.append(entities[i])
        nextEntity = bvh.findNextEntity(polys)
        while nextEntity != None:
            # Check if nextEntity and polys[0] form closed polyline
            if nextEntity.reverse == False:
                end = -1
            else:
                end = 0

            if nextEntity.Vertexes[end].isclose(polys[0].Vertexes[0]):
                polys.append(nextEntity)
                nextEntity.joined = True
                poly_is_close = True
                break

            # Join nextEntity
            polys.append(nextEntity)
            nextEntity.joined = True

            # find nextEntity
            nextEntity = bvh.findNextEntity(polys)
        
        if (not poly_is_closed):
            reverse_polys = []
            # Use polys[0] to find previousEntity
            previousEntity = bvh.findPreviousEntity([polys[0]])

            while previousEntity != None:
                # Join previousEntity
                reverse_polys.append(previousEntity)
                previousEntity.joined = True

                # find previousEntity
                previousEntity = bvh.findPreviousEntity(reverse_polys)

            polys = reverse_polys[::-1] + polys

        sorted_polys.append(polys)

    return sorted_polys


def Centroid(bbox):
    # UVec
    return 0.5*(bbox.extmin + bbox.extmax)

def maxExtent(bbox):
    d = bbox.extmax- bbox.extmin
    if (d.x > d.y):
        return 0
    else:
        return 1

class myEntity:
    def __init__(self, entity, dxftype):
        self.m_entity = entity
        self.reverse = False
        self.joined = False
        self.Vertexes = self.getVertexes(dxftype)
    
    def get_bounds(self):
        #if self.m_entity.dxftype() == 'CIRCLE':
            #c = self.m_entity.dxf.center
            #r = self.m_enitty.dxf.radius
            #return BoundingBox2d([c - Vec2(-r, -r), c + Vec2(r,r)])
        if self.m_entity.dxftype() == 'LINE':
            l = self.m_entity
            return BoundingBox2d([l.dxf.start, l.dxf.end])
        elif self.m_entity.dxftype() == 'ARC':
            arc = self.m_entity
            return BoundingBox2d([arc.start_point, arc.end_point])
        elif self.m_entity.dxftype() == 'LWPOLYLINE':
            pl = self.m_entity
            bbox = BoundingBox2d()
            return bbox.extend(pl.vertice())

    def getVertexes(self, dxftype):
        if dxftype == 'LINE':
            l = self.m_entity
            return [l.dxf.start, l.dxf.end]
        elif dxftype == 'ARC':
            arc = self.m_entity
            return [arc.start_point, arc.end_point]
        elif dxftype == 'LWPOLYLINE':
            pl = self.m_entity
            return [Vec2(pl.get_points['xy'][0]), Vec2(pl.get_points['xy'][-1])]

def ezprocessdxf(dxfdoc, sel_layer, mydoc=None):
    FCC.PrintMessage("mydoc : " + mydoc.Name + "\n")
    ezreadPreferences()
    dxfmsp = dxfdoc.modelspace()

    tmpdoc = ezdxf.new()
    tmpmsp = tmpdoc.modelspace()
    
    # FreeCAD layers
    global layers
    layers = []

    # copy sel_layer to tmpdoc and deal with entities
    for l in sel_layer:
        tmpdoc.layers.add(name=l, color=dxfdoc.layers.get(l).dxf.color)

        # deal with entities
        entities = []
        for e in msp.query('*[layer=="' + l + '"]'):
            if e.dxftype() == 'CIRCLE':
                tmpmsp.add_foreign_entity(e)
            
            elif e.dxftype() == 'LINE':
                entity = myEntity(e, 'LINE')
                entities.append(entity)

            elif e.dxftype() == 'ARC':
                entity = myEntity(e, 'ARC')
                entities.append(entity)

            elif e.dxftype() == 'LWPOLYLINE':
                if e.is_closed or Vec2(e.get_points('xy')[0]).isclose(Vec2(e.get_points('xy')[-1])):
                    e.close(True)
                    tmpmsp.add_foreign_entity(e)
                else:
                    entity = myEntity(e, 'LWPOLYLINE')
                    entities.append(entity)
            
            else:
                pass

        sorted_entities = ezJoinPolys(entities)

        # Draw sorted_entities to tmpmsp on layer l
        for poly in sorted_entites:
            ezaddEntity(poly, tmpmsp, l)

    # ======= Draw tmpdoc in FreeCAD =======
    # Obtain the layers in tmpdoc
    ezlayers = []
    for lay_name in sel_layer:
        ezlayers.append(tmpdoc.layers.get(lay_name))

    # Traverse through each layer in tmpdoc
    for ezlay in ezlayers: 
        # Query for LWPOLYLINE
        polylines = dxfmsp.query('LWPOLYLINE[layer=="' + ezlay.dxf.name + '"]')
        if polylines:
            FCC.PrintMessage("Drawing " + str(len(polylines)) + " polylines...\n")

        num = 0
        for polyline in polylines:
            shape = ezdrawPolyline(polyline, num)
            newob = ezaddObject(shape, mydoc, "Polyline", ezlay)

        # Query for LINE
        lines = dxfmsp.query('LINE[layer=="' + ezlay.dxf.name + '"]')
        if polylines:
            FCC.PrintMessage("Drawing " + str(len(lines)) + " lines...\n")

        num = 0
        for line in lines:
            shape = ezdrawLine(line)
            newob = ezaddObject(shape, mydoc, "Line", ezlay)

        # Query for ARC
        arcs = dxfmsp.query('ARC[layer=="' + ezlay.dxf.name + '"]')
        if arcs:
            FCC.PrintMessage("Drawing " + str(len(arcs)) + " arcs...\n")

        num = 0
        for arc in arcs:
            shape = ezdrawArc(arc)
            newob = ezaddObject(shape, mydoc, "Arc", ezlay)

        # Query for CIRCLE
        circles = dxfmsp.query('CIRCLE[layer=="' + ezlay.dxf.name + '"]')
        if circles:
            FCC.PrintMessage("Drawing " + str(len(arcs)) + " circles...\n")

        num = 0
        for circle in circles:
            shape = ezdrawCircle(circle)
            newob = ezaddObject(shape, mydoc, "Circle", ezlay)

    # Finishing
    print("done processing")

    mydoc.recompute()
    print("recompute done")

    FCC.PrintMessage("successfully imported.\n")

def ezaddEntity(ent_list, tmpmsp, l):
    if len(ent_list) == 1:
        e = ent_list[0].m_entity
        tmpmsp.add_foreign_entity(e)
    else:
        vertexes = []

        # Obtain is_poly_closed
        is_poly_closed = False
        first_ent = ent_list[0]
        last_ent = ent_list[-1]
        if first_ent.reverse == False:
            start = 0
        else:
            start = -1

        if last_ent.reverse == False:
            end = -1
        else:
            end = 0
        
        if first_ent.Vertexes[start].isclose(last_ent.Vertexes[end]):
            is_poly_closed = True
        else:
            e = first_ent.m_entity
            if e.dxftype() == 'LINE':
                vertexes.append((e.Vertexes[start].x, e.Vertexes[start.y]))

            elif e.dxftype() == 'ARC':
                if first_ent.reverse == False:
                    vertexes.append((e.Vertexes[start].x, e.Vertexes[start.y],0,0,ezgetBulge(e))
                else:
                    vertexes.append((e.Vertexes[start].x, e.Vertexes[start.y],0,0,-ezgetBulge(e))

            elif e.dxftype() == 'LWPOLYLINE':
                if first_ent.reverse == False:
                    vertexes = e.get_point()[:-1:]
                else:
                    vertexes = e.get_point()[::-1][:-1:]

        # Do not add start vertex to vertexes!
        for myEnt in ent_list[1::]:
            e = myEnt.m_entity

            if e.dxftype() == 'LINE':
                pass

            elif e.dxftype() == 'ARC':
                pass

            elif e.dxftype() == 'LWPOLYLINE':
                if e.is_closed or Vec2(e.get_points('xy')[0]).isclose(Vec2(e.get_points('xy')[-1])):
                    e.close(True)
                    tmpmsp.add_foreign_entity(e)
                else:
                    entity = myEntity(e, 'LWPOLYLINE')
                    entities.append(entity)

        tmpmsp.add_lwpolyline(vertexes, close=is_poly_closed, dxfattribs={"layer": l})

from ezdxf.math import arc_angle_span_deg
def ezgetBulge(arc):
    span_angle = arc_angle_span_deg(arc.dxf.start_angle, arc.dxf.end_angle)
    V1 = arc.start_point
    V2 = arc.end_point




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

def ezvec(pt, z0=None):
    if isinstance(pt, (int, float)):
        v = round(pt, importDXF.prec())
        if dxfScaling != 1:
            v = v * dxfScaling
    else:
        if z0 == None:
            z0 = pt[2]

        v = FreeCAD.Vector(round(pt[0], importDXF.prec()),
                    round(pt[1], importDXF.prec()),
                    round(z0, importDXF.prec()))
        if dxfScaling != 1:
            v.multiply(dxfScaling)
    return v

def ezdrawPolyline(polyline, num=None):
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
                elif (dxfCreateDraft or dxfCreateSketch) and (not curves):
                    ob = Draft.makeWire(verts)
                    ob.Closed = polyline.is_closed
                    #ob.Placement = placementFromDXFOCS(polyline)
                    ob.Placement = FreeCAD.Placement()
                    return ob
                else:
                    if polyline.is_closed and dxfFillMode:
                        w = Part.Wire(edges)
                        #w.Placement = placementFromDXFOCS(polyline)
                        w.Placement = FreeCAD.Placement()
                        return Part.Face(w)
                    else:
                        w = Part.Wire(edges)
                        #w.Placement = placementFromDXFOCS(polyline)
                        w.Placement = FreeCAD.Placement()
                        return w
            except Part.OCCError:
                importDXF.warn(polyline, num)
    return None

def ezdrawLine(line):
    if len(line.points) > 1:
        v1 = ezvec(line.dxf.start)
        v2 = ezvec(line.dxf.end)
        if not DraftVecUtils.equals(v1, v2):
            try:
                if (dxfCreateDraft or dxfCreateSketch):
                    return Draft.makeWire([v1, v2])
                else:
                    return Part.LineSegment(v1, v2).toShape()
            except Part.OCCError:
                importDXF.warn(line)
    return None   

def ezdrawArc(arc):
    v = ezvec(arc.dxf.center)
    firstangle = round(arc.dxf.start_angle, importDXF.prec())
    lastangle = round(arc.dxf.end_angle, importDXF.prec())
    circle = Part.Circle()
    circle.Center = v
    circle.Radius = ezvec(arc.dxf.radius)
    try:
        if (dxfCreateDraft or dxfCreateSketch):
            #pl = placementFromDXFOCS(arc)
            pl = FreeCAD.Placement()
            return Draft.makeCircle(circle.Radius, pl, face=False,
                                    startangle=firstangle,
                                    endangle=lastangle)
        else:
            return circle.toShape(math.radians(firstangle),
                                  math.radians(lastangle))
    except Part.OCCError:
        importDXF.warn(arc)
    return None

def ezdrawCircle(circle):
    v = ezvec(circle.dxf.center)
    curve = Part.Circle()
    curve.Radius = ezvec(circle.radius)
    curve.Center = v
    try:
        if (dxfCreateDraft or dxfCreateSketch):
            #pl = placementFromDXFOCS(circle)
            pl = FreeCAD.Placement()
            return Draft.makeCircle(circle.radius, pl)
        else:
            return curve.toShape()
    except Part.OCCError:
        importDXF.warn(circle)
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
