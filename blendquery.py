from typing import Union, List, Tuple
from dataclasses import dataclass, field

import bpy
import cadquery
import build123d

ParametricShape = Union[cadquery.Shape, build123d.Shape]
ParametricObject = Union[
    ParametricShape,
    cadquery.Workplane,
    cadquery.Assembly,
    build123d.Builder,
]

@dataclass
class ParametricObjectNode:
    name: str
    material: Union[str, None] = None
    children: List['ParametricObjectNode'] = field(default_factory=list)
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)

class BlendQueryBuildException(Exception):
    def __init__(self, message):
        super().__init__(message)

def regenerate_blendquery_object(parametric_objects: List[ParametricObject], root_blender_object: bpy.types.Object, old_blender_objects):
    # Store current selection
    active = bpy.context.view_layer.objects.active
    selected_objects = bpy.context.selected_objects.copy()

    # Clean up previously generated objects
    delete_blender_objects(old_blender_objects)

    new_blender_objects = []

    for parametric_object in parametric_objects:
        new_blender_objects.append(build_blender_object(parametric_object, root_blender_object))

    new_blender_objects = flatten_list(new_blender_objects)

    root_collection = root_blender_object.users_collection[0]
    # Link new objects to the scene and add them into the blendquery objects collection
    for blender_object in new_blender_objects:
        root_collection.objects.link(blender_object)
        property_group = old_blender_objects.add()
        property_group.object = blender_object

    # Restore selection
    for selected_object in bpy.context.selected_objects:
        selected_object.select_set(False)
    try:
        for selected_object in selected_objects:
            selected_object.select_set(True)
        bpy.context.view_layer.objects.active = active
    except:
        pass

def delete_blender_objects(blender_objects):
    for pointer in blender_objects:
        try:
            bpy.data.objects.remove(pointer.object, do_unlink=True)
        except:
            continue
    blender_objects.clear()

def build_blender_object(parametric_object: ParametricObjectNode, parent: bpy.types.Object):

    mesh = None

    if len(parametric_object.vertices) > 0:
        mesh = bpy.data.meshes.new(parametric_object.name)
        mesh.from_pydata(parametric_object.vertices, [], parametric_object.faces)
        mesh.update()

    blender_object = bpy.data.objects.new(
        parametric_object.name,
        mesh,
    )

    if mesh is not None:
        if parametric_object.material is not None:
            try:
                material = bpy.data.materials[parametric_object.material]
                blender_object.data.materials.append(material)
            except:
                pass

    blender_object.parent = parent

    blender_objects = [blender_object]

    for child in parametric_object.children:
        blender_objects.append(build_blender_object(child, blender_object))

    return blender_objects

def flatten_list(nested_list):
    flattened_list = []
    for item in nested_list:
        if isinstance(item, list):
            flattened_list.extend(flatten_list(item))
        else:
            flattened_list.append(item)
    return flattened_list
