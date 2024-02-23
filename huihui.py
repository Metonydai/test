import ezdxf
from ezdxf.math import Vec2

file_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\HuiyuTony.dxf"
doc = ezdxf.readfile(file_path)
#msp = doc.modelspace()

tmpdoc = ezdxf.new()
#tmpmsp = tmpdoc.modelspace()

sel_layer = ['lovehui']

# copy sel_layer to tmpdoc
for l in sel_layer:
    tmpdoc.layers.add(name=l, color=doc.layers.get(l).dxf.color)

def ezjoin(doc, tmpdoc, sel_layer):
    msp = doc.modelspace()
    tmpmsp = tmpdoc.modelspace()
    
    for l in sel_layer:
        entities = []
        for e in msp.query('*[layer=="' + l + '"]'):
            if e.dxftype() == 'CIRCLE':
                tmpmsp.add_foreign_entity(e)
            
            elif e.dxftype() == 'LWPOLYLINE':
                if e.is_closed or Vec2(e.get_points('xy')[0]).isclose(Vec2(e.get_points('xy')[-1])):
                    e.close(True)
                    tmpmsp.add_foreign_entity(e)

            else:
                entity = myEntity(e)
                entities.append(entity)
            
        bvh = BVHAccel(entities)
        #bvh.findCoincidentEntity(entity)
            
        

from enum import Enum
from time import time
from ezdxf.math import BoundingBox2d

class myEntity:
    def __init__(self, entity, check=False):
        self.m_entity = entity
        self.m_check = check
    
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
        else:
            return BoundingBox2d()
            

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

    def coincident(self, myEnt):
        node = self.root
        return self.findCoincidentEntity(node, myEnt)
    
    def findCoincidentEntity(self, node, myEnt):
        ent = myEnt.m_entity
        #if ent.dxftype() == 'CIRCLE':
            #c = self.m_entity.dxf.center
            #r = self.m_enitty.dxf.radius
            #return BoundingBox2d([c - Vec2(-r, -r), c + Vec2(r,r)])
        if ent.dxftype() == 'LINE':
            start_point = ent.dxf.start
            end_point = ent.dxf.end
        elif self.m_entity.dxftype() == 'ARC':
            start_point = ent.start_point
            end_point = ent.end_point
        elif self.m_entity.dxftype() == 'LWPOLYLINE':
            start_point = Vec2(ent.get_points('xy')[0])
            end_point = Vec2(ent.get_points('xy')[0])
        else:
            start_point = Vec2(float('inf'), float('inf'))
            end_point = Vec2(float('inf'), float('inf'))


        # Leaf node
        if (node.object != None and node.object != myEnt):
            return node

        epoint_in_left = node.left.bounds.insed(end_point)
        epoint_in_right = node.right.bounds.inside(end_point)

        return

    
    def _recursiveBuild(self, ents):
        node = BVHBuildNode()
        #bounds = BoundingBox2d()
        if (len(ents) == 1):
            node.bounds = ents[0].get_bounds()
            node.object = ents[0].m_entity
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

def Centroid(bbox):
    # UVec
    return 0.5*(bbox.extmin + bbox.extmax)

def maxExtent(bbox):
    d = bbox.extmax- bbox.extmin
    if (d.x > d.y):
        return 0
    else:
        return 1

class BVHBuildNode:
    def __init__(self):
        self.left = None
        self.right = None
        self.object = None
        self.bounds = BoundingBox2d()


ezjoin(doc, tmpdoc, sel_layer)


output_path = "C:\\Users\\Tony.dai\\Desktop\\fixture\\new_issue\\DDC需求資料\\loveHuiyuTony.dxf"
tmpdoc.saveas(output_path)
