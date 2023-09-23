bl_info = {
    "name": "BlendQuery",
    "blender": (3, 0, 0),
    "category": "Parametric",
}

import bpy
from bpy.app.handlers import persistent
from . import polling


def register():
    global cadquery, loading
    from . import install

    cadquery = install.cadquery()

    # TODO: Until we can somehow declare the `cadquery` module upfront, any files importing it must be imported AFTER we install it

    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(CadQueryPropertyGroup)
    bpy.utils.register_class(CadQueryPanel)
    bpy.types.Object.cadquery = bpy.props.PointerProperty(type=CadQueryPropertyGroup)
    if cadquery:
        bpy.app.handlers.load_post.append(initialise)


def unregister():
    if cadquery:
        bpy.app.handlers.load_post.remove(initialise)
    bpy.utils.unregister_class(CadQueryPanel)
    bpy.utils.unregister_class(CadQueryPropertyGroup)
    bpy.utils.unregister_class(ObjectPropertyGroup)


@persistent
def initialise(_=None):
    # TODO: find a cleaner solution than this
    # as `update_object` may delete objects from `bpy.data.objects` to perform cleanup, iterate on a copy of it instead to avoid crashes due to `EXCEPTION_ACCESS_VIOLATION`
    objects = []
    for object in bpy.data.objects:
        objects.append(object)
    for object in objects:
        try:
            update_object(object)
        except:
            pass


disposers = {}


def update_object(object: bpy.types.Object):
    from . import loading

    script = object.cadquery.script
    reload = object.cadquery.reload
    if script is not None and reload is True:
        loading.load(object)
        disposers[object] = polling.watch_for_text_changes(
            script, lambda: loading.load(object)
        )
    else:
        if script is None:
            # clean up previously generated objects if script is removed
            loading.unload(object)
        disposer = disposers[object]
        if callable(disposer):
            disposer()


class ObjectPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class CadQueryPropertyGroup(bpy.types.PropertyGroup):
    def update(self, _):
        update_object(self.id_data)

    script: bpy.props.PointerProperty(name="Script", type=bpy.types.Text, update=update)
    reload: bpy.props.BoolProperty(name="Hot Reload", default=True, update=update)
    objects: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


class CadQueryPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_CAD_QUERY"
    bl_label = bl_info["name"]
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        if not cadquery:
            box = layout.box()
            box.label(
                text="Failed to install dependencies; See system console.", icon="ERROR"
            )
        column = layout.row()
        column.enabled = cadquery is not None
        if len(context.selected_objects) > 0:
            object = context.selected_objects[0]
            column.prop(object.cadquery, "script")
            column.prop(object.cadquery, "reload")
