# TODO: fix typing
import bpy
import cadquery
from typing import Union, List
import re

Object = Union[cadquery.Workplane, cadquery.Shape, cadquery.Assembly]


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
    # TODO: Tidy up this mess
    if isinstance(object, cadquery.Workplane):
        compound = cadquery.exporters.utils.toCompound(object)
        blender_object = build_shape(compound, name)
        blender_object.parent = parent
        # object.data.materials.append(material)
        property_group = object_pointers.add()
        property_group.object = blender_object
    elif isinstance(object, cadquery.Shape):
        blender_object = build_shape(object, name)
        blender_object.parent = parent
        # object.data.materials.append(material)
        property_group = object_pointers.add()
        property_group.object = blender_object
    elif isinstance(object, cadquery.Assembly):
        blender_object = bpy.data.objects.new(
            name if object.parent is None else object.name, None
        )
        blender_object.parent = parent
        property_group = object_pointers.add()
        property_group.object = blender_object
        bpy.context.scene.collection.objects.link(blender_object)
        # try:
        #     material_name = assembly.metadata["material"]
        #     material = bpy.data.materials[material_name]
        # except:
        #     pass
        for shape in object.shapes:
            build_object(shape, name, blender_object, object_pointers)
        for child in object.children:
            build_object(child, name, blender_object, object_pointers)
    else:
        raise TypeError("Unsupported object type")


def build_shape(
    shape: cadquery.Shape,
    name: str,
    tolerance=0.1,
    angularTolerance=0.1,
):
    vertices, faces = shape.tessellate(tolerance, angularTolerance)
    vertices = [vertex.toTuple() for vertex in vertices]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    object = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(object)
    return object
