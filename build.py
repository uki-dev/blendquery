# TODO: fix typing
import bpy
import cadquery
from typing import Union, List
import re

Object = Union[cadquery.Workplane, cadquery.Shape, cadquery.Assembly]


class BlendQueryBuildException(Exception):
    def __init__(self, message):
        super().__init__(message)


def build(cadquery_objects, object_pointers, root):
    # Store current selection
    active = bpy.context.view_layer.objects.active
    selected_objects = bpy.context.selected_objects.copy()

    # Clean up previously generated objects
    clean(object_pointers)

    for name, value in cadquery_objects.items():
        build_object(value, name, root, object_pointers)

    # Restore selection
    for selected_object in bpy.context.selected_objects:
        selected_object.select_set(False)
    try:
        for selected_object in selected_objects:
            selected_object.select_set(True)
        bpy.context.view_layer.objects.active = active
    except:
        pass


def clean(object_pointers):
    for pointer in object_pointers:
        try:
            bpy.data.objects.remove(pointer.object, do_unlink=True)
        except:
            continue
    object_pointers.clear()


# TODO: Reimplement material linking
def build_object(object: Object, name: str, parent, object_pointers):
    if isinstance(object, cadquery.Assembly):
        assembly_object = create_blender_object(
            name if object.parent is None else object.name,
            assembly_object,
            object_pointers,
        )
        for shape in object.shapes:
            build_object(shape, name, assembly_object, object_pointers)
        for child in object.children:
            build_object(child, name, assembly_object, object_pointers)
        return

    if isinstance(object, cadquery.Shape):
        shape = object
    elif isinstance(object, cadquery.Workplane):
        shape = cadquery.exporters.utils.toCompound(object)
    else:
        raise BlendQueryBuildException(
            "Failed to build object; Unsupported object type " + str(type(object))
        )
    build_shape(shape, name, parent, object_pointers)


def build_shape(
    shape: cadquery.Shape,
    name: str,
    parent,
    object_pointers,
    tolerance=0.1,
    angularTolerance=0.1,
):
    vertices, faces = shape.tessellate(tolerance, angularTolerance)
    vertices = [vertex.toTuple() for vertex in vertices]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    return create_blender_object(name, parent, object_pointers, mesh)


def create_blender_object(name: str, parent, object_pointers, mesh):
    object = bpy.data.objects.new(
        name,
        mesh,
    )
    object.parent = parent
    property_group = object_pointers.add()
    property_group.object = object
    bpy.context.scene.collection.objects.link(object)
    return object
