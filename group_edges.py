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
            if con_vert.count(edge.Vertexes[0].hashCode()) > 0: #Check if there is a match in hashcode (mutual vertex)
                if len(edge.Vertexes)>1: #circles only have one vertex..
                    next = edge.Vertexes[1].hashCode()  # find the next vertex' hashcode
                    con_vert.append(next) #Add it to the list of vertexes
                result_edges.append(edge) #Add the edge to the list of edges
                searchedges.pop(i)  # remove found edge from searchspace
                found = True
                break
            if len(edge.Vertexes)>1: #circles only have one vertex..
                if con_vert.count(edge.Vertexes[1].hashCode()) > 0 and found is False: #Check the second vertex of the edge
                    next = edge.Vertexes[0].hashCode()  # find the next
                    con_vert.append(next)
                    result_edges.append(edge)
                    searchedges.pop(i)  # remove found edge from searchspace
                    found = True
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
        return result_edges
