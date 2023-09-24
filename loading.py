# TODO: fix typing
import bpy
import cadquery as cq
import cadquery.cqgi as cqgi
from cadquery import Workplane, Compound, Shape, Assembly
import traceback
from types import ModuleType
from typing import List, Union
import re

Object = Union[cq.Workplane, cq.Shape, cq.Assembly]


def load(object: bpy.types.Object):
    cadquery = object.cadquery
    script, objects, attributes = cadquery.script, cadquery.objects, cadquery.attributes

    # Store current selection
    active = bpy.context.view_layer.objects.active
    selected_objects = bpy.context.selected_objects.copy()

    # Clean up previously generated objects
    unload(objects)

    build(script.as_string(), object, objects, attributes)

    # Restore selection
    for selected_object in bpy.context.selected_objects:
        selected_object.select_set(False)
    try:
        for selected_object in selected_objects:
            selected_object.select_set(True)
        bpy.context.view_layer.objects.active = active
    except:
        pass


def unload(objects: list[bpy.types.Object]):
    for pointer in objects:
        try:
            bpy.data.objects.remove(pointer.object, do_unlink=True)
        except:
            continue
    objects.clear()


# TODO: share with `__init__.py`
TYPE_TO_PROPERTY = {
    "bool": "bool_value",
    "int": "int_value",
    "float": "float_value",
    "str": "str_value",
}


def build(script, parent, objects, attributes):
    globals = {
        "cq": cq,
    }
    locals = {}

    print("Executing")
    try:
        # Override attributes
        for attribute in attributes:
            if not attribute.defined:
                continue
            key = attribute.key
            property = TYPE_TO_PROPERTY[attribute.type]
            value = getattr(attribute, property)
            print("Overriding " + key + " with " + str(value))
            pattern = r'({} = "(.*?)")'.format(re.escape(key))
            script = re.sub(pattern, f'{key} = "{value}"', script)
        print("Script override: " + script)
        exec(script, globals, locals)
        # Ignore all keys that start with `_` as they are to be considered hidden
        visible_locals = {
            key: value for key, value in locals.items() if not key.startswith("_")
        }
        for name, value in visible_locals.items():
            print("Iterating local: " + str(name) + " : " + str(value))
            if isinstance(value, Object):
                build_object(value, name, parent, objects)
    except Exception as exception:
        traceback.print_exception(exception)


def build_object(object: Object, name: str, parent, objects):
    print("Building object " + name + ": " + str(object) + " " + str(type(object)))

    if isinstance(object, Workplane):
        compound = cq.exporters.utils.toCompound(object)
        blender_object = build_shape(compound, name)
        blender_object.parent = parent
        # object.data.materials.append(material)
        property_group = objects.add()
        property_group.object = blender_object
    elif isinstance(object, Shape):
        blender_object = build_shape(object, name)
        blender_object.parent = parent
        # object.data.materials.append(material)
        property_group = objects.add()
        property_group.object = blender_object
    elif isinstance(object, Assembly):
        blender_object = bpy.data.objects.new(
            name if object.parent is None else object.name, None
        )
        blender_object.parent = parent
        property_group = objects.add()
        property_group.object = blender_object
        bpy.context.scene.collection.objects.link(blender_object)
        # try:
        #     material_name = assembly.metadata["material"]
        #     material = bpy.data.materials[material_name]
        # except:
        #     pass
        for shape in object.shapes:
            build_object(shape, name, blender_object, objects)
        for child in object.children:
            build_object(child, name, blender_object, objects)


def build_shape(
    shape: Shape,
    name: str,
    tolerance=0.1,
    angularTolerance=0.1,
):
    print("Building shape " + name + ": " + str(shape) + " " + str(type(shape)))
    vertices, faces = shape.tessellate(tolerance, angularTolerance)
    vertices = [vertex.toTuple() for vertex in vertices]

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    object = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(object)
    return object
