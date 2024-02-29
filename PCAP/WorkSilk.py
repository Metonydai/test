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

class Point:
    def __init__(self, w, f, l):
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

def featureToClosedWire(grp_list):
    wire_list=[]
    label_list=[]
    for feature in grp_list:
        shape=feature.Shape
        if shape.Wires != []:
            wire = shape.Wires[0]
            if wire.isClosed():
                # Exclusion of "8"
                if len(wire.Vertexes) != len(wire.Edges):
                    continue
                # Exclusion of "0"
                if len(wire.Edges) == 20 and all(map(lambda e: e.Length < 0.1, wire.Edges)):
                    continue

                wire_list.append(wire)
                label_list.append(feature.Label+ "_exp")

        elif shape.isClosed(): # Circle
            wire = Part.Wire(shape.Edges)
            wire_list.append(wire)
            label_list.append(feature.Label+ "_exp")

    return wire_list, label_list

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
    def __init__(self, label):
        #self.name = name
        self.label = label
        self.wire_list, self.label_list = featureToClosedWire(self.getLayer().Group)
        self.face_list = []
        self.depth = self.getDepth()

    def getLayer(self):
        return App.ActiveDocument.getObjectsByLabel(self.label)[0]

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
            return 0


def checkForProblem(layer_selected_list, quad_tree, dr, area_bound):
    result = []
    for layer in layer_selected_list:
        layer.createFace(overlap_check=True)
        for l_face in layer.face_list:
            included = query_range(quad_tree, l_face.BoundBox)
            for point in included:
                # Already Checked
                if point.check == True:
                    continue
                # Point is Circle
                if len(point.wire.Edges) == 1:
                    point.check = True
                    continue
                # Area Check
                if point.face.Area >= area_bound:
                    point.check = True
                    continue
                # Inside Check
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

def run():
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
    layer_selected_list = []
    if pcaplib.get_pcap_dxf_layers() == "":
        App.Console.PrintWarning("Please select the layers and then press the \"Save Setting\" button!\n")
        return -1

    for layer_label in pcaplib.get_pcap_dxf_layers().split(','):
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
        botsilk = Layer(pcaplib.get_pcap_layer_of_botmask())
        botsilk.createFace(overlap_check=False)
        App.Console.PrintWarning("Layer botsilk is empty. Use botmask layer to analyze.\n")

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

    # Create layer_export
    for layer in layer_selected_list:
        
        #obtain layer property
        #line_color
        if (layer.getLayer().Group != []):
            line_color = layer.getLayer().Group[0].ViewObject.LineColor

        # Add Document
        new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', layer.label+ '_exp')
        export_list.append(new_layer)
        new_layer.Label = layer.label+ '_exp'

        new_layer_wire=[]
        for wire, label in zip(layer.wire_list, layer.label_list):
            obj_wire=formObject(wire, label)
            obj_wire.ViewObject.LineColor=line_color
            new_layer_wire.append(obj_wire)

        new_layer.Group = new_layer_wire

    # Determine the Range and Create QuadTreeNode
    botsilk_bbox = botsilk.getLayer().Shape.BoundBox
    quad_tree = QuadTree(botsilk_bbox.XMin, botsilk_bbox.YMin, botsilk_bbox.XMax, botsilk_bbox.YMax)

    # Insert Node in quad_tree
    for wire, face, label in zip(botsilk.wire_list, botsilk.face_list, botsilk.label_list):
        quad_tree.insert(Point(wire, face, label))

    # Start to detect
    error_line_color = (1.0, 1.0, 0.0)
    error_shape_color = (1.0, 0.0, 0.0)

    point_list = checkForProblem(layer_selected_list, quad_tree, dr, area_bound)

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

    #===================================================
    # Function 2: Print All Component In Open And THRU
    #===================================================
    # Get OPEN_color
    OPEN_color = OPEN.getLayer().Group[0].ViewObject.LineColor

    # Add Document
    new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', OPEN.label+ '_exp')
    export_list.append(new_layer)
    new_layer.Label = OPEN.label+ '_exp'

    new_layer_wire=[]
    for wire, label in zip(OPEN.wire_list, OPEN.label_list):
        obj_wire=formObject(wire, label)
        obj_wire.ViewObject.LineColor=OPEN_color
        new_layer_wire.append(obj_wire)

    new_layer.Group = new_layer_wire
    export_list.append(new_layer)

    # Determine the Range and Create QuadTreeNode
    botmask_bbox = botmask.getLayer().Shape.BoundBox
    quad_tree_1 = QuadTree(botmask_bbox.XMin, botmask_bbox.YMin, botmask_bbox.XMax, botmask_bbox.YMax)

    # Insert Node in quad_tree
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
    board_pocket_color = board_pocket.getLayer().Group[0].ViewObject.LineColor

    # Add Document
    new_layer = App.ActiveDocument.addObject('App::DocumentObjectGroup', board_pocket.label+ '_exp')
    export_list.append(new_layer)
    new_layer.Label = board_pocket.label+ '_exp'

    new_layer_wire=[]
    for wire, label in zip(board_pocket.wire_list, board_pocket.label_list):
        obj_wire=formObject(wire, label)
        obj_wire.ViewObject.LineColor=board_pocket_color
        new_layer_wire.append(obj_wire)

    new_layer.Group = new_layer_wire
    export_list.append(new_layer)

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

    #===================================================
    # Function 4
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
