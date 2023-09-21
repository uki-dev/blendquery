# TODO: fix typing
import bpy
import cadquery
import traceback
from . import mesh


def load(object: bpy.types.Object):
    active = bpy.context.view_layer.objects.active
    selected_objects = bpy.context.selected_objects.copy()

    # clean up previously generated objects
    unload(object)

    try:
        script = object.cadquery.script
        module = script.as_module()
        # TODO: realise a more flexible approach to exposing result to add-on
        #       like cq-editor's `show_object`
        objects = mesh.generate(module.result)
        add_object_pointers(objects, object.cadquery.pointers)
        attach_objects_to_root(objects, object)
        # link_materials(assembly, objects)
    except Exception as exception:
        traceback.print_exception(exception)
    restore_selection(active, selected_objects)


def restore_selection(active, selected_objects):
    for selected_object in bpy.context.selected_objects:
        selected_object.select_set(False)
    try:
        for selected_object in selected_objects:
            selected_object.select_set(True)
        bpy.context.view_layer.objects.active = active
    except:
        pass


def unload(object: bpy.types.Object):
    delete_object_ponters(object.cadquery.pointers)


def add_object_pointers(objects, collection):
    for object in objects:
        pointer = collection.add()
        pointer.object = object


def delete_object_ponters(collection):
    for pointer in collection:
        try:
            bpy.data.objects.remove(pointer.object, do_unlink=True)
        except:
            continue
    collection.clear()


def attach_objects_to_root(objects, parent):
    for object in objects:
        if object.parent is None:
            object.parent = parent


def link_materials(assembly: cadquery.Assembly, objects):
    for child in assembly.objects.values():
        try:
            material = bpy.data.materials[child.metadata["material"]]
            # TODO: use `objects`` not `bpy.data.objects`
            object = bpy.data.objects[child.name]
            apply_material(object, material)
        except:
            pass


def apply_material(object: bpy.types.Object, material: bpy.types.Material):
    def walk(object: bpy.types.Object):
        if object.type == "MESH":
            object.data.materials.append(material)
        for child in object.children:
            walk(child)

    walk(object)
