function formPolylineUsingBVH(edges, tol3d):
    sortedEdges = empty list
    bvh = buildBVH(edges) // Construct the bounding volume hierarchy
    
    // Select an arbitrary starting edge
    startEdge = selectArbitraryEdge(edges)
    sortedEdges.append(startEdge)
    currentEdge = startEdge

    while True:
        // Find adjacent edges within tolerance distance
        adjacentEdges = findAdjacentEdges(bvh, currentEdge, tol3d)
        
        // If no adjacent edges found, terminate the process
        if adjacentEdges.isEmpty():
            break
        
        // Select the adjacent edge that maintains polyline continuity
        nextEdge = selectNextEdge(currentEdge, adjacentEdges)
        
        // Add the selected edge to the sorted list
        sortedEdges.append(nextEdge)
        
        // Update current edge
        currentEdge = nextEdge
    
    return sortedEdges

def buildBVH(edges):
    // Construct the bounding volume hierarchy from the edges
    // This step may involve recursively partitioning the space and assigning edges to bounding volumes
    
def findAdjacentEdges(bvh, edge, tol3d):
    // Query the BVH to find neighboring edges within the tolerance distance of the given edge
    // This may involve traversing the BVH and checking proximity of bounding volumes
    
def selectNextEdge(currentEdge, adjacentEdges):
    // Select the next edge from the adjacent edges that maintains polyline continuity
    // This may involve checking vertex connectivity and possibly reversing the edge
    
def selectArbitraryEdge(edges):
    // Select an arbitrary edge from the list of edges
    // This can be the first edge or any other suitable selection strategy










T a polyline connecting adjacent edges and ensure that consecutive edges in the sorted list are connected end-to-end, you can follow these steps:

    Build the Bounding Volume Hierarchy (BVH): First, construct a bounding volume hierarchy (BVH) for all edges in your model. BVH is a tree structure where each node represents a bounding volume enclosing a subset of the edges. This allows for efficient spatial querying to find adjacent edges.

    Find Adjacent Edges: Traverse the BVH to find adjacent edges. For each edge, query the BVH to find neighboring edges within a certain proximity. This proximity can be determined based on the tolerance value tol3d.

    Form Polyline: Once adjacent edges are identified, connect them end-to-end to form a continuous polyline. You can do this by ensuring that the end vertex of one edge matches the start vertex of the next edge in the polyline. If necessary, reverse the direction of edges to ensure proper connectivity.

    Sort Edges: After forming the polyline, sort the edges based on their connectivity to ensure consecutive edges are connected end-to-end.

Here is a more detailed algorithm:

    Initialize an empty list to store the polyline.
    Select an arbitrary edge to start the polyline.
    Traverse the BVH to find neighboring edges within the tolerance distance.
    Connect the selected edge with the neighboring edge by ensuring proper vertex connectivity.
    If no adjacent edge is found, terminate the process.
    Repeat the process with the newly connected edge until all edges are included in the polyline.
    Sort the edges in the polyline based on their connectivity.

By following this approach, you can form a polyline connecting adjacent edges while ensuring that consecutive edges in the sorted list are connected end-to-end, thus forming a continuous polyline.

def group_edges_by_connection(edge_list):
    """Translate a list of edges to a list of lists of edges that are connected to each other by their endpoints"""
    result_edges = [edge_list[-1]]
    if len(edge_list[-1].Vertexes) > 1:  # circles only have one vertex..
        con_vert = [edge_list[-1].Vertexes[0], edge_list[-1].Vertexes[1]]
    else:
        con_vert = [edge_list[-1].Vertexes[0]]

    #2. Initialize list of edges that still have no match
    searchedges = edge_list[:-1]

    #3. Continue as long as there are searchedges
    while len(searchedges) > 0:

        found = False #Parameter to tell if a match has been found
        for i, edge in enumerate(searchedges):
            if len(edge.Vertexes)>1: #circles only have one vertex..
                if con_vert.count(edge.Vertexes[0].hashCode()) > 0: #Check if there is a match in hashcode (mutual vertex)
                    next = edge.Vertexes[1].hashCode()  # find the next vertex' hashcode
                    con_vert.append(next) #Add it to the list of vertexes
                    result_edges.append(edge) #Add the edge to the list of edges
                    searchedges.pop(i)  # remove found edge from searchspace
                    found = True
                    break
                elif con_vert.count(edge.Vertexes[1].hashCode()) > 0: #Check the second vertex of the edge
                    next = edge.Vertexes[0].hashCode()  # find the next
                    con_vert.append(next)
                    result_edges.append(edge)
                    searchedges.pop(i)  # remove found edge from searchspace
                    found = True
                    break
            else:
                searchedges.pop(i): # remove circle from searchspace
                break


        # If a match is found keep a list of vertexes that can still be match in con_vert
        if found is True:
            open_vert = []
            for i, edge in enumerate(searchedges):
                if len(edge.Vertexes)>1:
                    open_vert.extend(
                        [edge.Vertexes[0].hashCode(), edge.Vertexes[1].hashCode()])  # all open vertexes which can be connected
                else:
                    open_vert.extend(
                        [edge.Vertexes[0].hashCode()])

            new_con = [vhash for vhash in con_vert if open_vert.count(
                vhash) > 0]  # remove all vertexes which can not be further connected to edges from con_vert (they are not interesting to be matched as their is no match no more)
            con_vert = new_con
        else:
            break  # no more edge added, end
 
    if len(searchedges)==0: #Nothing can be added anymore
        return [result_edges]
    else:
        result_edges = [result_edges] + group_edges_by_connection(searchedges) #A new list can be made and appended
        return result_edge












def group_edges_by_connection(edge_list):
    """Translate a list of edges to a list of lists of edges that are connected to each other by their endpoints"""
    result_edges = [edge_list[-1]]
    if len(edge_list[-1].Vertexes) > 1:  # circles only have one vertex..
        con_vert = [edge_list[-1].Vertexes[0].hashCode(), edge_list[-1].Vertexes[1].hashCode()]
    else:
        con_vert = [edge_list[-1].Vertexes[0].hashCode()]

    #2. Initialize list of edges that still have no match
    searchedges = edge_list[:-1]

    #3. Continue as long as there are searchedges
    while len(searchedges) > 0:

        found = False #Parameter to tell if a match has been found
        for i, edge in enumerate(searchedges):
            if len(edge.Vertexes)>1: #circles only have one vertex..
                if con_vert.count(edge.Vertexes[0].hashCode()) > 0: #Check if there is a match in hashcode (mutual vertex)
                    next = edge.Vertexes[1].hashCode()  # find the next vertex' hashcode
                    con_vert.append(next) #Add it to the list of vertexes
                    result_edges.append(edge) #Add the edge to the list of edges
                    searchedges.pop(i)  # remove found edge from searchspace
                    found = True
                    break
                elif con_vert.count(edge.Vertexes[1].hashCode()) > 0: #Check the second vertex of the edge
                    next = edge.Vertexes[0].hashCode()  # find the next
                    con_vert.append(next)
                    result_edges.append(edge)
                    searchedges.pop(i)  # remove found edge from searchspace
                    found = True
                    break
            else:
                searchedges.pop(i): # remove circle from searchspace
                break


        # If a match is found keep a list of vertexes that can still be match in con_vert
        if found is True:
            open_vert = []
            for i, edge in enumerate(searchedges):
                if len(edge.Vertexes)>1:
                    open_vert.extend(
                        [edge.Vertexes[0].hashCode(), edge.Vertexes[1].hashCode()])  # all open vertexes which can be connected
                else:
                    open_vert.extend(
                        [edge.Vertexes[0].hashCode()])

            new_con = [vhash for vhash in con_vert if open_vert.count(
                vhash) > 0]  # remove all vertexes which can not be further connected to edges from con_vert (they are not interesting to be matched as their is no match no more)
            con_vert = new_con
        else:
            break  # no more edge added, end
 
    if len(searchedges)==0: #Nothing can be added anymore
        return [result_edges]
    else:
        result_edges = [result_edges] + group_edges_by_connection(searchedges) #A new list can be made and appended
        return result_edge
