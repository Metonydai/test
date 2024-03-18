import ezdxf
from ezdxf.math import Vec2
from ezdxf.math import BoundingBox2d
from ezdxf.math import arc_angle_span_deg
from enum import Enum
from time import time


def ezjoin(doc, tmpdoc, sel_layer):
    msp = doc.modelspace()
    tmpmsp = tmpdoc.modelspace()
    
    # copy sel_layer to tmpdoc and deal with entities
    for l in sel_layer:
        tmpdoc.layers.add(name=l, color=doc.layers.get(l).dxf.color)

        # deal with entities
        entities = []
        for e in msp.query('*[layer=="' + l + '"]'):
            if e.dxftype() == 'CIRCLE':
                tmpmsp.add_foreign_entity(e)
            
            elif e.dxftype() == 'LINE':
                entity = myEntity(e)
                entities.append(entity)

            elif e.dxftype() == 'ARC':
                entity = myEntity(e)
                entities.append(entity)

            elif e.dxftype() == 'LWPOLYLINE':
                if e.is_closed or Vec2(e.get_points('xy')[0]).isclose(Vec2(e.get_points('xy')[-1])):
                    e.close(True)
                    tmpmsp.add_foreign_entity(e)
                else:
                    entity = myEntity(e)
                    entities.append(entity)
            
            else:
                pass

        print("Deal with Layer : {}".format(l), flush=True)
        start = time()
        sorted_entities = ezJoinPolys(entities)
        stop = time()
        print("Join polylines complete: \nTime Taken: {} secs\n".format(stop-start), flush=True)

        # Draw sorted_entities to tmpmsp on layer l
        for poly in sorted_entities:
            ezaddEntity(poly, tmpmsp, l)           

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

def ezaddEntity(ent_list, tmpmsp, l):
    if len(ent_list) == 1:
        e = ent_list[0].m_entity
        tmpmsp.add_foreign_entity(e)
    else:
        vertexes = []

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

        tmpmsp.add_lwpolyline(vertexes, close=is_poly_closed, dxfattribs={"layer": l})

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
        print("BVH Generation complete: \nTime Taken: {} secs".format(stop-start), flush=True)

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
    for i in range(len(entities)):
        if entities[i].joined:
            continue

        poly_is_closed = False
        polys = []
        polys.append(entities[i])
        entities[i].joined = True
        nextEntity = bvh.findNextEntity(polys)
        while nextEntity != None and (not nextEntity.joined):
            # Check if nextEntity and polys[0] form closed polyline
            if nextEntity.reverse == False:
                end = -1
            else:
                end = 0

            if (len(polys) >= 2):
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
                    if (pl1.Vertexes[pl1st].y - (m * (pl1.Vertexes[pl1st].x- V1.x) + V1.y)) * (checkEntity.Vertexes[end].y - (m * (checkEntity.Vertexes[0].x- V1.x) + V1.y)) <= 0:
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
        print("\rProgressing : {}%".format(int(100*(i+1)/total)), end='', flush=True)  

    print("\n", end='', flush=True)  
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

#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\HUIYU.dxf"
file_path = "C:\\Users\\KyoaniDai\\Desktop\\dxf\\HUIYU0318.dxf"
#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\loveHuiyu.dxf"
#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\壓合\\台達電 DV-1000I 2976804200 壓合治具(驗證).dxf"
#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\slot_huiyu.dxf"
#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\壓合\\XGS1935-52_52HP-US MB 2976679600 壓合.dxf"
#file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\壓合\\XGS1935-52_52HP-US MB 2976679600 壓合.dxf"

doc = ezdxf.readfile(file_path)
#msp = doc.modelspace()
for layer in doc.layers:
    print(layer.dxf.name)

tmpdoc = ezdxf.new()
#tmpmsp = tmpdoc.modelspace()

#sel_layer = ['BOARD_ART', 'TOP_SILK_ART']
#sel_layer = ['BOARD_ART']
sel_layer = ['SST']

# copy sel_layer to tmpdoc
#for l in sel_layer:
    #tmpdoc.layers.add(name=l, color=doc.layers.get(l).dxf.color)

ezjoin(doc, tmpdoc, sel_layer)


output_path = "C:\\Users\\KyoaniDai\\Desktop\\dxf\\LoveHuiyu.dxf"
#output_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\loveHuiyu.dxf"
tmpdoc.saveas(output_path)
