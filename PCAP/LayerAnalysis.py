import Part
import FreeCAD as App
import importDXF
import re
import os
from time import time
import logging
import pcaplib
from math import sqrt

MAX_POINTS_PER_NODE = 4

class Dot:
    def __init__(self, idx, shape):
        self.x = shape.Vertexes[idx].X
        self.y = shape.Vertexes[idx].Y
        self.connected = False
        self.point = App.Vector(self.x, self.y, 0)
        self.idx = idx
        if self.idx == 0: 
            self.udir = (shape.Vertexes[0].Point - shape.Vertexes[1].Point).normalize()
        elif self.idx == -1:
            self.udir = (shape.Vertexes[-1].Point - shape.Vertexes[-2].Point).normalize()
        self.paired = None
        self.shape = shape
    def set_paired_dot(self, paired):
        self.paired = paired

class GPin:
    def __init__(self, wire):
        self.wire = wire
        self.C1, self.C2 = self._findCenter()
        self.radius = 0
        self.isCircle = False
        self.pcb_dir1 = None
        self.pcb_dir2 = None
    def _findCenter(self):
        if len(self.wire.Edges) == 1: # Circle
            cen = self.wire.Edges[0].Curve.Center
            self.isCircle = True
            return cen, cen
        cens = []
        for e in self.wire.Edges:
            if e.Curve.TypeId == "Part::GeomCircle":
                cens.append(e.Curve.Center)
                if self.radius==0:
                    self.radius = e.Curve.Radius
        assert len(cens) == 2, "Guide Pin Shape Error"
        # Check C1 and C2 are coincident
        if hash((cens[0].x, cens[0].y)) == hash((cens[1].x, cens[1].y)):
            self.isCircle = True
        return cens[0], cens[1]

    def set_pcb_dir1(self, vec):
        self.pcb_dir1 = vec

    def set_pcb_dir2(self, vec):
        self.pcb_dir2 = vec

    @property
    def diameter(self):
        return 2 * self.radius

    @property
    def C12_udir(self):
        if self.isCircle:
            return None
        return (self.C2- self.C1).normalize()

class PairedEdge:
    def __init__(self, left_open, right_open):
        self.left_open = left_open
        self.right_open = right_open
        self.C1 = left_open.Curve.Center
        self.C2 = right_open.Curve.Center
        self.C12_udir = (self.C2- self.C1).normalize()
    def is_horizontal(self):
        epsilon = 0.000001
        return abs((self.C12_udir).dot(App.Vector(0,1,0))) < epsilon

class RTOpen:
    def __init__(self, wire):
        self.wire = wire
        self.h_lines, self.v_lines = self._find_lines()
        self.rtEdge_pair = []
        self.strokes = 0
    def _find_lines(self):
        epsilon = 0.000001
        w = self.wire
        h_lines = []
        v_lines = []
        for e in w.Edges:
            if e.Curve.TypeId == 'Part::GeomLine':
                e_tan = e.tangentAt(0)
                if abs(e_tan.dot(App.Vector(0.0, 1.0, 0.0))) < epsilon: # h_lines
                    h_lines.append(e)
                elif abs(e_tan.dot(App.Vector(1.0, 0.0, 0.0))) < epsilon: # v_lines
                    v_lines.append(e)
        
        h_lines.sort(key=lambda line: line.Vertexes[0].Point.y)       
        v_lines.sort(key=lambda line: line.Vertexes[0].Point.x)       
        return h_lines, v_lines

    def find_pair_paralines(self):
        if not self.rtEdge_pair:
            return
        paralines = [] # list of edges
        for paired_edge in self.rtEdge_pair:
            if (paired_edge.is_horizontal()):
                paralines.append(self._find_adjacent_lines(paired_edge.C1.y, True))
            else:
                paralines.append(self._find_adjacent_lines(paired_edge.C1.x, False))
        return paralines
            
    def _find_adjacent_lines(self, value, horizontal):           
        if horizontal:
            hl = self.h_lines
            l, u = 0, len(hl)-1
            mid = (l + u) // 2
            while (l <= u):
                if hl[mid].Vertexes[0].Point.y < value < hl[mid+1].Vertexes[0].Point.y:
                    a1 = value - hl[mid].Vertexes[0].Point.y
                    a2 = hl[mid+1].Vertexes[0].Point.y- value
                    if abs(a1 - a2) < 0.01: # absolutely close
                        return [hl[mid], hl[mid+1]]
                    elif a1 > a2 and mid+2 < len(hl)-1: # find next line
                        return [hl[mid], hl[mid+2]]
                    else:
                        return [hl[mid-1], hl[mid+1]]
                elif value >= hl[mid+1].Vertexes[0].Point.y:
                    l = mid+1
                else:
                    u = mid
                mid = (l + u) // 2
        else:
            vl = self.v_lines
            l, u = 0, len(vl)-1
            mid = (l + u) // 2
            while (l <= u):
                if vl[mid].Vertexes[0].Point.x < value < vl[mid+1].Vertexes[0].Point.x:
                    a1 = value - vl[mid].Vertexes[0].Point.x
                    a2 = vl[mid+1].Vertexes[0].Point.x- value
                    if abs(a1 - a2) < 0.01: # absolutely close
                        return [vl[mid], vl[mid+1]]
                    elif a1 > a2 and mid+2 < len(hl)-1: # find next line
                        return [vl[mid], vl[mid+2]]
                    else:
                        return [vl[mid-1], vl[mid+1]]
                elif value >= vl[mid+1].Vertexes[0].Point.x:
                    l = mid+1
                else:
                    u = mid
                mid = (l + u) // 2
            
    def set_rtEdge_pair(self, pair_list):
        self.rtEdge_pair = pair_list
        self.strokes = len(pair_list)

class Point:
    def __init__(self, w, f="None", l=""):
        self.wire = w
        self.face = f
        self.label = l
        self.x = w.CenterOfMass.x
        self.y = w.CenterOfMass.y
        self.check = False

class Point2:
    def __init__(self, Vec, l_idx, w_idx):
        self.x = Vec.x
        self.y = Vec.y
        self.layer_idx = l_idx
        self.wire_idx = w_idx

class QuadTree:
    def __init__(self, x_min, y_min, x_max, y_max, depth=0):
        self.x_min = x_min
        self.y_min = y_min
        self.x_max = x_max
        self.y_max = y_max
        self.points = []
        self.children = [None, None, None, None]
        self.depth = depth

    def insert(self, point):
        x, y = point.x, point.y

        if not (self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max):
            return False

        if len(self.points) <= MAX_POINTS_PER_NODE:  # Define a threshold
            # There's room for our point without dividing the Quadree
            self.points.append(point)
            return True

        if None in self.children:
            self.subdivide()

        quadrant = self.get_quadrant(point)
        return self.children[quadrant].insert(point)

    def subdivide(self):
        x_mid = (self.x_min + self.x_max) / 2
        y_mid = (self.y_min + self.y_max) / 2

        # Create four child selfs representing quadrants
        self.children[0] = QuadTree(self.x_min, self.y_min, x_mid, y_mid, self.depth+1) # Bottom-left
        self.children[1] = QuadTree(x_mid, self.y_min, self.x_max, y_mid, self.depth+1) # Bottom-right
        self.children[2] = QuadTree(self.x_min, y_mid, x_mid, self.y_max, self.depth+1) # Top-left
        self.children[3] = QuadTree(x_mid, y_mid, self.x_max, self.y_max, self.depth+1) # Top-right

    def get_quadrant(self, point):
        x_mid = (self.x_min + self.x_max) / 2
        y_mid = (self.y_min + self.y_max) / 2

        if point.x <= x_mid:
            if point.y <= y_mid:
                return 0  # Bottom-left quadrant
            else:
                return 2  # Top-left quadrant
        else:
            if point.y <= y_mid:
                return 1  # Bottom-right quadrant
            else:
                return 3  # Top-right quadrant
    
    def get_all_points(self):
        point_list = self.points
        for child in self.children:
            if child: # child is not none
                point_list += child.get_all_points()
        return point_list

def initialize_tree(node):
    # Set all points' check to False
    if node is None:
        return
    for point in node.points:
        point.check = False
    for child in node.children:
        initialize_tree(child)

def query_not_checked(node):
    result = []

    if node is None:
        return result

    for point in node.points:
        if not point.check:
            result.append(point)

    for child in node.children:
        result.extend(query_not_checked(child))

    return result

def query_range(node, bbox):
    result = []

    if node is None:
        return result

    if not is_intersect(node, bbox):
        return result

    for point in node.points:
        x, y = point.x, point.y
        if bbox.XMin <= x <= bbox.XMax and bbox.YMin <= y <= bbox.YMax:
            result.append(point)

    for child in node.children:
        result.extend(query_range(child, bbox))

    return result


def is_intersect(node, bbox):
    # Check if the bbox and the node have no overlap
    return not (bbox.XMax < node.x_min or
                bbox.XMin > node.x_max or
                bbox.YMax < node.y_min or
                bbox.YMin > node.y_max)



def formObject(obj, name=''):
    Part.show(obj, name)
    return App.ActiveDocument.Objects[-1]

def isWireInside(region, wire):
    face = Part.Face(region)
    pts = wire.discretize(40)
    for p in pts:
        if not face.isInside(p, 1e-7, True):
            return False
    return True

def bboxCheck(feature1, feature2):
    # return true if BoundBox1 encloses BoundBox2
    return feature1.BoundBox.isInside(feature2.BoundBox)

def featureToClosedWire(grp_list, is_layer_silk):
    wire_list=[]
    label_list=[]
    if is_layer_silk:
        nonclosed_shape = [] # For nonclosed_shape, such as line segament or nonclosed_poly
        for feature in grp_list:
            shape=feature.Shape
            if shape.Wires != []:
                wire = shape.Wires[0]
                if wire.isClosed():
                    # Exclusion of "8"
                    #if len(wire.Vertexes) != len(wire.Edges):
                        #continue
                    # Exclusion of "0"
                    #if len(wire.Edges) == 20 and all(map(lambda e: e.Length < 0.1, wire.Edges)):
                        #continue
                    # Exclusion of "Q"
                    #if len(wire.Edges) == 22
                    # Exclusion of "D"
                    #if len(wire.Edges) == 13
                    if all(map(lambda e: e.Length < 0.80, wire.Edges)):
                        continue
                    wire_list.append(wire)
                    label_list.append(feature.Label+ "_exp")
                else:
                    # Filter Text and English Alphabet from A-Z and 0-9 (exclude 0, 8, Q, D, which is closed)
                    if all(map(lambda e: e.Length < 0.80, wire.Edges)):
                        continue
                    nonclosed_shape.append(shape)
                
            elif shape.isClosed(): # Circle
                wire = Part.Wire(shape.Edges)
                wire_list.append(wire)
                label_list.append(feature.Label+ "_exp")
            
            else:
                nonclosed_shape.append(shape)
        
        closed_wire = connectDots(nonclosed_shape)
        for wire in closed_wire:
            wire_list.append(wire)
            label_list.append("")
    else:
        for feature in grp_list:
            shape=feature.Shape
            if shape.Wires != []:
                wire = shape.Wires[0]
                if wire.isClosed():
                    wire_list.append(wire)
                    label_list.append(feature.Label+ "_exp")
            elif shape.isClosed(): # Circle
                wire = Part.Wire(shape.Edges)
                wire_list.append(wire)
                label_list.append(feature.Label+ "_exp")
    return wire_list, label_list

def findBoundBox(shape_list):
    bbox = App.BoundBox()
    for sh in shape_list:
        bbox.add(sh.BoundBox)
    return bbox

def rayBoundBox(origin, udir, length, epsilon=0.0001):
    # For 2D 
    V1 = origin + epsilon * udir # Try to add an epsilon along udir, to avoid find itself
    V2 = origin + length * udir
    if abs(udir.dot(App.Vector(0, 1, 0))) < epsilon: # x-dir
        return App.BoundBox(V1 + 0.5*epsilon*App.Vector(0,-1,0), V2 + 0.5*epsilon*App.Vector(0,1,0))
    if abs(udir.dot(App.Vector(1, 0, 0))) < epsilon: # y-dir
        return App.BoundBox(V1 + 0.5*epsilon*App.Vector(-1,0,0), V2 + 0.5*epsilon*App.Vector(1,0,0))
    return App.BoundBox(V1, V2)

def findNextArc(center, udir, quad_tree, searchLength = 30):
    epsilon = 0.1

    ray_bbox = rayBoundBox(center, udir, searchLength, epsilon)
    find_pts = query_range(quad_tree, ray_bbox)
    if not find_pts:
        return None
    find_pts.sort(key = lambda f_pt : (f_pt.wire.CenterOfMass - center).dot(udir)) # projection on udir
    # Find Linear Equation : ax + by + c = 0
    # c = -a*x0 - b*y0
    a = -udir.y
    b = udir.x
    c = -a * center.x - b * center.y

    for f_pt in find_pts:
        if f_pt.x == center.x and f_pt.y == center.y:
            continue
        if abs(a * f_pt.x + b * f_pt.y + c) < epsilon and not f_pt.check: # f_dot colinear
            return f_pt
    return None

def findNextDot(pdot, quad_tree, searchLength = 30):
    epsilon = 0.00000001

    ray_bbox = rayBoundBox(pdot.point, pdot.udir, searchLength, epsilon)
    find_dots = query_range(quad_tree, ray_bbox)
    if not find_dots:
        return None
    find_dots.sort(key = lambda f_dot : (f_dot.point - pdot.point).dot(pdot.udir)) # projection on pdot.udir
    # Find Linear Equation : ax + by + c = 0
    # c = -a*x0 - b*y0
    a = -pdot.udir.y
    b = pdot.udir.x
    c = -a * pdot.x - b * pdot.y

    for f_dot in find_dots:
        if f_dot.x == pdot.x and f_dot.y == pdot.y:
            continue
        if abs(a * f_dot.x + b * f_dot.y + c) < epsilon and not f_dot.connected: # f_dot colinear
            return f_dot
    return None

def reversePoly(wire):
    # Reverse the direction of the poly
    return Part.Wire(wire.Edges[::-1])

def connectDots(nonclosed_shape):
    closed_wire = []
    bbox = findBoundBox(nonclosed_shape)
    # Create a QuadTree Node
    quad_tree = QuadTree(bbox.XMin, bbox.YMin, bbox.XMax, bbox.YMax)
    # Insert Dot class type
    for sh in nonclosed_shape:
        if len(sh.Vertexes) == 1: # Just a point
            continue
        start = Dot(0, sh)
        end = Dot(-1, sh)
        start.set_paired_dot(end)
        end.set_paired_dot(start)
        quad_tree.insert(end) # Insert sh's end point
        quad_tree.insert(start) # Insert sh's start point
        
    dot_list = quad_tree.get_all_points()
    #print("len(dot_list) : {} ".format(len(dot_list)))
    for dot in dot_list:
        if dot.connected:
            continue
        
        polys = []
        current_dot = dot
        next_dot = findNextDot(current_dot, quad_tree)
        record_dots = []

        i = 0
        while next_dot: 
            if (i > 20): # Don't join too many times
                break
            # Consider the direction of the poly
            if current_dot.idx == -1:
                polys.append(current_dot.shape) # Collect the dot's shape(Edge or Wire)
            else:
                polys.append(reversePoly(current_dot.shape)) # Revere the wire
            polys.append(Part.makeLine(current_dot.point, next_dot.point)) # Collect new connected shape(Edge)
            record_dots.append(current_dot)
            record_dots.append(next_dot)
            if next_dot.paired == record_dots[0]: # Form a Region
                closed_wire.append(Part.Wire(polys)) 
                #Part.show(Part.Wire(polys))
                # Set all con_dot connected
                for con_dot in record_dots:
                    con_dot.connected = True
                break
            # Continue to find next point
            current_dot = next_dot.paired
            next_dot = findNextDot(current_dot, quad_tree)
            i += 1
    
    return closed_wire

def regionFormed(l_wires):
    region_list=[]
    del_index=[]
    for i, l_wire1 in enumerate(l_wires):
        l_wire1_enclosed=[]
        for j, l_wire2 in enumerate(l_wires):
            if i == j:
                continue

            if not bboxCheck(l_wire1, l_wire2):
                continue

            if isWireInside(l_wire1, l_wire2):
                l_wire1_enclosed.append(l_wire2)
                del_index.append(j)

        if l_wire1_enclosed != []:
            face1=Part.Face(l_wire1)
            faces=[]
            for wire in l_wire1_enclosed:
                faces.append(Part.Face(wire))
            region_list.append(face1.cut(faces))
        else:
            face1=Part.Face(l_wire1)
            region_list.append(face1)

    del_index.sort(reverse=True)

    for i in del_index:
        region_list.pop(i)

    return region_list

def minDist(face_region, inside_wire):
    min_dist = float('inf')
    for l_wire in face_region.Wires:
        dist = l_wire.distToShape(inside_wire)[0]
        if dist < min_dist:
            min_dist = dist
    return min_dist

class Layer():
    def __init__(self, label, is_layer_silk=False):
        #self.name = name
        self.label = label
        self.wire_list, self.label_list = featureToClosedWire(self.getLayer().Group, is_layer_silk)
        self.face_list = []
        self.depth = self.getDepth()

    def getLayer(self):
        p = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft")
        if (p.GetBool("dxfUseDraftVisGroups")): #Draft Layer
            for layer in App.ActiveDocument.LayerContainer.Group:
                if layer.Label == self.label:
                    return layer
        else:  #Group object
            for layer in App.ActiveDocument.RootObjects:
                if layer.Label == self.label:
                    return layer

    def createFace(self, overlap_check = False):
        if overlap_check:
            self.face_list = regionFormed(self.wire_list)
        else:
            self.face_list = [Part.Face(w) for w in self.wire_list]

    def getDepth(self):
        m = re.search(r'\d+\.?\d*', self.label)
        if m:
            return float(m.group())
        else:
            n = re.search('open|through|thru', self.label)
            if n:
                return float('inf')
            return 0

class specialLayer(Layer):
    def __init__(self, label):
        self.label = label
        self.wire_list = self.getWire()
    def getLayer(self):
        return super().getLayer()
    def getWire(self):
        return [feature.Shape for feature in self.getLayer().Group]

def checkForProblem(layer_selected_list, quad_tree, dr):
    result = []
    for layer in layer_selected_list:
        layer.createFace(overlap_check=True)
        for l_face in layer.face_list:
            included = query_range(quad_tree, l_face.BoundBox)
            for point in included:
                # Already Checked
                if point.check == True:
                    continue
                # Not inside the grooving region
                if not l_face.isInside(point.wire.CenterOfMass, 0.0, True):
                    continue

                # Distance Check
                point.check = True
                if minDist(l_face, point.wire) < dr:
                    result.append(point)

    return result

def getBoard(b_list, area_bound):
    for pnt in b_list:
        if pnt.face.Area > area_bound:
            return pnt

def delUnnecessary(pairsOfVec):
    vset = set()
    freecad_pairs = []
    #from math import floor
    for vec1, vec2 in pairsOfVec:
        #vset.add(((floor(vec1.x*1E6)/1E6, floor(vec1.y*1E6)/1E6), (floor(vec2.x*1E6)/1E6, floor(vec2.y*1E6)/1E6)))
        vset.add(((round(vec1.x,5), round(vec1.y, 5)), (round(vec2.x,5), round(vec2.y,5))))
    #Transform vset to freecad vector
    for vert1, vert2 in vset:
        freecad_pairs.append([App.Vector(vert1[0], vert1[1], 0), App.Vector(vert2[0], vert2[1], 0)])

    return freecad_pairs

def gapCheck(wire1, wire2, dist):
    tolerance = 0.00001
    result = []
    d = wire1.distToShape(wire2)
    if d[0] < dist- tolerance:
        App.Console.PrintWarning("The gap between two wires is {}mm. ".format(round(d[0],6)))
        App.Console.PrintWarning("Designed gap : {}\n".format(dist))

        vec_pair = delUnnecessary(d[1])

        for vert1, vert2 in vec_pair:
            cen = (vert1+ vert2)/2
            r = sqrt((vert1- vert2).dot(vert1- vert2))/2
            circle = Part.makeCircle(r, cen)
            result.append(formObject(circle))

    return result

def findGroove(wire, tangents):
    idxes = []
    edges = wire.Edges
    # Determine whether the curve is counter-clockwise or clockwise
    # First find the line idx
    l_idx = 0
    while edges[l_idx].Curve.TypeId != 'Part::GeomLine':
        l_idx += 1
    l_tan = edges[l_idx].tangentAt(0)
    l_normal = App.Rotation(App.Vector(0,0,1), 90).multVec(l_tan)
    # Make the disturbance along the l_normal to see if the pnt is inside the curve. 
    l_pnt = edges[l_idx].Vertex1.Point+ 0.1*l_normal
    if Part.Face(wire).isInside(l_pnt, 1e-7, True):
        ccw = 1
    else:
        ccw = -1

    L = len(edges)
    i = 0
    while i < L:
        i_tan = edges[i].tangentAt(0)
        if edges[i].Curve.TypeId == 'Part::GeomLine' and (i_tan in tangents) and \
        edges[(i+1)%L].Curve.TypeId == 'Part::GeomCircle' and \
        edges[(i+2)%L].Curve.TypeId == 'Part::GeomLine' and \
        edges[(i+3)%L].Curve.TypeId == 'Part::GeomCircle' and \
        edges[(i+4)%L].Curve.TypeId == 'Part::GeomLine' and edges[(i+4)%L].tangentAt(0) == i_tan and\
        edges[(i+5)%L].Curve.TypeId == 'Part::GeomCircle' and \
        edges[(i+6)%L].Curve.TypeId == 'Part::GeomLine' and \
        edges[(i+7)%L].Curve.TypeId == 'Part::GeomCircle' and \
        edges[(i+8)%L].Curve.TypeId == 'Part::GeomLine' and edges[(i+8)%L].tangentAt(0) == i_tan:
            # Further Check: edges[i] and edges[i+4]
            if i_tan.x == 0.0:
                if (edges[i].Vertex1.Point.x*i_tan.y*ccw < edges[(i+4)%L].Vertex1.Point.x*i_tan.y*ccw) and\
                abs(edges[i].Vertex1.Point.x - edges[(i+8)%L].Vertex1.Point.x) < 0.00001:
                    idxes.append(i)
                    i += 8
                else:
                    i += 4
            else: #i_tan.y == 0.0 
                if (edges[i].Vertex1.Point.y*i_tan.x*ccw > edges[(i+4)%L].Vertex1.Point.y*i_tan.x*ccw) and\
                abs(edges[i].Vertex1.Point.y - edges[(i+8)%L].Vertex1.Point.y) < 0.00001:
                    idxes.append(i)
                    i += 8
                else:
                    i += 4
        else:
            i += 1

    return idxes, ccw

def findStopBlockWire(layer_stopBlock):
    l_wires = layer_stopBlock.wire_list
    max_wires = []
    enclosed_wires = [0] * len(l_wires)
    for i, l_wire1 in enumerate(l_wires):
        if enclosed_wires[i] == 1:
            continue
        for j, l_wire2 in enumerate(l_wires):
            if i == j or enclosed_wires[j] == 1:
                continue
            if bboxCheck(l_wire1, l_wire2): # l_wire1 encloses l_wire2
                enclosed_wires[j] = 1

    for idx, value in enumerate(enclosed_wires):
        if not value: # Means the wire is not enclosed by other wires
            max_wires.append(l_wires[idx])

    return max_wires

def run_router():
    start = time()
    epsilon = 0.000001

    # Determine the output folder
    filePath = pcaplib.get_pcap_dxf_file_path()
    output_folder = pcaplib.get_pcap_output_folder() or os.path.dirname(os.path.abspath(filePath))

    # Construct the output file path using os.path.join
    output_file_path = os.path.join(output_folder, "final_result.dwg")

    # Get values from pcaplib
    dr = float(pcaplib.get_pcap_dr())
    area_bound = float(pcaplib.get_pcap_area_bound())
    rtHoleWidth = float(pcaplib.get_rt_hole_width())
    rtHoleAddLen = float(pcaplib.get_rt_hole_add_len())
    rtDGuidePinInside = float(pcaplib.get_rt_d_guide_pin_inside())
    rtDGuidePinBreakAway = float(pcaplib.get_rt_d_guide_pin_break_away())

    # Initialize Custom Layer Object
    if not pcaplib.get_rt_layers():
        App.Console.PrintWarning("Please select the layers and then press the \"Save Setting\" button!\n")
        return -1
    if not pcaplib.get_pcap_layer_of_botsilk():
        App.Console.PrintWarning("Cannot find Layer Botsilk.\n")
        return -1
    if not pcaplib.get_pcap_layer_of_botpaste():
        App.Console.PrintWarning("Cannot find Layer Botpaste.\n")
        return -1
    #if not pcaplib.get_pcap_layer_of_botmask():
    #    App.Console.PrintWarning("Cannot find Layer Botmask.\n")
    #    return -1
    if not pcaplib.get_rt_layer_of_guide_pin():
        App.Console.PrintWarning("Cannot find Layer Guide_Pin.\n")
        return -1
    if not pcaplib.get_pcap_layer_of_open():
        App.Console.PrintWarning("Cannot find Layer Open.\n")
        return -1
    if not pcaplib.get_rt_layer_of_router_edge():
        App.Console.PrintWarning("Cannot find Layer Router_Edge.\n")
        return -1

    layer_selected_list = []
    for layer_label in pcaplib.get_rt_layers().split(','):
        #print(layer_label)
        layer_selected_list.append(Layer(layer_label))

    # Sorted in layer.depth
    layer_selected_list.sort(key=lambda layer: layer.depth, reverse=True)

    # Initialize layer botsilk, botpaste, fixedPin, supportPin, supportBlock, stopBlock, pressfit and Check their Group() 
    # Create botsilk Layer
    botsilk = Layer(pcaplib.get_pcap_layer_of_botsilk(), is_layer_silk=True)
    botsilk.createFace(overlap_check=False)
    if botsilk.getLayer().Group == []:
        App.Console.PrintWarning("Layer Botsilk is empty. Please check the DXF file.\n")
        return -1

    # Create botpaste Layer
    botpaste = Layer(pcaplib.get_pcap_layer_of_botpaste())
    botpaste.createFace(overlap_check=False)
    if botpaste.getLayer().Group == []:
        App.Console.PrintWarning("Layer Botpaste is empty. Please check the DXF file.\n")
        return -1

    # Create guidePin Layer
    guidePin = Layer(pcaplib.get_rt_layer_of_guide_pin())
    guidePin.createFace(overlap_check=False)
    if guidePin.getLayer().Group == []:
        App.Console.PrintWarning("Layer Guide_Pin is empty. Please check the DXF file.\n")
        return -1

    # Create open Layer
    open = Layer(pcaplib.get_pcap_layer_of_open())
    open.createFace(overlap_check=False)
    if open.getLayer().Group == []:
        App.Console.PrintWarning("Layer Open is empty. Please check the DXF file.\n")
        return -1
    
    # Create routerEdge Layer
    routerEdge = specialLayer(pcaplib.get_rt_layer_of_router_edge())
    if routerEdge.getLayer().Group == []:
        App.Console.PrintWarning("Layer Router_Edge is empty. Please check the DXF file.\n")
        return -1
    """ 
    #===================================================
    # Function 1 : Interference check (Grooving)
    #===================================================
    # Create an export_list
    export_list = []

    # Direct Output, since ezlib join directly
    for layer in layer_selected_list:
        export_list.append(layer.getLayer())

    # Add botsilk, botpaste, fixedPin, supportPin, supportBlock, stopBlock, pressfit 
    export_list.append(botsilk.getLayer())
    export_list.append(botpaste.getLayer())
    export_list.append(open.getLayer())
    export_list.append(routerEdge.getLayer())
    export_list.append(guidePin.getLayer())

    # Determine the Range and Create QuadTreeNode
    botsilk_bbox = botsilk.getLayer().Shape.BoundBox
    quad_tree = QuadTree(botsilk_bbox.XMin, botsilk_bbox.YMin, botsilk_bbox.XMax, botsilk_bbox.YMax)

    # Insert Node in quad_tree (botsilk)
    for wire, face, label in zip(botsilk.wire_list, botsilk.face_list, botsilk.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all points' Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Insert Node in quad_tree (botpaste)
    for wire, face, label in zip(botpaste.wire_list, botpaste.face_list, botpaste.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Start to detect
    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    point_list = checkForProblem(layer_selected_list, quad_tree, dr)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_problem = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem')
    layer_problem.Group = problem_list
    layer_problem.Label = "[ERROR]Interference Within {}mm".format(dr)
    export_list.append(layer_problem)

    # New function: query for quad_tree to find point.check is False
    not_check_list = query_not_checked(quad_tree)
    problem_list = []
    for point in not_check_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem_interference
    layer_problem_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_Interference')
    layer_problem_interference.Group = problem_list
    layer_problem_interference.Label = "[ERROR]Interference without Grooving".format(dr)
    export_list.append(layer_problem_interference)

    # del quad_tree
    del quad_tree
    """

    #===================================================
    # Function 2: Get Router_Edge and Check Open_Hole Length and Width
    #===================================================
    routerEdge_bbox = findBoundBox(routerEdge.wire_list)
    # Create quadtree_rtEdge
    quadtree_rtEdge = QuadTree(routerEdge_bbox.XMin, routerEdge_bbox.YMin, routerEdge_bbox.XMax, routerEdge_bbox.YMax)
    rtEdge_Point = [Point(w) for w in routerEdge.wire_list]
    #print(len(rtEdge_Point))

    pi = 3.1415926535900773
    for pt in rtEdge_Point:
        # check = True stands for not half-circle
        w = pt.wire
        if len(w.Edges) > 1:
            pt.check = True
            continue
        e = w.Edges[0]
        if not e.Curve.TypeId == "Part::GeomCircle":
            pt.check = True
            continue
        th1, th2 = e.ParameterRange

        if abs(th1) < 0.005 and abs(th2 - pi) < 0.005: #half circle
            quadtree_rtEdge.insert(pt)
        else:
            pt.check = True

    # Find each open area
    rtopen_list = []
    problem_rt_width_sh_list = []
    problem_rt_addLen_sh_list = []
    for wire in open.wire_list:
        rtopen = RTOpen(wire)
        rtEdge_pair = []
        rtEdges_Open = query_range(quadtree_rtEdge, wire.BoundBox) #list of Point(edge)
        rtEdges_Open.sort(key=lambda pt : (pt.wire.Edges[0].Curve.Center.x, pt.wire.Edges[0].Curve.Center.y))

        items = len(rtEdges_Open)
        for idx in range(items):
            pt_0 = rtEdges_Open[idx]
            if pt_0.check: #not half circle
                continue

            pt_1 = rtEdges_Open[idx+1]
            e0 = pt_0.wire.Edges[0]
            e1 = pt_1.wire.Edges[0]
            c0 = e0.Curve.Center
            c1 = e1.Curve.Center
            pt_0.check = True
            pt_1.check = True

            if items == 2:
                rtEdge_pair.append(PairedEdge(e0, e1))
            # I Need 'Next' Pair's First point
            elif idx+2 <= items-1:
                next_pt_0 = rtEdges_Open[idx+2]
                next_c0 = next_pt_0.wire.Edges[0].Curve.Center
                # c0, next_c0 is closer than c1, next_c0
                if (c0- next_c0).dot(c0- next_c0) < (c1- next_c0).dot(c1- next_c0): 
                    rtEdge_pair.append(PairedEdge(e1, e0))
                else:
                    rtEdge_pair.append(PairedEdge(e0, e1))
            elif rtEdge_pair:
                # c0, pre_c1 is closer than c1, pre_c1
                pre_c1 = rtEdge_pair[-1].C2
                if (c0- pre_c1).dot(c0- pre_c1) < (c1- pre_c1).dot(c1- pre_c1): 
                    rtEdge_pair.append(PairedEdge(e0, e1))
                else:
                    rtEdge_pair.append(PairedEdge(e1, e0))

        rtopen.set_rtEdge_pair(rtEdge_pair)
        # Check rtopen width
        para_list = rtopen.find_pair_paralines()
        for l1, l2 in para_list:
            l_tan = l1.tangentAt(0)
            # l1, l2 is horizontal
            if abs(l_tan.dot(App.Vector(0.0, 1.0, 0.0))) < epsilon: # h_lines
                rt_w = l2.Vertexes[0].Point.y - l1.Vertexes[0].Point.y
                if rt_w < rtHoleWidth:
                    # Draw lines in Layer 
                    if l1.Length < l2.Length:
                        shorter = l1
                    else:
                        shorter = l2
                    start = App.Vector(shorter.CenterOfMass.x, l1.Vertexes[0].Point.y, 0)
                    end = App.Vector(start.x, l2.Vertexes[0].Point.y, 0)
                    problem_rt_width_sh_list.append(Part.makeLine(start, end))
            # l1, l2 is vertical
            else:
                rt_w = l2.Vertexes[0].Point.x - l1.Vertexes[0].Point.x
                if rt_w < rtHoleWidth:
                    # Draw lines in Layer 
                    if l1.Length < l2.Length:
                        shorter = l1
                    else:
                        shorter = l2
                    start = App.Vector(l1.Vertexes[0].Point.x, shorter.CenterOfMass.y, 0)
                    end = App.Vector(l2.Vertexes[1].Point.x, start.y, 0)
                    problem_rt_width_sh_list.append(Part.makeLine(start, end))
        
        # Check rtopen addLen
        rtopen_bbox = wire.BoundBox
        first_edges = rtopen.rtEdge_pair[0]
        last_edges = rtopen.rtEdge_pair[-1]
        # Check rtopen head
        if first_edges.is_horizontal():
            rt_addl = first_edges.C1.x - rtopen_bbox.XMin
            if rt_addl < rtHoleAddLen:
                start = first_edges.C1
                end = start + rt_addl * (-first_edges.C12_udir)
                problem_rt_addLen_sh_list.append(Part.makeLine(start, end))
        else: #Vertical!!
            if first_edges.C12_udir.y > 0: # upward
                rt_addl = first_edges.C1.y - rtopen_bbox.YMin
            else:
                rt_addl = rtopen_bbox.YMax - first_edges.C1.y 

            if rt_addl < rtHoleAddLen:
                start = first_edges.C1
                end = start + rt_addl * (-first_edges.C12_udir)
                problem_rt_addLen_sh_list.append(Part.makeLine(start, end))

        # Check rtopen tail
        if last_edges.is_horizontal():
            rt_addl = rtopen_bbox.XMax - last_edges.C2.x 
            if rt_addl < rtHoleAddLen:
                start = last_edges.C2
                end = start + rt_addl * last_edges.C12_udir
                problem_rt_addLen_sh_list.append(Part.makeLine(start, end))
        else:
            if last_edges.C12_udir.y < 0:
                rt_addl = last_edges.C2.y - rtopen_bbox.YMin
            else:
                rt_addl = rtopen_bbox.YMax - last_edges.C2.y

            if rt_addl < rtHoleAddLen:
                start = last_edges.C2
                end = start + rt_addl * last_edges.C12_udir
                problem_rt_addLen_sh_list.append(Part.makeLine(start, end))

        rtopen_list.append(rtopen)

    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    problem_rt_width_list = []
    for sh in problem_rt_width_sh_list:
        problem = formObject(sh)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_rt_width_list.append(problem)

    # Create layer_rt_width
    layer_rt_width = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_rt_width')
    layer_rt_width.Group = problem_rt_width_list
    layer_rt_width.Label = "[ERROR] Router Open Hole Width less than {}mm".format(rtHoleWidth)
    #export_list.append(layer_rt_width)
        
    problem_rt_addLen_list = []
    for sh in problem_rt_addLen_sh_list:
        problem = formObject(sh)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_rt_addLen_list.append(problem)

    # Create layer_rt_addLen
    layer_rt_addLen = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_rt_addLen')
    layer_rt_addLen.Group = problem_rt_addLen_list
    layer_rt_addLen.Label = "[ERROR] Router Open Hole addLen less than {}mm".format(rtHoleAddLen)
    
    #===================================================
    # Function 3: Guide Pin Related
    #===================================================
    # Obtain Board_Face list
    board_count = int(4) # Trough pcaplib
    botpaste.wire_list.sort(key=lambda w : w.Area, reverse = True)
    board_wire = botpaste[:board_count]

    # Obtain Layer guidePin and create GPIN object
    guidePin_list = [GPin(wire) for wire in guidePin.wire_list]
    checkDist = 0.2

    for gp in guidePin_list:
        if gp.isCircle:
            continue
        # Try dir1, dir2 perpendicular to C12_udir
        dir1 = -gp.C12_udir.y + gp.C12_udir.x
        dir2 = -gp.C12_udir.y + gp.C12_udir.x
        test_st = (gp.C1 + gp.C2)/2
            
        # Check dir1
        test_point = test_st + checkDist * dir1
        for bd in board_wire:
            face_bd = Part.Face(bd)
            if face_bd.isInside(test_point):
                gp.set_pcb_dir1(dir1)
                break

        # Check dir2
        test_point = test_st + checkDist * dir2
        for bd in board_wire:
            face_bd = Part.Face(bd)
            if face_bd.isInside(test_point):
                gp.set_pcb_dir2(dir2)
                break
        


        
        

        

    """    
    # Get wires_stopBlock
    wires_stopBlock = findStopBlockWire(stopBlock)

    searchDist = blockKeepDist + 15.0
    do_not_keep_stopBlock = []
    # blockKeepDist
    for stopB in wires_stopBlock:
        stopB_face = Part.Face(stopB)
        stopB_bbox = stopB.BoundBox
        search_bbox = App.BoundBox(stopB_bbox.getPoint(0)-App.Vector(searchDist,searchDist,0), stopB_bbox.getPoint(2)+ App.Vector(searchDist,searchDist,0))
        included = query_range(quad_tree, search_bbox)
        for point in included:
            # Set all circle check == True, Hole or VIA Hole
            if len(point.wire.Edges) == 1 or len(point.wire.Edges) == 2:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                continue
            # Distance Check
            if minDist(stopB_face, point.wire) < blockKeepDist:
                shade_area = formObject(point.face, point.label)
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
                do_not_keep_stopBlock.append(shade_area)
   
    # Create layer_keep_dist_stopBlock
    layer_keep_dist_stopBlock = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_keep_dist_stopBlock')
    layer_keep_dist_stopBlock.Group = do_not_keep_stopBlock
    layer_keep_dist_stopBlock.Label = "[ERROR]Not keep enough dist {} mm with the stop_block".format(blockKeepDist)
    export_list.append(layer_keep_dist_stopBlock)

    #===================================================
    # Function 3: Keep distance with the Fixed_Pin and Support_Pin
    #===================================================
    # Create a set for pin position
    point_set = set()

    # Obtain the radius of the pin for supportPin Layer
    sp = supportPin.wire_list
    fp = fixedPin.wire_list

    # Get max p_radius
    p_radius = -1
    for p in sp:
        point_set.add((round(p.CenterOfMass.x, 5), round(p.CenterOfMass.y, 5))) # Add to point_set
        if len(p.Edges) == 6:
            p_vert = p.Vertexes[0].Point
            R = (p_vert - p.CenterOfMass).Length
            if R >= p_radius:
                p_radius = R
        elif hasattr(p.Edges[0], "Curve") and hasattr(p.Edges[0].Curve, "Radius"):
            R = p.Edges[0].Curve.Radius
            if R >= p_radius:
                p_radius = R
    #print("R = ", R)
    for p in fp:
        point_set.add((round(p.CenterOfMass.x, 5), round(p.CenterOfMass.y, 5))) # Add to point_set
    
    #print("len(point_set) : ", len(point_set))
    do_not_keep_fixed_support = []
    for p in point_set:
        # Create a circle for every p in point_set
        cen = App.Vector(p[0], p[1], 0)
        circle = Part.Wire(Part.makeCircle(R, cen))
        searchDist = distSupport + 20.0
        search_bbox = App.BoundBox(circle.BoundBox.getPoint(0)- App.Vector(searchDist,searchDist,0), circle.BoundBox.getPoint(2)+ App.Vector(searchDist,searchDist,0))
        included = query_range(quad_tree, search_bbox)
        for point in included:
            # Set all circle check == True, Hole or VIA Hole
            if len(point.wire.Edges) == 1 or len(point.wire.Edges) == 2:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                continue
            # Distance Check
            if minDist(circle, point.wire) < distSupport:
                shade_area = formObject(point.face, point.label)
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
                do_not_keep_fixed_support.append(shade_area)

    # Create layer_keep_dist_stopBlock
    layer_keep_dist_fixed_support = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_keep_dist_fixed_support')
    layer_keep_dist_fixed_support.Group = do_not_keep_fixed_support
    layer_keep_dist_fixed_support.Label = "[ERROR]Not keep enough dist {} mm with the Fixed_Pin and Support_Pin".format(distSupport)
    export_list.append(layer_keep_dist_fixed_support)
    # del quad_tree
    del quad_tree
    #===================================================
    # Function 4: Promise that all pins in Pressfit has grooving and Function 5: Keep Dist. with SupportBlock
    #===================================================
    # Create quad_tree_pressfit
    bbox_pressfit = findBoundBox(pressfit.wire_list)
    quad_tree_pressfit = QuadTree(bbox_pressfit.XMin, bbox_pressfit.YMin, bbox_pressfit.XMax, bbox_pressfit.YMax)
    
    # supportBlock
    bbox_supportBlock = supportBlock.wire_list[0].BoundBox

    # Insert Node in quad_tree (pressfit)
    for wire, face, label in zip(pressfit.wire_list, pressfit.face_list, pressfit.label_list):
        point = Point(wire, face, label)
        if point.face.Area >= area_bound:
            continue
        # Focus only on point on the supportBlock
        if not bbox_supportBlock.isInside(point.wire.CenterOfMass):
            continue
        quad_tree_pressfit.insert(point)
    
    for layer in layer_selected_list:
        layer.createFace(overlap_check=False)
        for l_face in layer.face_list:
            included = query_range(quad_tree_pressfit, l_face.BoundBox)
            for point in included:
                if l_face.isInside(point.wire.CenterOfMass, 0.0, True):
                    point.check = True
    
    # Query for not checked
    not_checked_pressfitPin = query_not_checked(quad_tree_pressfit)
    problem_list = []
    for point in not_checked_pressfitPin:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_pressfit_interference
    layer_pressfit_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'PressfitPin_Interference')
    layer_pressfit_interference.Group = problem_list
    layer_pressfit_interference.Label = "[ERROR]Pressfit Interference without Grooving"
    export_list.append(layer_pressfit_interference)
    
    # Function 5: Promise all pressfit Pins stay on the supportBlock and keep some dist.
    #point_list = checkForProblem(supportBlock, quad_tree_pressfit, sbKeepDist, area_bound)
    point_list = checkForProblem([supportBlock], quad_tree_pressfit, 5, area_bound)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_pressfit_pins_support = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'press_pins_support')
    layer_pressfit_pins_support.Group = problem_list
    layer_pressfit_pins_support.Label = "[ERROR]Pressfit Pins do not keep safe Distance with Support_Block in {}mm".format(sbKeepDist)
    export_list.append(layer_pressfit_pins_support)
    #===================================================
    # Export DWG
    #===================================================
    import importDWG
    importDWG.export(export_list,output_file_path)
    end=time()

    App.Console.PrintMessage("t = {}s\n".format(end- start))
    """

def run_unloader():
    #===================================================
    # Function 1
    #===================================================
    # Set distance and area_bound
    start = time()

    # Assuming filePath is defined earlier
    # importDXF.open(filePath)

    # Get values from pcaplib
    dr = float(pcaplib.get_pcap_dr())

    # Set default values
    area_bound = float(pcaplib.get_pcap_area_bound())

    # Determine the output folder
    filePath = pcaplib.get_pcap_dxf_file_path()
    output_folder = pcaplib.get_pcap_output_folder() or os.path.dirname(os.path.abspath(filePath))

    # Construct the output file path using os.path.join
    output_file_path = os.path.join(output_folder, "final_result.dwg")

    # Initialize Custom Layer Object
    if not pcaplib.get_pcap_dxf_layers():
        App.Console.PrintWarning("Please select the layers and then press the \"Save Setting\" button!\n")
        return -1
    
    if not pcaplib.get_pcap_layer_of_botsilk():
        App.Console.PrintWarning("Cannot find Layer botsilk.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_botpaste():
        App.Console.PrintWarning("Cannot find Layer botpaste.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_botmask():
        App.Console.PrintWarning("Cannot find Layer botmask.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_open():
        App.Console.PrintWarning("Cannot find Layer OPEN.\n")
        return -1
        
    if not pcaplib.get_pcap_layer_of_botmask():
        App.Console.PrintWarning("Cannot find Layer board_pocket.\n")
        return -1

    layer_selected_list = []
    for layer_label in pcaplib.get_pcap_dxf_layers().split(','):
        #print(layer_label)
        layer_selected_list.append(Layer(layer_label))

    # Sorted in layer.depth
    layer_selected_list.sort(key=lambda layer: layer.depth, reverse=True)

    # Create an export_list
    export_list = []

    # Initialize layer botsilk, botmask, OPEN, PCB_2.5 and Check their Group() 
    # Create botsilk Layer
    botsilk = Layer(pcaplib.get_pcap_layer_of_botsilk())
    botsilk.createFace(overlap_check=False)
    if botsilk.getLayer().Group == []:
        App.Console.PrintWarning("Layer botsilk is empty. Please check the DXF file.\n")
        return -1

    # Create botpaste Layer
    botpaste = Layer(pcaplib.get_pcap_layer_of_botpaste())
    botpaste.createFace(overlap_check=False)
    if botpaste.getLayer().Group == []:
        App.Console.PrintWarning("Layer botpaste is empty. Please check the DXF file.\n")
        return -1

    # Create botmask Layer
    botmask = Layer(pcaplib.get_pcap_layer_of_botmask())
    botmask.createFace(overlap_check=False)

    if botmask.getLayer().Group == []:
        App.Console.PrintWarning("Layer botmask is empty. Please check the DXF file.\n")
        return -1

    # Create OPEN Layer
    OPEN = Layer(pcaplib.get_pcap_layer_of_open())
    OPEN.createFace()
    if (OPEN.getLayer().Group == []):
        App.Console.PrintWarning("Layer Open is empty. Please reselect it and play again.\n")
        return -1

    # Create board_pocket Layer
    board_pocket = Layer(pcaplib.get_pcap_layer_of_board_sink())
    board_pocket.createFace(overlap_check=False)
    if board_pocket.getLayer().Group == []:
        App.Console.PrintWarning("Layer Board Sink is empty. Please reselect it and play again.\n")
        return -1

    ## Create layer_export
    #for layer in layer_selected_list:
    #    
    #    #obtain layer property
    #    #line_color
    #    if (layer.getLayer().Group != []):
    #        line_color = layer.getLayer().Group[0].ViewObject.LineColor

    #    # Add Document
    #    new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', layer.label+ '_exp')
    #    export_list.append(new_layer)
    #    new_layer.Label = layer.label+ '_exp'
    #    new_layer.Group = new_layer_wire

    # Direct Output, since ezlib join directly
    for layer in layer_selected_list:
        export_list.append(layer.getLayer())

    # Determine the Range and Create QuadTreeNode
    botsilk_bbox = botsilk.getLayer().Shape.BoundBox
    quad_tree = QuadTree(botsilk_bbox.XMin, botsilk_bbox.YMin, botsilk_bbox.XMax, botsilk_bbox.YMax)

    # Insert Node in quad_tree (botsilk)
    for wire, face, label in zip(botsilk.wire_list, botsilk.face_list, botsilk.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Insert Node in quad_tree (botpaste)
    for wire, face, label in zip(botpaste.wire_list, botpaste.face_list, botpaste.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Start to detect
    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    point_list = checkForProblem(layer_selected_list, quad_tree, dr)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_problem = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem')
    layer_problem.Group = problem_list
    layer_problem.Label = "[ERROR]Interference Within {}mm".format(dr)
    export_list.append(layer_problem)

    # New function: query for quad_tree to find point.check is False
    not_check_list = query_not_checked(quad_tree)
    problem_list = []
    for point in not_check_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem_interference
    layer_problem_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_Interference')
    layer_problem_interference.Group = problem_list
    layer_problem_interference.Label = "[ERROR]Interference without Grooving".format(dr)
    export_list.append(layer_problem_interference)

    # del quad_tree
    del quad_tree
    #===================================================
    # Function 2: Print All Component In Open And THRU
    #===================================================
    ## Get OPEN_color
    #OPEN_color = OPEN.getLayer().Group[0].ViewObject.LineColor

    ## Add Document
    #new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', OPEN.label+ '_exp')
    #export_list.append(new_layer)
    #new_layer.Label = OPEN.label+ '_exp'

    #new_layer_wire=[]
    #for wire, label in zip(OPEN.wire_list, OPEN.label_list):
    #    obj_wire=formObject(wire, label)
    #    obj_wire.ViewObject.LineColor=OPEN_color
    #    new_layer_wire.append(obj_wire)

    #new_layer.Group = new_layer_wire
    #export_list.append(new_layer)

    # Direct Output, since ezlib join directly
    export_list.append(OPEN.getLayer())

    # Determine the Range and Create QuadTreeNode
    botmask_bbox = botmask.getLayer().Shape.BoundBox
    quad_tree_1 = QuadTree(botmask_bbox.XMin, botmask_bbox.YMin, botmask_bbox.XMax, botmask_bbox.YMax)

    # Insert Node in quad_tree (botmask)
    for wire, face, label in zip(botmask.wire_list, botmask.face_list, botmask.label_list):
        quad_tree_1.insert(Point(wire, face, label))

    # Start to Detect
    tolerance = 0.00001
    result_open = []
    for l_face in OPEN.face_list:
        included = query_range(quad_tree_1, l_face.BoundBox)
        for point in included:
            # Already Checked
            if point.check == True:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                point.check = True
                continue
            # Inside Check
            if not l_face.isInside(point.wire.CenterOfMass, 0.0, True):
                continue

            point.check = True
            if len(point.wire.Edges) == 1:
                vec = point.wire.Vertex1.Point- point.wire.CenterOfMass
                r = sqrt(vec.dot(vec))
                c = Part.makeCircle(r, point.wire.CenterOfMass)
                c_wire = Part.Wire(c)
                c_face = Part.Face(c_wire)
                shade_area = formObject(c_face, point.label)
            else:
                shade_area = formObject(point.face, point.label)

            # Distance Check For line_color only
            if minDist(l_face, point.wire) < dr-tolerance:
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
            else:
                shade_area.ViewObject.LineColor = (1.0, 1.0, 1.0)
                #shade_area.ViewObject.ShapeColor = (1.0, 1.0, 1.0)

            result_open.append(shade_area)

    OPEN_component = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'OPEN_component')
    OPEN_component.Group = result_open
    export_list.append(OPEN_component)

    #===================================================
    # Function 3: the dist. between board and board_pocket
    #===================================================
    d_board = float(pcaplib.get_pcap_d_board())
    #board_pocket_color = board_pocket.getLayer().Group[0].ViewObject.LineColor

    ## Add Document
    #new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', board_pocket.label+ '_exp')
    #export_list.append(new_layer)
    #new_layer.Label = board_pocket.label+ '_exp'

    #new_layer_wire=[]
    #for wire, label in zip(board_pocket.wire_list, board_pocket.label_list):
    #    obj_wire=formObject(wire, label)
    #    obj_wire.ViewObject.LineColor=board_pocket_color
    #    new_layer_wire.append(obj_wire)

    #new_layer.Group = new_layer_wire
    export_list.append(board_pocket.getLayor())

    pair_board_objs = []
    board_color = (0.0, 0.0, 1.0)

    fixture_board_too_close = []
    # Create board_outline
    for l_wire in board_pocket.wire_list:
        # Create BoundBox
        boundary = 10
        vert1 = App.Vector(l_wire.CenterOfMass.x, l_wire.CenterOfMass.y, 0)- App.Vector(boundary/2, boundary/2, 0)
        vert2 = App.Vector(l_wire.CenterOfMass.x, l_wire.CenterOfMass.y, 0)+ App.Vector(boundary/2, boundary/2, 0)
        bbox = App.BoundBox(vert1, vert2)
        # Query
        included = query_range(quad_tree_1, bbox)
        board = getBoard(included, area_bound)
        if board:
            show = formObject(board.wire, board.label)
            show.ViewObject.LineColor = board_color
            pair_board_objs.append((l_wire, show))
            for edge in board.wire.Edges:
                fixture_board_too_close.extend(gapCheck(l_wire, edge, d_board))

    # Create layer_Board
    Board = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'board')
    Board.Group = [board_obj for (l_wire, board_obj) in pair_board_objs]
    export_list.append(Board)

    # Change Color
    for m in fixture_board_too_close:
        m.ViewObject.LineColor = error_line_color

    # Create layer_boardGapTooClose
    layer_boardGapTooClose = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_Thru_thickness')
    layer_boardGapTooClose.Group = fixture_board_too_close
    layer_boardGapTooClose.Label = "[ERROR]Fixture Board Gap Less Than {}mm".format(d_board)
    export_list.append(layer_boardGapTooClose)

    del quad_tree_1
    #===================================================
    # Function 4 : Thru Thickness to thin
    #===================================================
    do = float(pcaplib.get_pcap_do())
    slice_len = 2

    # Create quad_tree_2
    quad_tree_2 = QuadTree(botmask_bbox.XMin, botmask_bbox.YMin, botmask_bbox.XMax, botmask_bbox.YMax)

    for i, layer in enumerate(layer_selected_list):
        for j, wire in enumerate(layer.wire_list):
            pts = wire.discretize(int(wire.Length/slice_len)+ 1)
            # insert pts in QuadTree
            for pt in pts[:-1]:
                quad_tree_2.insert(Point2(pt, i, j))

    # Start to Check for wire in OPEN
    open_gap_too_close = []
    for w in OPEN.wire_list:
        check_bbox = App.BoundBox(w.BoundBox.XMin-do, w.BoundBox.YMin-do, 0, w.BoundBox.XMax+do, w.BoundBox.YMax+do, 0)
        check = query_range(quad_tree_2, check_bbox)
        # Obtain check_set
        check_set = set()
        for pt2 in check:
            check_set.add((pt2.layer_idx, pt2.wire_idx))
        # gap check
        for (i, j) in check_set:
            open_gap_too_close.extend(gapCheck(w, layer_selected_list[i].wire_list[j], do))

    # Change Color
    for m in open_gap_too_close:
        m.ViewObject.LineColor = error_line_color

    # Create layer_openGapTooClose
    layer_openGapTooClose = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_Thru_thickness')
    layer_openGapTooClose.Group = open_gap_too_close
    layer_openGapTooClose.Label = "[ERROR]Thru Thickness Less Than {}mm".format(do)
    export_list.append(layer_openGapTooClose)

    #===================================================
    # Function 5 : Check for Connect_Groove
    #===================================================
    dl = float(pcaplib.get_pcap_dl())
    dw = float(pcaplib.get_pcap_dw())

    tangents = [App.Vector(1,0,0), App.Vector(-1,0,0), App.Vector(0,1,0), App.Vector(0,-1,0)]

    func5_result=[]
    for l_wire, board_obj in pair_board_objs:
        idxes, ccw = findGroove(l_wire, tangents)
        L = len(l_wire.Edges)
        edges = l_wire.Edges
        for idx in idxes:
            Vl1 = edges[idx].Vertex2.Point
            Vl2 = edges[(idx+8)%L].Vertex1.Point
            dl_check = Vl1.distanceToPoint(Vl2)
            dw_check = board_obj.Shape.distToShape(edges[(idx+4)%L].Vertex1)[0]
            if dl_check < dl:
                func5_result.append(formObject(Part.makeLine(Vl1, Vl2)))
            if dw_check < dw:
                rot = App.Matrix(0,-1,0,0,1,0,0,0,0,0,1,0,0,0,0,1)
                t = edges[(idx+4)%L].tangentAt(0)
                t = rot.multVec(t)
                Vwmid = (edges[(idx+4)%L].Vertex1.Point+ edges[(idx+4)%L].Vertex2.Point)/2
                Vw2 = Vwmid+ ccw*dw_check*t
                func5_result.append(formObject(Part.makeLine(Vwmid, Vw2)))

    # Change Color
    for m in func5_result:
        m.ViewObject.LineColor = error_line_color

    # Create layer_errorConnectGroove
    layer_errorConnectGroove = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_ConnectGroove')
    layer_errorConnectGroove.Group = func5_result
    layer_errorConnectGroove.Label = "[ERROR]Connect Groove Dimension Violation"
    export_list.append(layer_errorConnectGroove)

    #===================================================
    # Export DWG
    #===================================================
    import importDWG
    importDWG.export(export_list,output_file_path)
    # Reset the parameter PrefPCAPLayers
    pcaplib.set_param("prefPCAPLayers", "")
    end=time()

    App.Console.PrintMessage("t = {}s\n".format(end- start))

def run_wave():
    #===================================================
    # Function 1
    #===================================================
    # Set distance and area_bound
    start = time()

    # Assuming filePath is defined earlier
    # importDXF.open(filePath)

    # Get values from pcaplib
    dr = float(pcaplib.get_pcap_dr())

    # Set default values
    area_bound = float(pcaplib.get_pcap_area_bound())

    # Determine the output folder
    filePath = pcaplib.get_pcap_dxf_file_path()
    output_folder = pcaplib.get_pcap_output_folder() or os.path.dirname(os.path.abspath(filePath))

    # Construct the output file path using os.path.join
    output_file_path = os.path.join(output_folder, "final_result.dwg")

    # Initialize Custom Layer Object
    if not pcaplib.get_pcap_dxf_layers():
        App.Console.PrintWarning("Please select the layers and then press the \"Save Setting\" button!\n")
        return -1
    
    if not pcaplib.get_pcap_layer_of_botsilk():
        App.Console.PrintWarning("Cannot find Layer botsilk.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_botpaste():
        App.Console.PrintWarning("Cannot find Layer botpaste.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_botmask():
        App.Console.PrintWarning("Cannot find Layer botmask.\n")
        return -1

    if not pcaplib.get_pcap_layer_of_open():
        App.Console.PrintWarning("Cannot find Layer OPEN.\n")
        return -1
        
    if not pcaplib.get_pcap_layer_of_board_sink():
        App.Console.PrintWarning("Cannot find Layer board_pocket.\n")
        return -1

    layer_selected_list = []
    for layer_label in pcaplib.get_pcap_dxf_layers().split(','):
        #print(layer_label)
        layer_selected_list.append(Layer(layer_label))

    # Sorted in layer.depth
    layer_selected_list.sort(key=lambda layer: layer.depth, reverse=True)

    # Create an export_list
    export_list = []

    # Initialize layer botsilk, botmask, OPEN, PCB_2.5 and Check their Group() 
    # Create botsilk Layer
    botsilk = Layer(pcaplib.get_pcap_layer_of_botsilk(), is_layer_silk=True)
    botsilk.createFace(overlap_check=False)
    if botsilk.getLayer().Group == []:
        App.Console.PrintWarning("Layer botsilk is empty. Please check the DXF file.\n")
        return -1

    # Create botpaste Layer
    botpaste = Layer(pcaplib.get_pcap_layer_of_botpaste())
    botpaste.createFace(overlap_check=False)
    if botpaste.getLayer().Group == []:
        App.Console.PrintWarning("Layer botpaste is empty. Please check the DXF file.\n")
        return -1

    # Create botmask Layer
    botmask = Layer(pcaplib.get_pcap_layer_of_botmask())
    botmask.createFace(overlap_check=False)

    if botmask.getLayer().Group == []:
        App.Console.PrintWarning("Layer botmask is empty. Please check the DXF file.\n")
        return -1

    # Create OPEN Layer
    OPEN = Layer(pcaplib.get_pcap_layer_of_open())
    OPEN.createFace()
    if (OPEN.getLayer().Group == []):
        App.Console.PrintWarning("Layer Open is empty. Please reselect it and play again.\n")
        return -1

    # Create board_pocket Layer
    board_pocket = Layer(pcaplib.get_pcap_layer_of_board_sink())
    board_pocket.createFace(overlap_check=False)
    if board_pocket.getLayer().Group == []:
        App.Console.PrintWarning("Layer Board Sink is empty. Please reselect it and play again.\n")
        return -1

    ## Create layer_export
    #for layer in layer_selected_list:
    #    
    #    #obtain layer property
    #    #line_color
    #    if (layer.getLayer().Group != []):
    #        line_color = layer.getLayer().Group[0].ViewObject.LineColor

    #    # Add Document
    #    new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', layer.label+ '_exp')
    #    export_list.append(new_layer)
    #    new_layer.Label = layer.label+ '_exp'
    #    new_layer.Group = new_layer_wire

    # Direct Output, since ezlib join directly
    for layer in layer_selected_list:
        export_list.append(layer.getLayer())

    # Determine the Range and Create QuadTreeNode
    botsilk_bbox = botsilk.getLayer().Shape.BoundBox
    quad_tree = QuadTree(botsilk_bbox.XMin, botsilk_bbox.YMin, botsilk_bbox.XMax, botsilk_bbox.YMax)

    # Insert Node in quad_tree (botsilk)
    for wire, face, label in zip(botsilk.wire_list, botsilk.face_list, botsilk.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Insert Node in quad_tree (botpaste)
    for wire, face, label in zip(botpaste.wire_list, botpaste.face_list, botpaste.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Start to detect
    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    point_list = checkForProblem(layer_selected_list, quad_tree, dr)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_problem = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem')
    layer_problem.Group = problem_list
    layer_problem.Label = "[ERROR]Interference Within {}mm".format(dr)
    export_list.append(layer_problem)

    # New function: query for quad_tree to find point.check is False
    not_check_list = query_not_checked(quad_tree)
    problem_list = []
    for point in not_check_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem_interference
    layer_problem_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_Interference')
    layer_problem_interference.Group = problem_list
    layer_problem_interference.Label = "[ERROR]Interference without Grooving".format(dr)
    export_list.append(layer_problem_interference)

    # del quad_tree
    del quad_tree
    #===================================================
    # Function 2: Print All Component In Open And THRU
    #===================================================
    ## Get OPEN_color
    #OPEN_color = OPEN.getLayer().Group[0].ViewObject.LineColor

    ## Add Document
    #new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', OPEN.label+ '_exp')
    #export_list.append(new_layer)
    #new_layer.Label = OPEN.label+ '_exp'

    #new_layer_wire=[]
    #for wire, label in zip(OPEN.wire_list, OPEN.label_list):
    #    obj_wire=formObject(wire, label)
    #    obj_wire.ViewObject.LineColor=OPEN_color
    #    new_layer_wire.append(obj_wire)

    #new_layer.Group = new_layer_wire
    #export_list.append(new_layer)

    # Direct Output, since ezlib join directly
    export_list.append(OPEN.getLayer())

    # Determine the Range and Create QuadTreeNode
    botmask_bbox = botmask.getLayer().Shape.BoundBox
    quad_tree_1 = QuadTree(botmask_bbox.XMin, botmask_bbox.YMin, botmask_bbox.XMax, botmask_bbox.YMax)

    # Insert Node in quad_tree (botmask)
    for wire, face, label in zip(botmask.wire_list, botmask.face_list, botmask.label_list):
        quad_tree_1.insert(Point(wire, face, label))

    # Start to Detect
    tolerance = 0.00001
    result_open = []
    for l_face in OPEN.face_list:
        included = query_range(quad_tree_1, l_face.BoundBox)
        for point in included:
            # Already Checked
            if point.check == True:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                point.check = True
                continue
            # Inside Check
            if not l_face.isInside(point.wire.CenterOfMass, 0.0, True):
                continue

            point.check = True
            if len(point.wire.Edges) == 1:
                vec = point.wire.Vertex1.Point- point.wire.CenterOfMass
                r = sqrt(vec.dot(vec))
                c = Part.makeCircle(r, point.wire.CenterOfMass)
                c_wire = Part.Wire(c)
                c_face = Part.Face(c_wire)
                shade_area = formObject(c_face, point.label)
            else:
                shade_area = formObject(point.face, point.label)

            # Distance Check For line_color only
            if minDist(l_face, point.wire) < dr-tolerance:
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
            else:
                shade_area.ViewObject.LineColor = (1.0, 1.0, 1.0)
                #shade_area.ViewObject.ShapeColor = (1.0, 1.0, 1.0)

            result_open.append(shade_area)

    OPEN_component = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'OPEN_component')
    OPEN_component.Group = result_open
    export_list.append(OPEN_component)

    #===================================================
    # Function 3: the dist. between board and board_pocket
    #===================================================
    d_board = float(pcaplib.get_pcap_d_board())
    #board_pocket_color = board_pocket.getLayer().Group[0].ViewObject.LineColor

    ## Add Document
    #new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', board_pocket.label+ '_exp')
    #export_list.append(new_layer)
    #new_layer.Label = board_pocket.label+ '_exp'

    #new_layer_wire=[]
    #for wire, label in zip(board_pocket.wire_list, board_pocket.label_list):
    #    obj_wire=formObject(wire, label)
    #    obj_wire.ViewObject.LineColor=board_pocket_color
    #    new_layer_wire.append(obj_wire)

    #new_layer.Group = new_layer_wire
    export_list.append(board_pocket.getLayer())

    pair_board_objs = []
    board_color = (0.0, 0.0, 1.0)

    fixture_board_too_close = []
    # Create board_outline
    for l_wire in board_pocket.wire_list:
        # Create BoundBox
        boundary = 10
        vert1 = App.Vector(l_wire.CenterOfMass.x, l_wire.CenterOfMass.y, 0)- App.Vector(boundary/2, boundary/2, 0)
        vert2 = App.Vector(l_wire.CenterOfMass.x, l_wire.CenterOfMass.y, 0)+ App.Vector(boundary/2, boundary/2, 0)
        bbox = App.BoundBox(vert1, vert2)
        # Query
        included = query_range(quad_tree_1, bbox)
        board = getBoard(included, area_bound)
        if board:
            show = formObject(board.wire, board.label)
            show.ViewObject.LineColor = board_color
            pair_board_objs.append((l_wire, show))
            for edge in board.wire.Edges:
                fixture_board_too_close.extend(gapCheck(l_wire, edge, d_board))

    # Create layer_Board
    Board = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'board')
    Board.Group = [board_obj for (l_wire, board_obj) in pair_board_objs]
    export_list.append(Board)

    # Change Color
    for m in fixture_board_too_close:
        m.ViewObject.LineColor = error_line_color

    # Create layer_boardGapTooClose
    layer_boardGapTooClose = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_Thru_thickness')
    layer_boardGapTooClose.Group = fixture_board_too_close
    layer_boardGapTooClose.Label = "[ERROR]Fixture Board Gap Less Than {}mm".format(d_board)
    export_list.append(layer_boardGapTooClose)

    del quad_tree_1
    #===================================================
    # Function 4 : Thru Thickness to thin
    #===================================================
    do = float(pcaplib.get_pcap_do())
    slice_len = 2

    # Create quad_tree_2
    quad_tree_2 = QuadTree(botmask_bbox.XMin, botmask_bbox.YMin, botmask_bbox.XMax, botmask_bbox.YMax)

    for i, layer in enumerate(layer_selected_list):
        for j, wire in enumerate(layer.wire_list):
            pts = wire.discretize(int(wire.Length/slice_len)+ 1)
            # insert pts in QuadTree
            for pt in pts[:-1]:
                quad_tree_2.insert(Point2(pt, i, j))

    # Start to Check for wire in OPEN
    open_gap_too_close = []
    for w in OPEN.wire_list:
        check_bbox = App.BoundBox(w.BoundBox.XMin-do, w.BoundBox.YMin-do, 0, w.BoundBox.XMax+do, w.BoundBox.YMax+do, 0)
        check = query_range(quad_tree_2, check_bbox)
        # Obtain check_set
        check_set = set()
        for pt2 in check:
            check_set.add((pt2.layer_idx, pt2.wire_idx))
        # gap check
        for (i, j) in check_set:
            open_gap_too_close.extend(gapCheck(w, layer_selected_list[i].wire_list[j], do))

    # Change Color
    for m in open_gap_too_close:
        m.ViewObject.LineColor = error_line_color

    # Create layer_openGapTooClose
    layer_openGapTooClose = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_Thru_thickness')
    layer_openGapTooClose.Group = open_gap_too_close
    layer_openGapTooClose.Label = "[ERROR]Thru Thickness Less Than {}mm".format(do)
    export_list.append(layer_openGapTooClose)

    #===================================================
    # Function 5 : Check for Connect_Groove
    #===================================================
    dl = float(pcaplib.get_pcap_dl())
    dw = float(pcaplib.get_pcap_dw())

    tangents = [App.Vector(1,0,0), App.Vector(-1,0,0), App.Vector(0,1,0), App.Vector(0,-1,0)]

    func5_result=[]
    for l_wire, board_obj in pair_board_objs:
        idxes, ccw = findGroove(l_wire, tangents)
        L = len(l_wire.Edges)
        edges = l_wire.Edges
        for idx in idxes:
            Vl1 = edges[idx].Vertex2.Point
            Vl2 = edges[(idx+8)%L].Vertex1.Point
            dl_check = Vl1.distanceToPoint(Vl2)
            dw_check = board_obj.Shape.distToShape(edges[(idx+4)%L].Vertex1)[0]
            if dl_check < dl:
                func5_result.append(formObject(Part.makeLine(Vl1, Vl2)))
            if dw_check < dw:
                rot = App.Matrix(0,-1,0,0,1,0,0,0,0,0,1,0,0,0,0,1)
                t = edges[(idx+4)%L].tangentAt(0)
                t = rot.multVec(t)
                Vwmid = (edges[(idx+4)%L].Vertex1.Point+ edges[(idx+4)%L].Vertex2.Point)/2
                Vw2 = Vwmid+ ccw*dw_check*t
                func5_result.append(formObject(Part.makeLine(Vwmid, Vw2)))

    # Change Color
    for m in func5_result:
        m.ViewObject.LineColor = error_line_color

    # Create layer_errorConnectGroove
    layer_errorConnectGroove = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'ERROR_ConnectGroove')
    layer_errorConnectGroove.Group = func5_result
    layer_errorConnectGroove.Label = "[ERROR]Connect Groove Dimension Violation"
    export_list.append(layer_errorConnectGroove)

    #===================================================
    # Export DWG
    #===================================================
    import importDWG
    importDWG.export(export_list,output_file_path)
    # Reset the parameter PrefPCAPLayers
    #pcaplib.set_param("prefPCAPLayers", "")
    end=time()

    App.Console.PrintMessage("t = {}s\n".format(end- start))

def run_press():
    start = time()

    # Determine the output folder
    filePath = pcaplib.get_pcap_dxf_file_path()
    output_folder = pcaplib.get_pcap_output_folder() or os.path.dirname(os.path.abspath(filePath))

    # Construct the output file path using os.path.join
    output_file_path = os.path.join(output_folder, "final_result.dwg")

    # Get values from pcaplib
    dr = float(pcaplib.get_pcap_dr())
    area_bound = float(pcaplib.get_pcap_area_bound())
    sbKeepDist = float(pcaplib.get_press_sb_keep_dist())
    blockKeepDist = float(pcaplib.get_press_block_keep_dist())
    distSupport = float(pcaplib.get_press_dist_support())

    # Initialize Custom Layer Object
    if not pcaplib.get_press_layers():
        App.Console.PrintWarning("Please select the layers and then press the \"Save Setting\" button!\n")
        return -1
    if not pcaplib.get_pcap_layer_of_botsilk():
        App.Console.PrintWarning("Cannot find Layer Botsilk.\n")
        return -1
    if not pcaplib.get_pcap_layer_of_botpaste():
        App.Console.PrintWarning("Cannot find Layer Botpaste.\n")
        return -1
    #if not pcaplib.get_pcap_layer_of_botmask():
    #    App.Console.PrintWarning("Cannot find Layer Botmask.\n")
    #    return -1
    if not pcaplib.get_press_layer_of_fixed_pin():
        App.Console.PrintWarning("Cannot find Layer Fixed_Pin.\n")
        return -1
    if not pcaplib.get_press_layer_of_support_pin():
        App.Console.PrintWarning("Cannot find Layer Supprot_Pin.\n")
        return -1
    if not pcaplib.get_press_layer_of_stop_block():
        App.Console.PrintWarning("Cannot find Layer Stop_Block.\n")
        return -1
    if not pcaplib.get_press_layer_of_pressfit():
        App.Console.PrintWarning("Cannot find Layer Pressfit.\n")
        return -1

    layer_selected_list = []
    for layer_label in pcaplib.get_press_layers().split(','):
        #print(layer_label)
        layer_selected_list.append(Layer(layer_label))

    # Sorted in layer.depth
    layer_selected_list.sort(key=lambda layer: layer.depth, reverse=True)

    # Initialize layer botsilk, botpaste, fixedPin, supportPin, supportBlock, stopBlock, pressfit and Check their Group() 
    # Create botsilk Layer
    botsilk = Layer(pcaplib.get_pcap_layer_of_botsilk(), is_layer_silk=True)
    botsilk.createFace(overlap_check=False)
    if botsilk.getLayer().Group == []:
        App.Console.PrintWarning("Layer Botsilk is empty. Please check the DXF file.\n")
        return -1

    # Create botpaste Layer
    botpaste = Layer(pcaplib.get_pcap_layer_of_botpaste())
    botpaste.createFace(overlap_check=False)
    if botpaste.getLayer().Group == []:
        App.Console.PrintWarning("Layer Botpaste is empty. Please check the DXF file.\n")
        return -1

    # Create fixedPin Layer
    fixedPin = Layer(pcaplib.get_press_layer_of_fixed_pin())
    fixedPin.createFace(overlap_check=False)
    if fixedPin.getLayer().Group == []:
        App.Console.PrintWarning("Layer Fixed_Pin is empty. Please check the DXF file.\n")
        return -1

    # Create supportPin Layer
    supportPin = Layer(pcaplib.get_press_layer_of_support_pin())
    supportPin.createFace(overlap_check=False)
    if supportPin.getLayer().Group == []:
        App.Console.PrintWarning("Layer Support_Pin is empty. Please check the DXF file.\n")
        return -1
    
    # Create supportBlock Layer
    supportBlock = Layer(pcaplib.get_press_layer_of_support_block())
    supportBlock.createFace(overlap_check=False)
    if supportBlock.getLayer().Group == []:
        App.Console.PrintWarning("Layer Support_Block is empty. Please check the DXF file.\n")
        return -1
    
    # Create stopBlock Layer
    stopBlock = Layer(pcaplib.get_press_layer_of_stop_block())
    stopBlock.createFace(overlap_check=False)
    if stopBlock.getLayer().Group == []:
        App.Console.PrintWarning("Layer Stop_Block is empty. Please check the DXF file.\n")
        return -1

    # Create pressfit Layer
    pressfit = Layer(pcaplib.get_press_layer_of_pressfit())
    pressfit.createFace(overlap_check=False)
    if pressfit.getLayer().Group == []:
        App.Console.PrintWarning("Layer Pressfit is empty. Please check the DXF file.\n")
        return -1
    #===================================================
    # Function 1 : Interference check (Grooving)
    #===================================================
    # Create an export_list
    export_list = []

    # Direct Output, since ezlib join directly
    for layer in layer_selected_list:
        export_list.append(layer.getLayer())

    # Add botsilk, botpaste, fixedPin, supportPin, supportBlock, stopBlock, pressfit 
    export_list.append(botsilk.getLayer())
    export_list.append(botpaste.getLayer())
    export_list.append(fixedPin.getLayer())
    export_list.append(supportPin.getLayer())
    export_list.append(supportBlock.getLayer())
    export_list.append(stopBlock.getLayer())
    export_list.append(pressfit.getLayer())

    # Determine the Range and Create QuadTreeNode
    botsilk_bbox = botsilk.getLayer().Shape.BoundBox
    quad_tree = QuadTree(botsilk_bbox.XMin, botsilk_bbox.YMin, botsilk_bbox.XMax, botsilk_bbox.YMax)

    # wire supportBlock
    wire_supportBlock = supportBlock.wire_list[0]

    # Insert Node in quad_tree (botsilk)
    for wire, face, label in zip(botsilk.wire_list, botsilk.face_list, botsilk.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all points' Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Insert Node in quad_tree (botpaste)
    for wire, face, label in zip(botpaste.wire_list, botpaste.face_list, botpaste.label_list):
        point = Point(wire, face, label)
        # Set all circle check == True
        if len(point.wire.Edges) == 1:
                point.check = True
        # Set all point's Area >= area_bound check == True
        if point.face.Area >= area_bound:
            point.check = True
        quad_tree.insert(point)

    # Start to detect
    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    point_list = checkForProblem(layer_selected_list, quad_tree, dr)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_problem = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem')
    layer_problem.Group = problem_list
    layer_problem.Label = "[ERROR]Interference Within {}mm".format(dr)
    export_list.append(layer_problem)

    # Query for supportBlock BoundBox to find point.check is False
    included_point = query_range(quad_tree, wire_supportBlock.BoundBox)
    not_check_list = []
    for pt in included_point:
        if not pt.check:
            not_check_list.append(pt)
    problem_list = []
    for point in not_check_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem_interference
    layer_problem_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_Interference')
    layer_problem_interference.Group = problem_list
    layer_problem_interference.Label = "[ERROR]Interference without Grooving"
    export_list.append(layer_problem_interference)

    #===================================================
    # Function 2: Keep distance with the Stop_Block
    #===================================================
    # Set all points in quad_tree False in order to analyze
    initialize_tree(quad_tree)

    # Get wires_stopBlock
    wires_stopBlock = findStopBlockWire(stopBlock)

    searchDist = blockKeepDist + 20.0
    do_not_keep_stopBlock = []
    # blockKeepDist
    for stopB in wires_stopBlock:
        stopB_face = Part.Face(stopB)
        stopB_bbox = stopB.BoundBox
        search_bbox = App.BoundBox(stopB_bbox.getPoint(0)-App.Vector(searchDist,searchDist,0), stopB_bbox.getPoint(2)+ App.Vector(searchDist,searchDist,0))
        included = query_range(quad_tree, search_bbox)
        for point in included:
            # Set all circle check == True, Hole or VIA Hole
            if len(point.wire.Edges) == 1 or len(point.wire.Edges) == 2:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                continue
            # Distance Check
            if minDist(stopB_face, point.wire) < blockKeepDist:
                shade_area = formObject(point.face, point.label)
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
                do_not_keep_stopBlock.append(shade_area)
   
    # Create layer_keep_dist_stopBlock
    layer_keep_dist_stopBlock = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_keep_dist_stopBlock')
    layer_keep_dist_stopBlock.Group = do_not_keep_stopBlock
    layer_keep_dist_stopBlock.Label = "[ERROR]Not keep enough dist {} mm with the stop_block".format(blockKeepDist)
    export_list.append(layer_keep_dist_stopBlock)

    #===================================================
    # Function 3: Keep distance with the Fixed_Pin and Support_Pin
    #===================================================
    # Create a set for pin position
    point_set = set()

    # Obtain the radius of the pin for supportPin Layer
    sp = supportPin.wire_list
    fp = fixedPin.wire_list

    # Get max p_radius
    p_radius = -1
    for p in sp:
        point_set.add((round(p.CenterOfMass.x, 5), round(p.CenterOfMass.y, 5))) # Add to point_set
        if len(p.Edges) == 6:
            p_vert = p.Vertexes[0].Point
            R = (p_vert - p.CenterOfMass).Length
            if R >= p_radius:
                p_radius = R
        elif hasattr(p.Edges[0], "Curve") and hasattr(p.Edges[0].Curve, "Radius"):
            R = p.Edges[0].Curve.Radius
            if R >= p_radius:
                p_radius = R
    #print("R = ", R)
    for p in fp:
        point_set.add((round(p.CenterOfMass.x, 5), round(p.CenterOfMass.y, 5))) # Add to point_set
    
    #print("len(point_set) : ", len(point_set))
    do_not_keep_fixed_support = []
    for p in point_set:
        # Create a circle for every p in point_set
        cen = App.Vector(p[0], p[1], 0)
        circle = Part.Wire(Part.makeCircle(R, cen))
        searchDist = distSupport + 15.0
        search_bbox = App.BoundBox(circle.BoundBox.getPoint(0)- App.Vector(searchDist,searchDist,0), circle.BoundBox.getPoint(2)+ App.Vector(searchDist,searchDist,0))
        included = query_range(quad_tree, search_bbox)
        for point in included:
            # Set all circle check == True, Hole or VIA Hole
            if len(point.wire.Edges) == 1 or len(point.wire.Edges) == 2:
                continue
            # Area Check
            if point.face.Area >= area_bound:
                continue
            # Distance Check
            if minDist(circle, point.wire) < distSupport:
                shade_area = formObject(point.face, point.label)
                shade_area.ViewObject.LineColor = error_line_color
                shade_area.ViewObject.ShapeColor = error_shape_color
                do_not_keep_fixed_support.append(shade_area)

    # Create layer_keep_dist_stopBlock
    layer_keep_dist_fixed_support = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'Problem_keep_dist_fixed_support')
    layer_keep_dist_fixed_support.Group = do_not_keep_fixed_support
    layer_keep_dist_fixed_support.Label = "[ERROR]Not keep enough dist {} mm with the Fixed_Pin and Support_Pin".format(distSupport)
    export_list.append(layer_keep_dist_fixed_support)
    # del quad_tree
    del quad_tree
    #===================================================
    # Function 4: Promise that all pins in Pressfit has grooving and Function 5: Keep Dist. with SupportBlock
    #===================================================
    # Create quad_tree_pressfit
    bbox_pressfit = findBoundBox(pressfit.wire_list)
    quad_tree_pressfit = QuadTree(bbox_pressfit.XMin, bbox_pressfit.YMin, bbox_pressfit.XMax, bbox_pressfit.YMax)
    
    # supportBlock
    bbox_supportBlock = supportBlock.wire_list[0].BoundBox

    # Insert Node in quad_tree (pressfit)
    for wire, face, label in zip(pressfit.wire_list, pressfit.face_list, pressfit.label_list):
        point = Point(wire, face, label)
        if point.face.Area >= area_bound:
            continue
        # Focus only on point on the supportBlock
        if not bbox_supportBlock.isInside(point.wire.CenterOfMass):
            continue
        quad_tree_pressfit.insert(point)
    
    for layer in layer_selected_list:
        layer.createFace(overlap_check=False)
        for l_face in layer.face_list:
            included = query_range(quad_tree_pressfit, l_face.BoundBox)
            for point in included:
                if l_face.isInside(point.wire.CenterOfMass, 0.0, True):
                    point.check = True
    
    # Query for not checked
    not_checked_pressfitPin = query_not_checked(quad_tree_pressfit)
    problem_list = []
    for point in not_checked_pressfitPin:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_pressfit_interference
    layer_pressfit_interference = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'PressfitPin_Interference')
    layer_pressfit_interference.Group = problem_list
    layer_pressfit_interference.Label = "[ERROR]Pressfit Interference without Grooving"
    export_list.append(layer_pressfit_interference)
    
    # Function 5: Promise all pressfit Pins stay on the supportBlock and keep some dist.
    point_list = checkForProblem([supportBlock], quad_tree_pressfit, sbKeepDist, area_bound)

    problem_list = []
    for point in point_list:
        problem = formObject(point.face, point.label)
        problem.ViewObject.LineColor = error_line_color
        problem.ViewObject.ShapeColor = error_shape_color
        problem_list.append(problem)

    # Create layer_problem
    layer_pressfit_pins_support = App.ActiveDocument.addObject('App::DocumentObjectGroup', 'press_pins_support')
    layer_pressfit_pins_support.Group = problem_list
    layer_pressfit_pins_support.Label = "[ERROR]Pressfit Pins do not keep safe Distance with Support_Block in {}mm".format(sbKeepDist)
    export_list.append(layer_pressfit_pins_support)
    #===================================================
    # Export DWG
    #===================================================
    #import importDWG
    #importDWG.export(export_list,output_file_path)
    end=time()

    App.Console.PrintMessage("t = {}s\n".format(end- start))



def listShow(shape_list):
    for sh in shape_list:
        Part.show(sh)
