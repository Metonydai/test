import math
import ezdxf
from ezdxf.math import Vec2
from ezdxf.math import BoundingBox2d
from ezdxf.math import arc_angle_span_deg
import FreeCAD
import FreeCADGui
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
            return None

        self.root = self._recursiveBuild(self.m_ents)
        stop = time()
        print("BVH Generation complete: \nTime Taken: {} secs".format(stop-start))

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
            # Find itself
            if node.object == myEnt:
                return None

            # end connect start
            if node.object.Vertexes[0].isclose(myEnt.Vertexes[end]) and not node.object.joined:
                if node.object.Vertexes[-1].isclose(myEnt.Vertexes[st]): #if myEnt start connect find_ent end
                    # To exclude the conditon that e1 and e2 are essentially lines
                    e1 = node.object.m_entity
                    e2 = myEnt.m_entity
                    if e1.dxftype() == "LINE" and e2.dxftype() == "LINE":
                        return None
                    if e1.dxftype() == "LWPOLYLINE" and e2.dxftype() == "LWPOLYLINE": 
                        if all([v[4]==0.0 for v in e1.get_points()]) and all([v[4]==0.0 for v in e2.get_points()]): #e1 and e2 all vertexes value equal 0.0 -> line
                            return None
                return node.object
            
            # end connect end
            elif node.object.Vertexes[-1].isclose(myEnt.Vertexes[end]) and not node.object.joined:
                if node.object.Vertexes[0].isclose(myEnt.Vertexes[st]): #if myEnt start connect find_ent start
                    # To exclude the conditon that e1 and e2 are essentially lines
                    e1 = node.object.m_entity
                    e2 = myEnt.m_entity
                    if e1.dxftype() == "LINE" and e2.dxftype() == "LINE":
                        return None
                    if e1.dxftype() == "LWPOLYLINE" and e2.dxftype() == "LWPOLYLINE": 
                        if all([v[4]==0.0 for v in e1.get_points()]) and all([v[4]==0.0 for v in e2.get_points()]): #e1 and e2 all vertexes value equal 0.0 -> line
                            return None
                node.object.reverse = True
                return node.object

            else:
                return None

        # Try myEnt end_point
        point_in_left = node.left.bounds.inside(myEnt.Vertexes[end])
        point_in_right = node.right.bounds.inside(myEnt.Vertexes[end])
        if point_in_left and not point_in_right:
            return self.getNextEntity(node.left, myEnt)
        elif point_in_right and not point_in_left:
            return self.getNextEntity(node.right, myEnt)
        elif point_in_left and point_in_right:
            if node.left.bounds.inside(myEnt.Vertexes[st]): # myEnt start_point in node.left
                return self.getNextEntity(node.left, myEnt) or self.getNextEntity(node.right, myEnt)
            else:
                return self.getNextEntity(node.right, myEnt) or self.getNextEntity(node.left, myEnt)

        return None

    def findPreviousEntity(self, reversed_polys):
        # For Previous Entity
        myEnt = reversed_polys[-1]
        node = self.root
        return self.getPreviousEntity(node, myEnt)
    
    def getPreviousEntity(self, node, myEnt):
        # check myEnt reverse: st, end 
        if myEnt.reverse == False:
            st,end = 0,-1
        else:
            st,end = -1,0

        # Leaf node
        if node.object != None:
            # Find itself
            if node.object == myEnt:
                return None

            # end connect start
            if node.object.Vertexes[-1].isclose(myEnt.Vertexes[st]) and not node.object.joined:
                if node.object.Vertexes[0].isclose(myEnt.Vertexes[end]): #if myEnt end connect find_ent start
                    # To exclude the conditon that e1 and e2 are essentially lines
                    e1 = node.object.m_entity
                    e2 = myEnt.m_entity
                    if e1.dxftype() == "LINE" and e2.dxftype() == "LINE":
                        return None
                    if e1.dxftype() == "LWPOLYLINE" and e2.dxftype() == "LWPOLYLINE": 
                        if all([v[4]==0.0 for v in e1.get_points()]) and all([v[4]==0.0 for v in e2.get_points()]): #e1 and e2 all vertexes value equal 0.0 -> line
                            return None
                return node.object
            
            # start connect start
            elif node.object.Vertexes[0].isclose(myEnt.Vertexes[st]) and not node.object.joined:
                if node.object.Vertexes[-1].isclose(myEnt.Vertexes[end]): #if myEnt end connect find_ent end
                    # To exclude the conditon that e1 and e2 are essentially lines
                    e1 = node.object.m_entity
                    e2 = myEnt.m_entity
                    if e1.dxftype() == "LINE" and e2.dxftype() == "LINE":
                        return None
                    if e1.dxftype() == "LWPOLYLINE" and e2.dxftype() == "LWPOLYLINE": 
                        if all([v[4]==0.0 for v in e1.get_points()]) and all([v[4]==0.0 for v in e2.get_points()]): #e1 and e2 all vertexes value equal 0.0 -> line
                            return None
                node.object.reverse = True
                return node.object

            else:
                return None

        # Try myEnt start_point
        point_in_left = node.left.bounds.inside(myEnt.Vertexes[st])
        point_in_right = node.right.bounds.inside(myEnt.Vertexes[st])
        if point_in_left and not point_in_right:
            return self.getPreviousEntity(node.left, myEnt)
        elif point_in_right and not point_in_left:
            return self.getPreviousEntity(node.right, myEnt)
        elif point_in_left and point_in_right:
            if node.left.bounds.inside(myEnt.Vertexes[end]): # myEnt end_point in node.left
                return self.getPreviousEntity(node.left, myEnt) or self.getPreviousEntity(node.right, myEnt)
            else:
                return self.getPreviousEntity(node.right, myEnt) or self.getPreviousEntity(node.left, myEnt)

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
                sorted_ents = sorted(ents, key=lambda ent: Centroid(ent.get_bounds()).x)
            elif dim == 1:
                sorted_ents = sorted(ents, key=lambda ent: Centroid(ent.get_bounds()).y)
            
            median = int((len(sorted_ents)+1)/2)

            leftentities = sorted_ents[0:median]
            rightentities = sorted_ents[median:]
            node.left = self._recursiveBuild(leftentities)
            node.right = self._recursiveBuild(rightentities)

            node.bounds = node.left.bounds.union(node.right.bounds)

        return node

def ezJoinPolys(entities): 
    bvh = BVHAccel(entities)
    sorted_polys = []
    total = len(entities)
    for i in range(total):
        if entities[i].joined:
            continue

        poly_is_closed = False
        polys = []
        polys.append(entities[i])
        entities[i].joined = True
        nextEntity = bvh.findNextEntity(polys)
        while nextEntity != None and (not nextEntity.joined):
            # Check if nextEntity and polys[0] form closed polyline
            if not nextEntity.reverse:
                end = -1
            else:
                end = 0

            if (len(polys) == 1):
                e0 = polys[0].m_entity
                if e0.dxftype() in ['ARC', 'LWPOLYLINE']:
                    if e0.dxftype() == 'ARC':
                        b0 = ezgetBulge(e0)
                    else:
                        b0 = e0.get_points()[-2][4]

                    checkEntity = nextEntity
                    v1 = polys[0].Vertexes[1] - polys[0].Vertexes[0]
                    v2 = checkEntity.Vertexes[end] - polys[0].Vertexes[1]  
                    
                    if b0 != 0.0 and b0 * (v1.x * v2.y - v1.y * v2.x) <= 0: # Different side with the bulge
                        checkEntity.joined = True # Temporary!!
                        nextEntity = bvh.findNextEntity(polys)
                        if nextEntity and not nextEntity.joined: # Find newEntity
                            checkEntity.joined = False # Return to False
                            checkEntity.reverse = False # Return to default!!
                            if nextEntity.reverse == False:
                                end = -1
                            else:
                                end = 0
                        else:
                            nextEntity = checkEntity # Did not find
            else:
                checkEntity = nextEntity
                pl1 = polys[-2] 
                if pl1.reverse:
                    pl1st = -1
                else:
                    pl1st = 0
                pl2 = polys[-1]
                # Check if nextEntity is on the same side with pl1 and pl2
                # find linear equation for pl2 : y = (y1 - y0) / (x1 - x0) * (x - x0) + y0
                V1 = pl2.Vertexes[0] #Vec2
                V2 = pl2.Vertexes[1] #Vec2
                if V1.x == V2.x: # Vertical line, x = const 
                    if (pl1.Vertexes[pl1st].x- V1.x) * (checkEntity.Vertexes[end].x - V1.x) <= 0: # pl1 start point is on the different side with checkEntity end point
                        checkEntity.joined = True # Temporary!!
                        nextEntity = bvh.findNextEntity(polys)
                        if nextEntity and not nextEntity.joined: # Find newEntity
                            checkEntity.joined = False # Return to False
                            checkEntity.reverse = False # Return to default!!
                            if nextEntity.reverse == False:
                                end = -1
                            else:
                                end = 0
                        else:
                            nextEntity = checkEntity # Did not find
                else:
                    m = (V2.y - V1.y) / (V2.x - V1.x)
                    if (pl1.Vertexes[pl1st].y - (m * (pl1.Vertexes[pl1st].x- V1.x) + V1.y)) * (checkEntity.Vertexes[end].y - (m * (checkEntity.Vertexes[end].x- V1.x) + V1.y)) <= 0:
                        checkEntity.joined = True # Temporary!!
                        nextEntity = bvh.findNextEntity(polys)
                        if nextEntity and not nextEntity.joined: # Find newEntity
                            checkEntity.joined = False # Return to False
                            checkEntity.reverse = False # Return to default!!
                            if nextEntity.reverse == False:
                                end = -1
                            else:
                                end = 0
                        else:
                            nextEntity = checkEntity # Did not find

            if nextEntity.Vertexes[end].isclose(polys[0].Vertexes[0]):
                polys.append(nextEntity)
                nextEntity.joined = True
                poly_is_closed = True
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

            while previousEntity != None and (not previousEntity.joined):
                # Join previousEntity
                reverse_polys.append(previousEntity)
                previousEntity.joined = True

                # find previousEntity
                previousEntity = bvh.findPreviousEntity(reverse_polys)

            polys = reverse_polys[::-1] + polys

        sorted_polys.append(polys)
        #print("\rProgressing : {}%".format(int(100*(i+1)/total)), end='', flush=True)  
    #print("\n", end='', flush=True)  
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
    def __init__(self, entity):
        self.m_entity = entity
        self.reverse = False
        self.joined = False
        self.Vertexes = self.getVertexes()
    
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
            bbox.extend(pl.vertices())
            return bbox

    def getVertexes(self):
        if self.m_entity.dxftype() == 'LINE':
            l = self.m_entity
            return [l.dxf.start, l.dxf.end]
        elif self.m_entity.dxftype() == 'ARC':
            arc = self.m_entity
            return [arc.start_point, arc.end_point]
        elif self.m_entity.dxftype() == 'LWPOLYLINE':
            pl = self.m_entity
            return [Vec2(pl.get_points('xy')[0]), Vec2(pl.get_points('xy')[-1])]

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
        tmpdoc.layers.add(name=l, color=abs(dxfdoc.layers.get(l).dxf.color))

        # deal with entities
        entities = []
        for e in dxfmsp.query('*[layer=="' + l + '"]'):
            if e.dxftype() == 'CIRCLE':
                tmpmsp.add_foreign_entity(e)
            
            elif e.dxftype() == 'LINE':
                # start and end not coincident
                if hash(e.dxf.start) != hash(e.dxf.end):
                    entity = myEntity(e)
                    entities.append(entity)

            elif e.dxftype() == 'ARC':
                entity = myEntity(e)
                entities.append(entity)

            elif e.dxftype() == 'LWPOLYLINE':
                if e.is_closed or Vec2(e.get_points('xy')[0]).isclose(Vec2(e.get_points('xy')[-1])):
                    if all([hash(pt) == hash(e.get_points('xy')[0]) for pt in e.get_points('xy')[1::]]): #exclude point polyline
                        pass
                    else:
                        e.close(True)
                        tmpmsp.add_foreign_entity(e)
                else:
                    entity = myEntity(e)
                    entities.append(entity)

            elif e.dxftype() == 'INSERT':
                if 'OBLONG' in e.dxf.name.upper():
                    # Get C1, C2, R
                    find_R = False
                    for be in e1.virtual_entities():
                        if not find_R and be.is_closed: # a circle in lwpolyline
                            V1 = Vec2(be.get_points('xy')[0])
                            V2 = Vec2(be.get_points('xy')[1])
                            R = V1.distance(V2) # since polyline width is the same as diameter
                            find_R = True
                        else: # a line in lwpolyline 
                            C1 = Vec2(be.get_points('xy')[0])
                            C2 = Vec2(be.get_points('xy')[1])
                    continue

                # break the block to entities
                for be in e.virtual_entities():
                    be.dxf.layer=l # set every be in layer l
                    if be.dxftype() == 'CIRCLE':
                        tmpmsp.add_foreign_entity(be)
                    
                    elif be.dxftype() == 'LINE':
                        entity = myEntity(be)
                        entities.append(entity)

                    elif be.dxftype() == 'ARC':
                        entity = myEntity(be)
                        entities.append(entity)

                    elif be.dxftype() == 'LWPOLYLINE':
                        if be.is_closed or Vec2(be.get_points('xy')[0]).isclose(Vec2(be.get_points('xy')[-1])):
                            if all([hash(pt) == hash(be.get_points('xy')[0]) for pt in be.get_points('xy')[1::]]): #exclude point polyline
                                pass
                            else:
                                be.close(True)
                                tmpmsp.add_foreign_entity(be)
                        else:
                            entity = myEntity(be)
                            entities.append(entity)
                    elif be.dxftype() == 'SOLID':
                        tmpmsp.add_lwpolyline(be.vertices(), close=is_poly_closed)
            
            else:
                pass

        print("Processing with Layer : {}".format(l), flush=True)
        start = time()
        sorted_entities = ezJoinPolys(entities)
        stop = time()
        print("Join polylines complete: \nTime Taken: {} secs".format(stop-start), flush=True)

        # Draw sorted_entities to tmpmsp on layer l
        for poly in sorted_entities:
            ezaddEntity(poly, tmpmsp, l)

    output_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\loveHuiyu.dxf"
    tmpdoc.saveas(output_path)

    FreeCADGui.updateGui()
    # ======= Draw tmpdoc in FreeCAD =======
    # Obtain the layers in tmpdoc
    ezlayers = []
    for lay_name in sel_layer:
        ezlayers.append(tmpdoc.layers.get(lay_name))

    # Traverse through each layer in tmpdoc
    for ezlay in ezlayers: 
        FCC.PrintMessage("Drawing layer : " + ezlay.dxf.name + " in FreeCAD\n")
        FreeCADGui.updateGui()

        # Query for LWPOLYLINE
        polylines = tmpmsp.query('LWPOLYLINE[layer=="' + ezlay.dxf.name + '"]')
        if polylines:
            FCC.PrintMessage("---Drawing " + str(len(polylines)) + " polylines...\n")

        num = 0
        for polyline in polylines:
            shape = ezdrawPolyline(polyline, num)
            if shape:
                newob = ezaddObject(shape, mydoc, "Polyline", ezlay)
                num += 1

        # Query for LINE
        lines = tmpmsp.query('LINE[layer=="' + ezlay.dxf.name + '"]')
        if lines:
            FCC.PrintMessage("---Drawing " + str(len(lines)) + " lines...\n")

        num = 0
        for line in lines:
            shape = ezdrawLine(line)
            if shape:
                newob = ezaddObject(shape, mydoc, "Line", ezlay)
                num += 1

        # Query for ARC
        arcs = tmpmsp.query('ARC[layer=="' + ezlay.dxf.name + '"]')
        if arcs:
            FCC.PrintMessage("---Drawing " + str(len(arcs)) + " arcs...\n")

        num = 0
        for arc in arcs:
            shape = ezdrawArc(arc)
            if shape:
                newob = ezaddObject(shape, mydoc, "Arc", ezlay)
                num += 1

        # Query for CIRCLE
        circles = tmpmsp.query('CIRCLE[layer=="' + ezlay.dxf.name + '"]')
        if circles: 
            FCC.PrintMessage("---Drawing " + str(len(circles)) + " circles...\n")

        num = 0
        for circle in circles:
            shape = ezdrawCircle(circle)
            if shape:
                newob = ezaddObject(shape, mydoc, "Circle", ezlay)
                num += 1

        if not polylines and not lines and not arcs and not circles:
            lay_color = tuple( i/255 for i in ezdxf.colors.aci2rgb(ezlay.color))
            lay = ezlocateLayer(ezlay.dxf.name, mydoc, lay_color, "Solid")


    # Finishing
    print("done processing")

    mydoc.recompute()
    print("recompute done")

    FCC.PrintMessage("successfully imported.\n")
    FreeCADGui.updateGui()

def ezaddEntity(ent_list, tmpmsp, l):
    # Draw one poly at one time
    if len(ent_list) == 1:
        e = ent_list[0].m_entity
        tmpmsp.add_foreign_entity(e)
    else:
        vertexes = []
        line_width = 0
        set_width = False

        # Add start vertex to vertexes!
        for myEnt in ent_list:
            e = myEnt.m_entity
            if myEnt.reverse == False:
                start = 0
            else:
                start = -1

            if e.dxftype() == 'LINE':
                vertexes.append((myEnt.Vertexes[start].x, myEnt.Vertexes[start].y))

            elif e.dxftype() == 'ARC':
                if myEnt.reverse == False:
                    vertexes.append((myEnt.Vertexes[start].x, myEnt.Vertexes[start].y,0,0,ezgetBulge(e)))
                else:
                    vertexes.append((myEnt.Vertexes[start].x, myEnt.Vertexes[start].y,0,0,-ezgetBulge(e)))

            elif e.dxftype() == 'LWPOLYLINE':
                if not set_width:
                    line_width = e.dxf.const_width
                    set_width = True
                if myEnt.reverse == False:
                    vertexes += e.get_points()[:-1:]
                else:
                    pts = e.get_points()
                    m = len(pts)
                    rev_pts = [(pts[m-i-1][0], pts[m-i-1][1], pts[m-i-1][3], pts[m-i-1][2], -pts[m-i-2][4]) for i in range(m)]
                    vertexes += rev_pts[:-1:]

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
            #Add last_end Vertexes[end]
            vertexes.append((last_ent.Vertexes[end].x, myEnt.Vertexes[end].y))

        tmpmsp.add_lwpolyline(vertexes, close=is_poly_closed, dxfattribs={"layer" : l, "const_width" : line_width,})

def ezgetBulge(arc):
    span_angle = arc_angle_span_deg(arc.dxf.start_angle, arc.dxf.end_angle)
    V1 = arc.start_point
    V2 = arc.end_point
    center = arc.dxf.center
    radius = arc.dxf.radius
    M = (V1 + V2)/2
    epsilon = 0.0001
    if span_angle < 180 - epsilon:
        d = radius * (M - center).normalize()
    elif abs(span_angle - 180.0) < epsilon:
            return 1.0
    else:
        d = radius * (center - M).normalize()
    S = center + d
    return S.distance(M) / V2.distance(M)


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
    if len(polyline) > 1:
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
                        pass
                        #importDXF.warn(polyline, num)
                else:
                    try:
                        edges.append(Part.Arc(v1, cv, v2).toShape())
                    except Part.OCCError:
                        pass
                        #importDXF.warn(polyline, num)
            else:
                try:
                    edges.append(Part.LineSegment(v1, v2).toShape())
                except Part.OCCError:
                    pass
                    #importDXF.warn(polyline, num)

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
                        pass
                        #importDXF.warn(polyline, num)
                else:
                    try:
                        edges.append(Part.Arc(v1, cv, v2).toShape())
                    except Part.OCCError:
                        pass
                        #importDXF.warn(polyline, num)
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
                pass
                #importDXF.warn(polyline, num)
    return None

def ezdrawLine(line):
    v1 = ezvec(line.dxf.start)
    v2 = ezvec(line.dxf.end)
    if not DraftVecUtils.equals(v1, v2):
        try:
            if (dxfCreateDraft or dxfCreateSketch):
                return Draft.makeWire([v1, v2])
            else:
                return Part.LineSegment(v1, v2).toShape()
        except Part.OCCError:
            pass
            #importDXF.warn(line)
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
        pass
        #importDXF.warn(arc)
    return None

def ezdrawCircle(circle):
    v = ezvec(circle.dxf.center)
    curve = Part.Circle()
    curve.Radius = ezvec(circle.dxf.radius)
    curve.Center = v
    try:
        if (dxfCreateDraft or dxfCreateSketch):
            #pl = placementFromDXFOCS(circle)
            pl = FreeCAD.Placement()
            return Draft.makeCircle(circle.radius, pl)
        else:
            return curve.toShape()
    except Part.OCCError:
        pass
        #importDXF.warn(circle)
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
