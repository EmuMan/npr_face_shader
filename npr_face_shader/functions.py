import bpy
from mathutils import Vector
import bmesh

from .utils import *

def create_face_shadow_map():
    target_name = 'face'
    target_obj = bpy.data.objects.get(target_name)
    
    face_lines_name = 'Face Lines'
    face_lines_obj = bpy.data.objects.get(face_lines_name)
    face_lines_layer = face_lines_obj.data.layers[0]
    face_lines_strokes = face_lines_layer.frames[0].strokes
    
    nose_line_name = 'Nose Line'
    nose_line_obj = bpy.data.objects.get(nose_line_name)
    nose_line_layer = nose_line_obj.data.layers[0]
    nose_line_stroke = nose_line_layer.frames[0].strokes[0]
    
    rembrandt_line_name = 'Rembrandt Line'
    rembrandt_line_obj = bpy.data.objects.get(rembrandt_line_name)
    rembrandt_line_layer = rembrandt_line_obj.data.layers[0]
    rembrandt_line_stroke = rembrandt_line_layer.frames[0].strokes[0]
    
    # mesh has to be triangulated for barycentric conversion to work
    print('Triangulating mesh...')
    bm = bmesh.new()
    bm.from_mesh(target_obj.data)
    triangulated = bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    
    lines_on_image = []
    print('Mapping face strokes to UV coordinates...')
    for stroke in face_lines_strokes:
        lines_on_image.append(project_points_to_uv(bm, triangulated, target_obj.matrix_world, stroke.points, face_lines_obj.matrix_world))
    
    image = bpy.data.images['Face Shadow']
    width = image.size[0]
    height = image.size[1]
    
    # The image is grayscale so this is fine
    image_pixels = [0.0 for _ in range(width * height)]
    
    print('Finding row intersection points...')
    intersection_points = []
    for line in lines_on_image:
        intersections_for_line = []
        for i in range(height):
            segments = get_surrounding_values(i / height, line, lambda point: point.y)
            if not segments[0]:
                intersections_for_line.append(segments[1].x)
            elif not segments[1]:
                intersections_for_line.append(segments[0].x)
            else:
                intersections_for_line.append(get_line_x_from_y(i / height, segments[0], segments[1]))
        intersection_points.append(intersections_for_line)
    
    print('Calculating base pixels...')
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            line_options = [(i, x_values[y]) for i, x_values in enumerate(intersection_points)]
            surrounding_lines = get_surrounding_values(position.x, line_options, key=lambda line: line[1])
            
            final_value = 0.0
            if surrounding_lines[0]:
                offset = (surrounding_lines[0][0] + 1) / (len(line_options) + 1)
                final_point = 1.0
                if surrounding_lines[1]:
                    final_point = surrounding_lines[1][1]
                temp_value = (position.x - surrounding_lines[0][1]) / \
                            (final_point - surrounding_lines[0][1])
                final_value = offset + temp_value / (len(line_options) + 1)
            elif surrounding_lines[1]:
                final_value = (position.x / surrounding_lines[1][1]) / (len(line_options) + 1)
            
            set_pixel(image_pixels, width, height, position, final_value)
    
    nose_on_image = []
    print('Mapping nose stroke to UV coordinates...')
    nose_on_image = project_points_to_uv(bm, triangulated, target_obj.matrix_world, nose_line_stroke.points, nose_line_obj.matrix_world)
    
    print('Closing off nose shape...')
    nose_on_image = close_2d_shape(nose_on_image)
    
    print('Calculating nose pixels...')
    # many multipliers are so the effective area of the nose is expanded
    nose_center = find_2d_shape_center(nose_on_image)
    nose_max_distance_squared = find_2d_furthest_distance_squared(nose_center, nose_on_image)
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            ratio = find_value_inside_shape(position, nose_center, nose_max_distance_squared, nose_on_image)
            if not ratio:
                continue
            pixel_value = ratio ** 2 / 2.0
            set_pixel_blended(image_pixels, width, height, position, pixel_value)
    
    rembrandt_on_image = []
    print('Mapping Rembrandt stroke to UV coordinates...')
    rembrandt_on_image = project_points_to_uv(bm, triangulated, target_obj.matrix_world, rembrandt_line_stroke.points, rembrandt_line_obj.matrix_world)
    
    print('Closing off Rembrandt shape...')
    rembrandt_on_image = close_2d_shape(rembrandt_on_image)
    
    print('Calculating Rembrandt pixels...')
    rembrandt_center = find_2d_shape_center(rembrandt_on_image)
    rembrandt_max_distance_squared = find_2d_furthest_distance_squared(rembrandt_center, rembrandt_on_image)
    for x in range(width):
        for y in range(height):
            position = Vector((x / width, y / height))
            ratio = find_value_inside_shape(position, rembrandt_center, rembrandt_max_distance_squared, rembrandt_on_image)
            if not ratio:
                continue
            pixel_value = (1 - ratio ** 2) / 2.0 + 0.5
            set_pixel_blended(image_pixels, width, height, position, pixel_value)
    
    print('Updating image...')
    converted = []
    for pixel in image_pixels:
        converted.extend([pixel, pixel, pixel, 1.0])
    image.pixels[:] = converted
    
    print('Done!')

if __name__ == '__main__':
    main()
