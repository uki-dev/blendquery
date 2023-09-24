bl_info = {
    "name": "BlendQuery",
    "blender": (3, 0, 0),
    "category": "Parametric",
}

import bpy
from bpy.app.handlers import persistent
from . import polling
import traceback


def register():
    global cadquery, loading
    from . import install

    cadquery = install.cadquery()

    bpy.utils.register_class(AttributePropertyGroup)
    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(BlendQueryPropertyGroup)
    bpy.utils.register_class(ResetOperator)
    bpy.utils.register_class(BlendQueryPanel)
    bpy.types.Object.blendquery = bpy.props.PointerProperty(
        type=BlendQueryPropertyGroup
    )
    if cadquery:
        bpy.app.handlers.load_post.append(initialise)


def unregister():
    if cadquery:
        bpy.app.handlers.load_post.remove(initialise)
    bpy.utils.unregister_class(BlendQueryPanel)
    bpy.utils.unregister_class(ResetOperator)
    bpy.utils.unregister_class(BlendQueryPropertyGroup)
    bpy.utils.unregister_class(ObjectPropertyGroup)
    bpy.utils.unregister_class(AttributePropertyGroup)


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
    # TODO: Until we can somehow declare the `cadquery` module upfront, any files importing it must be imported AFTER we install it
    from . import loading

    blendquery = object.blendquery
    script, reload, attributes, objects = (
        blendquery.script,
        blendquery.reload,
        blendquery.attributes,
        blendquery.objects,
    )
    if script is not None and reload is True:

        def refresh():
            print("refresh")
            # If there are any issues in the script we just end early due to try/except
            try:
                # TODO: we should share this module with `loading.load` and avoid two script evaluations
                module = script.as_module()
                visible_attributes = {
                    key for key in dir(module) if not key.startswith("_")
                }
                # cadquery.attributes = attributes = [attribute for attribute in attributes if attribute.key in visible_attributes]

                for attribute in attributes:
                    attribute.defined = attribute.key in visible_attributes

                for key in visible_attributes:
                    value = getattr(module, key)
                    type_name = value.__class__.__name__
                    print(
                        "module attribute "
                        + str(key)
                        + " "
                        + type_name
                        + " "
                        + str(type_name in TYPE_TO_PROPERTY)
                    )

                    if type_name in TYPE_TO_PROPERTY:
                        # Find existing property group that matches key and type
                        attribute_property_group = next(
                            (
                                attribute
                                for attribute in attributes
                                if attribute.key == key and attribute.type == type_name
                            ),
                            None,
                        )
                        # Do not add property group if one matching already exists
                        if attribute_property_group is not None:
                            continue

                        attribute_property_group = attributes.add()
                        attribute_property_group.key = key
                        attribute_property_group.type = type_name
                        property = TYPE_TO_PROPERTY[type_name]
                        setattr(attribute_property_group, property, value)
                        print("added property group " + str(key))

                loading.load(object)
            except Exception as exception:
                traceback.print_exception(exception)

        refresh()
        disposers[object] = polling.watch_for_text_changes(script, refresh)
    else:
        if script is None:
            loading.unload(objects)
        disposer = disposers[object]
        if callable(disposer):
            disposer()


TYPE_TO_PROPERTY = {
    "bool": "bool_value",
    "int": "int_value",
    "float": "float_value",
    "str": "str_value",
}


class AttributePropertyGroup(bpy.types.PropertyGroup):
    _init = False

    def update(self, _):
        # if not self._init:
        #     print("ignore first update")
        #     self._init = True
        #     return
        print("update " + str(self.key) + " " + str(self.str_value))
        update_object(self.id_data)

    key: bpy.props.StringProperty()
    type: bpy.props.EnumProperty(
        items=[
            ("bool", "Boolean", "Boolean Type"),
            ("int", "Integer", "Integer Type"),
            ("float", "Float", "Float Type"),
            ("str", "String", "String Type"),
        ],
    )
    bool_value: bpy.props.BoolProperty(update=update)
    int_value: bpy.props.IntProperty(update=update)
    float_value: bpy.props.FloatProperty(update=update)
    str_value: bpy.props.StringProperty(update=update)
    defined: bpy.props.BoolProperty(default=True)


class ObjectPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class BlendQueryPropertyGroup(bpy.types.PropertyGroup):
    def update(self, _):
        update_object(self.id_data)

    script: bpy.props.PointerProperty(name="Script", type=bpy.types.Text, update=update)
    reload: bpy.props.BoolProperty(name="Hot Reload", default=True, update=update)
    attributes: bpy.props.CollectionProperty(type=AttributePropertyGroup)
    objects: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


class ResetOperator(bpy.types.Operator):
    bl_idname = "blendquery.reset"
    bl_label = "Reset"

    def execute(self, context):
        if context.active_object:
            context.active_object.blendquery.attributes.clear()
        return {"FINISHED"}


class BlendQueryPanel(bpy.types.Panel):
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
        if context.active_object:
            object = context.active_object
            column.prop(object.blendquery, "script")
            column.prop(object.blendquery, "reload")
            box = layout.box()
            row = box.row()
            row.label(text="Attributes")
            row.operator("blendquery.reset", icon="FILE_REFRESH")
            for attribute in object.blendquery.attributes:
                if not attribute.defined:
                    continue
                row = box.row()
                property = TYPE_TO_PROPERTY[attribute.type]
                row.prop(attribute, property, text=attribute.key)
