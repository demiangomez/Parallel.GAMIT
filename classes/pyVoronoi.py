"""
Author: Tyler Reddy

The purpose of this Python module is to provide utility code for handling spherical Voronoi Diagrams.
"""

import math

# deps
import scipy
import scipy.spatial
import numpy
import numpy.linalg
import numpy.random


class IntersectionError(Exception):
    pass


def filter_tetrahedron_to_triangle(current_tetrahedron_coord_array):
    current_triangle_coord_array = [] #initialize as a list
    for row in current_tetrahedron_coord_array: #ugly to use for loop for this, but ok for now!
        if row[0] == 0 and row[1] == 0 and row[2] == 0: #filter out origin row
            continue
        else:
            current_triangle_coord_array.append(row)
    current_triangle_coord_array = numpy.array(current_triangle_coord_array)
    return current_triangle_coord_array


def test_polygon_for_self_intersection(array_ordered_Voronoi_polygon_vertices_2D):
    '''Test an allegedly properly-ordered numpy array of Voronoi region vertices in 2D for self-intersection of edges
    based on algorithm described at http://algs4.cs.princeton.edu/91primitives/'''
    total_vertices = array_ordered_Voronoi_polygon_vertices_2D.shape[0]
    total_edges = total_vertices

    def intersection_test(a,b,c,d):
        # code in r & s equations provided on above website, which operate on the 2D coordinates of the edge
        # vertices for edges a - b and c - d
        # so: a, b, c, d are numpy arrays of vertex coordinates -- presumably with shape (2,)
        intersection = False
        denominator = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
        r = ( (a[1] - c[1]) * (d[0] - c[0]) - (a[0] - c[0]) * (d[1] - c[1]) ) / denominator
        s = ( (a[1] - c[1]) * (b[0] - a[0]) - (a[0] - c[0]) * (b[1] - a[1]) ) / denominator
        if (r >= 0 and r <= 1) and (s >= 0 and s <= 1): #conditions for intersection
            intersection = True
        if intersection:
            raise IntersectionError("Voronoi polygon line intersection !")

    # go through and test all possible non-consecutive edge combinations for intersection
    list_vertex_indices_in_edges = [ [vertex_index, vertex_index + 1] for vertex_index in range(total_vertices)]
    # for the edge starting from the last point in the Voronoi polygon the index of the final point should be switched to the starting index -- to close the polygon
    filtered_list_vertex_indices_in_edges = []
    for list_vertex_indices_in_edge in list_vertex_indices_in_edges:
        if list_vertex_indices_in_edge[1] == total_vertices:
            filtered_list_vertex_indices_in_edge = [list_vertex_indices_in_edge[0],0]
        else:
            filtered_list_vertex_indices_in_edge = list_vertex_indices_in_edge
        filtered_list_vertex_indices_in_edges.append(filtered_list_vertex_indices_in_edge)

    for edge_index, list_vertex_indices_in_edge in enumerate(filtered_list_vertex_indices_in_edges):
        for edge_index_2, list_vertex_indices_in_edge_2 in enumerate(filtered_list_vertex_indices_in_edges):
            if (list_vertex_indices_in_edge[0] not in list_vertex_indices_in_edge_2) and (list_vertex_indices_in_edge[1] not in list_vertex_indices_in_edge_2): #non-consecutive edges
                a = array_ordered_Voronoi_polygon_vertices_2D[list_vertex_indices_in_edge[0]]
                b = array_ordered_Voronoi_polygon_vertices_2D[list_vertex_indices_in_edge[1]]
                c = array_ordered_Voronoi_polygon_vertices_2D[list_vertex_indices_in_edge_2[0]]
                d = array_ordered_Voronoi_polygon_vertices_2D[list_vertex_indices_in_edge_2[1]]
                intersection_test(a,b,c,d)


def calculate_Vincenty_distance_between_spherical_points(cartesian_array_1,cartesian_array_2,sphere_radius):
    '''Apparently, the special case of the Vincenty formula (http://en.wikipedia.org/wiki/Great-circle_distance) may be the most accurate method for calculating great-circle distances.'''
    spherical_array_1 = convert_cartesian_array_to_spherical_array(cartesian_array_1)
    spherical_array_2 = convert_cartesian_array_to_spherical_array(cartesian_array_2)
    lambda_1 = spherical_array_1[1]
    lambda_2 = spherical_array_2[1]
    phi_1    = spherical_array_1[2]
    phi_2    = spherical_array_2[2]
    delta_lambda = abs(lambda_2 - lambda_1)
    delta_phi = abs(phi_2 - phi_1)
    radian_angle = math.atan2( math.sqrt( (math.sin(phi_2)*math.sin(delta_lambda))**2 + (math.sin(phi_1)*math.cos(phi_2) - math.cos(phi_1)*math.sin(phi_2)*math.cos(delta_lambda)  )**2 ),  (math.cos(phi_1) * math.cos(phi_2) + math.sin(phi_1) * math.sin(phi_2) * math.cos(delta_lambda) ) )
    spherical_distance = sphere_radius * radian_angle
    return spherical_distance


def calculate_haversine_distance_between_spherical_points(cartesian_array_1,cartesian_array_2,sphere_radius):
    '''Calculate the haversine-based distance between two points on the surface of a sphere. Should be more accurate than the arc cosine strategy. See, for example: http://en.wikipedia.org/wiki/Haversine_formula'''
    spherical_array_1 = convert_cartesian_array_to_spherical_array(cartesian_array_1)
    spherical_array_2 = convert_cartesian_array_to_spherical_array(cartesian_array_2)
    lambda_1 = spherical_array_1[1]
    lambda_2 = spherical_array_2[1]
    phi_1    = spherical_array_1[2]
    phi_2    = spherical_array_2[2]
    #we rewrite the standard Haversine slightly as long/lat is not the same as spherical coordinates - phi differs by pi/4
    spherical_distance = 2.0 * sphere_radius * math.asin(math.sqrt( ((1 - math.cos(phi_2-phi_1))/2.) + math.sin(phi_1) * math.sin(phi_2) * ( (1 - math.cos(lambda_2-lambda_1))/2.)  ))
    return spherical_distance


def filter_polygon_vertex_coordinates_for_extreme_proximity(array_ordered_Voronoi_polygon_vertices,sphere_radius):
    '''Merge (take the midpoint of) polygon vertices that are judged to be extremely close together and return the filtered polygon vertex array. The purpose is to alleviate numerical complications that may arise during surface area calculations involving polygons with ultra-close / nearly coplanar vertices.'''
    while 1:
        distance_matrix = scipy.spatial.distance.cdist(array_ordered_Voronoi_polygon_vertices,array_ordered_Voronoi_polygon_vertices,'euclidean')
        maximum_euclidean_distance_between_any_vertices = numpy.amax(distance_matrix)
        vertex_merge_threshold = 0.02 #merge any vertices that are separated by less than 1% of the longest inter-vertex distance (may have to play with this value a bit)
        threshold_assessment_matrix = distance_matrix / maximum_euclidean_distance_between_any_vertices
        row_indices_that_violate_threshold, column_indices_that_violate_threshold = numpy.where((threshold_assessment_matrix < vertex_merge_threshold) & (threshold_assessment_matrix > 0))
        if len(row_indices_that_violate_threshold) > 0 and len(column_indices_that_violate_threshold) > 0:
            for row, column in zip(row_indices_that_violate_threshold,column_indices_that_violate_threshold):
                if not row==column: #ignore diagonal values
                    first_violating_vertex_index = row
                    associated_vertex_index = column
                    new_vertex_at_midpoint = ( array_ordered_Voronoi_polygon_vertices[row] + array_ordered_Voronoi_polygon_vertices[column] ) / 2.0
                    spherical_polar_coords_new_vertex = convert_cartesian_array_to_spherical_array(new_vertex_at_midpoint)
                    spherical_polar_coords_new_vertex[0] = sphere_radius #project back to surface of sphere
                    new_vertex_at_midpoint = convert_spherical_array_to_cartesian_array(spherical_polar_coords_new_vertex)
                    array_ordered_Voronoi_polygon_vertices[row] = new_vertex_at_midpoint
                    array_ordered_Voronoi_polygon_vertices = numpy.delete(array_ordered_Voronoi_polygon_vertices,column,0)
                    break
        else: break #no more violating vertices
    return array_ordered_Voronoi_polygon_vertices


def calculate_surface_area_of_planar_polygon_in_3D_space(array_ordered_Voronoi_polygon_vertices):
    '''Based largely on: http://stackoverflow.com/a/12653810
    Use this function when spherical polygon surface area calculation fails (i.e., lots of nearly-coplanar vertices and negative surface area).'''
    #unit normal vector of plane defined by points a, b, and c
    def unit_normal(a, b, c):
        x = numpy.linalg.det([[1,a[1],a[2]],
             [1,b[1],b[2]],
             [1,c[1],c[2]]])
        y = numpy.linalg.det([[a[0],1,a[2]],
             [b[0],1,b[2]],
             [c[0],1,c[2]]])
        z = numpy.linalg.det([[a[0],a[1],1],
             [b[0],b[1],1],
             [c[0],c[1],1]])
        magnitude = (x**2 + y**2 + z**2)**.5
        return (x/magnitude, y/magnitude, z/magnitude)

    #area of polygon poly
    def poly_area(poly):
        '''Accepts a list of xyz tuples.'''
        assert len(poly) >= 3, "Not a polygon (< 3 vertices)."
        total = [0, 0, 0]
        N = len(poly)
        for i in range(N):
            vi1 = poly[i]
            vi2 = poly[(i+1) % N]
            prod = numpy.cross(vi1, vi2)
            total[0] += prod[0]
            total[1] += prod[1]
            total[2] += prod[2]
        result = numpy.dot(total, unit_normal(poly[0], poly[1], poly[2]))
        return abs(result/2)

    list_vertices = [] #need a list of tuples for above function
    for coord in array_ordered_Voronoi_polygon_vertices:
        list_vertices.append(tuple(coord))
    planar_polygon_surface_area = poly_area(list_vertices)
    return planar_polygon_surface_area

def calculate_surface_area_of_a_spherical_Voronoi_polygon(array_ordered_Voronoi_polygon_vertices,sphere_radius):
    '''Calculate the surface area of a polygon on the surface of a sphere. Based on equation provided here: http://mathworld.wolfram.com/LHuiliersTheorem.html
    Decompose into triangles, calculate excess for each'''
    #have to convert to unit sphere before applying the formula
    spherical_coordinates = convert_cartesian_array_to_spherical_array(array_ordered_Voronoi_polygon_vertices)
    spherical_coordinates[...,0] = 1.0
    array_ordered_Voronoi_polygon_vertices = convert_spherical_array_to_cartesian_array(spherical_coordinates)
    #handle nearly-degenerate vertices on the unit sphere by returning an area close to 0 -- may be better options, but this is my current solution to prevent crashes, etc.
    #seems to be relatively rare in my own work, but sufficiently common to cause crashes when iterating over large amounts of messy data
    if scipy.spatial.distance.pdist(array_ordered_Voronoi_polygon_vertices).min() < (10 ** -7):
        return 10 ** -8
    else:
        n = array_ordered_Voronoi_polygon_vertices.shape[0]
        #point we start from
        root_point = array_ordered_Voronoi_polygon_vertices[0]
        totalexcess = 0
        #loop from 1 to n-2, with point 2 to n-1 as other vertex of triangle
        # this could definitely be written more nicely
        b_point = array_ordered_Voronoi_polygon_vertices[1]
        root_b_dist = calculate_haversine_distance_between_spherical_points(root_point, b_point, 1.0)
        for i in 1 + numpy.arange(n - 2):
            a_point = b_point
            b_point = array_ordered_Voronoi_polygon_vertices[i+1]
            root_a_dist = root_b_dist
            root_b_dist = calculate_haversine_distance_between_spherical_points(root_point, b_point, 1.0)
            a_b_dist = calculate_haversine_distance_between_spherical_points(a_point, b_point, 1.0)
            s = (root_a_dist + root_b_dist + a_b_dist) / 2
            totalexcess += 4 * math.atan(math.sqrt( math.tan(0.5 * s) * math.tan(0.5 * (s-root_a_dist)) * math.tan(0.5 * (s-root_b_dist)) * math.tan(0.5 * (s-a_b_dist))))
        return totalexcess * (sphere_radius ** 2)

def calculate_and_sum_up_inner_sphere_surface_angles_Voronoi_polygon(array_ordered_Voronoi_polygon_vertices,sphere_radius):
    '''Takes an array of ordered Voronoi polygon vertices (for a single generator) and calculates the sum of the inner angles on the sphere surface. The resulting value is theta in the equation provided here: http://mathworld.wolfram.com/SphericalPolygon.html '''
    #if sphere_radius != 1.0:
        #try to deal with non-unit circles by temporarily normalizing the data to radius 1:
        #spherical_polar_polygon_vertices = convert_cartesian_array_to_spherical_array(array_ordered_Voronoi_polygon_vertices)
        #spherical_polar_polygon_vertices[...,0] = 1.0
        #array_ordered_Voronoi_polygon_vertices = convert_spherical_array_to_cartesian_array(spherical_polar_polygon_vertices)

    num_vertices_in_Voronoi_polygon = array_ordered_Voronoi_polygon_vertices.shape[0] #the number of rows == number of vertices in polygon

    #some debugging here -- I'm concerned that some sphere radii are demonstrating faulty projection of coordinates (some have r = 1, while others have r = sphere_radius -- see workflowy for more detailed notes)
    spherical_polar_polygon_vertices = convert_cartesian_array_to_spherical_array(array_ordered_Voronoi_polygon_vertices)
    min_vertex_radius = spherical_polar_polygon_vertices[...,0].min()
    #print 'before array projection check'
    assert sphere_radius - min_vertex_radius < 0.1, "The minimum projected Voronoi vertex r value should match the sphere_radius of {sphere_radius}, but got {r_min}.".format(sphere_radius=sphere_radius,r_min=min_vertex_radius)
    #print 'after array projection check'

    #two edges (great circle arcs actually) per vertex are needed to calculate tangent vectors / inner angle at that vertex
    current_vertex_index = 0
    list_Voronoi_poygon_angles_radians = []
    while current_vertex_index < num_vertices_in_Voronoi_polygon:
        current_vertex_coordinate = array_ordered_Voronoi_polygon_vertices[current_vertex_index]
        if current_vertex_index == 0:
            previous_vertex_index = num_vertices_in_Voronoi_polygon - 1
        else:
            previous_vertex_index = current_vertex_index - 1
        if current_vertex_index == num_vertices_in_Voronoi_polygon - 1:
            next_vertex_index = 0
        else:
            next_vertex_index = current_vertex_index + 1
        #try using the law of cosines to produce the angle at the current vertex (basically using a subtriangle, which is a common strategy anyway)
        current_vertex = array_ordered_Voronoi_polygon_vertices[current_vertex_index]
        previous_vertex = array_ordered_Voronoi_polygon_vertices[previous_vertex_index]
        next_vertex = array_ordered_Voronoi_polygon_vertices[next_vertex_index]
        #produce a,b,c for law of cosines using spherical distance (http://mathworld.wolfram.com/SphericalDistance.html)
        #old_a = math.acos(numpy.dot(current_vertex,next_vertex))
        #old_b = math.acos(numpy.dot(next_vertex,previous_vertex))
        #old_c = math.acos(numpy.dot(previous_vertex,current_vertex))
        #print 'law of cosines a,b,c:', old_a,old_b,old_c
        #a = calculate_haversine_distance_between_spherical_points(current_vertex,next_vertex,sphere_radius)
        #b = calculate_haversine_distance_between_spherical_points(next_vertex,previous_vertex,sphere_radius)
        #c = calculate_haversine_distance_between_spherical_points(previous_vertex,current_vertex,sphere_radius)
        a = calculate_Vincenty_distance_between_spherical_points(current_vertex,next_vertex,sphere_radius)
        b = calculate_Vincenty_distance_between_spherical_points(next_vertex,previous_vertex,sphere_radius)
        c = calculate_Vincenty_distance_between_spherical_points(previous_vertex,current_vertex,sphere_radius)
        #print 'law of haversines a,b,c:', a,b,c
        #print 'Vincenty edge lengths a,b,c:', a,b,c
        pre_acos_term = (math.cos(b) - math.cos(a)*math.cos(c)) / (math.sin(a)*math.sin(c))
        if abs(pre_acos_term) > 1.0:
            print('angle calc vertex coords (giving acos violation):', [convert_cartesian_array_to_spherical_array(vertex) for vertex in [current_vertex,previous_vertex,next_vertex]])
            print('Vincenty edge lengths (giving acos violation) a,b,c:', a,b,c)
            print('pre_acos_term:', pre_acos_term)
            #break
        current_vertex_inner_angle_on_sphere_surface = math.acos(pre_acos_term)

        list_Voronoi_poygon_angles_radians.append(current_vertex_inner_angle_on_sphere_surface)

        current_vertex_index += 1

    if abs(pre_acos_term) > 1.0:
        theta = 0
    else:
        theta = numpy.sum(numpy.array(list_Voronoi_poygon_angles_radians))

    return theta

def convert_cartesian_array_to_spherical_array(coord_array,angle_measure='radians'):
    '''Take shape (N,3) cartesian coord_array and return an array of the same shape in spherical polar form (r, theta, phi). Based on StackOverflow response: http://stackoverflow.com/a/4116899
    use radians for the angles by default, degrees if angle_measure == 'degrees' '''
    spherical_coord_array = numpy.zeros(coord_array.shape)
    xy = coord_array[...,0]**2 + coord_array[...,1]**2
    spherical_coord_array[...,0] = numpy.sqrt(xy + coord_array[...,2]**2)
    spherical_coord_array[...,1] = numpy.arctan2(coord_array[...,1], coord_array[...,0])
    spherical_coord_array[...,2] = numpy.arccos(coord_array[...,2] / spherical_coord_array[...,0])
    if angle_measure == 'degrees':
        spherical_coord_array[...,1] = numpy.degrees(spherical_coord_array[...,1])
        spherical_coord_array[...,2] = numpy.degrees(spherical_coord_array[...,2])
    return spherical_coord_array

def convert_spherical_array_to_cartesian_array(spherical_coord_array,angle_measure='radians'):
    '''Take shape (N,3) spherical_coord_array (r,theta,phi) and return an array of the same shape in cartesian coordinate form (x,y,z). Based on the equations provided at: http://en.wikipedia.org/wiki/List_of_common_coordinate_transformations#From_spherical_coordinates
    use radians for the angles by default, degrees if angle_measure == 'degrees' '''
    cartesian_coord_array = numpy.zeros(spherical_coord_array.shape)
    #convert to radians if degrees are used in input (prior to Cartesian conversion process)
    if angle_measure == 'degrees':
        spherical_coord_array[...,1] = numpy.deg2rad(spherical_coord_array[...,1])
        spherical_coord_array[...,2] = numpy.deg2rad(spherical_coord_array[...,2])
    #now the conversion to Cartesian coords
    cartesian_coord_array[...,0] = spherical_coord_array[...,0] * numpy.cos(spherical_coord_array[...,1]) * numpy.sin(spherical_coord_array[...,2])
    cartesian_coord_array[...,1] = spherical_coord_array[...,0] * numpy.sin(spherical_coord_array[...,1]) * numpy.sin(spherical_coord_array[...,2])
    cartesian_coord_array[...,2] = spherical_coord_array[...,0] * numpy.cos(spherical_coord_array[...,2])
    return cartesian_coord_array

def produce_triangle_vertex_coordinate_array_Delaunay_sphere(hull_instance):
    '''Return shape (N,3,3) numpy array of the Delaunay triangle vertex coordinates on the surface of the sphere.'''
    list_points_vertices_Delaunay_triangulation = []
    for simplex in hull_instance.simplices: #for each simplex (face; presumably a triangle) of the convex hull
        convex_hull_triangular_facet_vertex_coordinates = hull_instance.points[simplex]
        assert convex_hull_triangular_facet_vertex_coordinates.shape == (3,3), "Triangular facet of convex hull should be a triangle in 3D space specified by coordinates in a shape (3,3) numpy array."
        list_points_vertices_Delaunay_triangulation.append(convex_hull_triangular_facet_vertex_coordinates)
    array_points_vertices_Delaunay_triangulation = numpy.array(list_points_vertices_Delaunay_triangulation)
    return array_points_vertices_Delaunay_triangulation

def produce_array_Voronoi_vertices_on_sphere_surface(facet_coordinate_array_Delaunay_triangulation,sphere_radius,sphere_centroid):
    '''Return shape (N,3) array of coordinates for the vertices of the Voronoi diagram on the sphere surface given a shape (N,3,3) array of Delaunay triangulation vertices.'''
    assert facet_coordinate_array_Delaunay_triangulation.shape[1:] == (3,3), "facet_coordinate_array_Delaunay_triangulation should have shape (N,3,3)."
    #draft numpy vectorized workflow to avoid Python for loop
    facet_normals_array = numpy.cross(facet_coordinate_array_Delaunay_triangulation[...,1,...] - facet_coordinate_array_Delaunay_triangulation[...,0,...],facet_coordinate_array_Delaunay_triangulation[...,2,...] - facet_coordinate_array_Delaunay_triangulation[...,0,...])
    facet_normal_magnitudes = numpy.linalg.norm(facet_normals_array,axis=1)
    facet_normal_unit_vector_array = facet_normals_array / numpy.column_stack((facet_normal_magnitudes,facet_normal_magnitudes,facet_normal_magnitudes))
    #try to ensure that facet normal faces the correct direction (i.e., out of sphere)
    triangle_centroid_array = numpy.average(facet_coordinate_array_Delaunay_triangulation,axis=1)
    #normalize the triangle_centroid to unit sphere distance for the purposes of the following directionality check
    array_triangle_centroid_spherical_coords = convert_cartesian_array_to_spherical_array(triangle_centroid_array)
    array_triangle_centroid_spherical_coords[...,0] = 1.0
    triangle_centroid_array = convert_spherical_array_to_cartesian_array(array_triangle_centroid_spherical_coords)
    #the Euclidean distance between the triangle centroid and the facet normal should be smaller than the sphere centroid to facet normal distance, otherwise, need to invert the vector
    triangle_to_normal_distance_array = numpy.linalg.norm(triangle_centroid_array - facet_normal_unit_vector_array,axis=1)
    sphere_centroid_to_normal_distance_array = numpy.linalg.norm(sphere_centroid-facet_normal_unit_vector_array,axis=1)
    delta_value_array = sphere_centroid_to_normal_distance_array - triangle_to_normal_distance_array
    facet_normal_unit_vector_array[delta_value_array < -0.1] *= -1.0 #need to rotate the vector so that it faces out of the circle
    facet_normal_unit_vector_array *= sphere_radius #adjust for radius of sphere
    array_Voronoi_vertices = facet_normal_unit_vector_array
    assert array_Voronoi_vertices.shape[1] == 3, "The array of Voronoi vertices on the sphere should have shape (N,3)."
    return array_Voronoi_vertices
