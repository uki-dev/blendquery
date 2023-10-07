bl_info = {
    "name": "BlendQuery",
    "blender": (3, 0, 0),
    "category": "Parametric",
}

import os
import sys
import venv
import platform
import traceback
import importlib
import importlib.util
from typing import Union

import bpy
from bpy.app.handlers import persistent

from . import poll

if platform.system() == "Windows":
    user_dir = os.environ["USERPROFILE"]
else:
    user_dir = os.environ["HOME"]
venv_dir = os.path.join(user_dir, "blendquery")


def setup_venv():
    if not os.path.exists(os.path.join(venv_dir, "pyvenv.cfg")):
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_dir)

    # TODO: Is there a better way to do this?
    sys.path.append(os.path.join(venv_dir, "Lib", "site-packages"))


def register():
    bpy.utils.register_class(AttributePropertyGroup)
    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(BlendQueryPropertyGroup)
    bpy.utils.register_class(BlendQueryInstallOperator)
    bpy.utils.register_class(BlendQueryPanel)
    bpy.types.Object.blendquery = bpy.props.PointerProperty(
        type=BlendQueryPropertyGroup
    )

    setup_venv()

    global cadquery
    if importlib.util.find_spec("cadquery") is not None:
        cadquery = importlib.import_module("cadquery")
        bpy.app.handlers.load_post.append(initialise)
    else:
        cadquery = None


def unregister():
    if cadquery:
        bpy.app.handlers.load_post.remove(initialise)
    bpy.utils.unregister_class(BlendQueryPanel)
    bpy.utils.unregister_class(BlendQueryInstallOperator)
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
script_exception = None


# TODO: Turn this into a modal operator
def update_object(object: bpy.types.Object):
    # TODO: Until we can somehow declare the `cadquery` module upfront, any files importing it must be imported AFTER we install it
    from .build import build, clean
    from .parse import parse_script, map_attributes

    blendquery = object.blendquery
    script, reload, attribute_pointers, object_pointers = (
        blendquery.script,
        blendquery.reload,
        blendquery.attribute_pointers,
        blendquery.object_pointers,
    )
    if script is not None and reload is True:

        def refresh():
            global script_exception
            script_exception = None
            try:
                locals = parse_script(script.as_string(), attribute_pointers)
                map_attributes(locals, attribute_pointers)
                cadquery_objects = {
                    name: value
                    for name, value in locals.items()
                    if isinstance(
                        value,
                        Union[cadquery.Workplane, cadquery.Shape, cadquery.Assembly],
                    )
                }
                build(cadquery_objects, object_pointers, object)
            except Exception as exception:
                traceback.print_exception(exception)
                script_exception = exception
                # TODO: this stinks :)
                redraw_ui()

        refresh()
        disposers[object] = poll.watch_for_text_changes(script, refresh)
    else:
        if script is None:
            clean(object_pointers)
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
    def update(self, _):
        # TODO: Debounce
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
    attribute_pointers: bpy.props.CollectionProperty(type=AttributePropertyGroup)
    object_pointers: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


installing = False
install_exception = None


class BlendQueryInstallOperator(bpy.types.Operator):
    bl_idname = "blendquery.install"
    bl_label = "Install"
    bl_description = "Installs BlendQuery required dependencies."

    def invoke(self, context, event):
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)

        from .install import install_dependencies, BlendQueryInstallException

        def callback(result):
            if isinstance(result, BlendQueryInstallException):
                global install_exception
                install_exception = result
            else:
                global cadquery
                cadquery = importlib.import_module("cadquery")
            global installing
            installing = False

        global installing, install_exception
        installing = True
        install_exception = None
        pip_executable = os.path.join(
            venv_dir, "Scripts" if os.name == "nt" else "bin", "pip"
        )
        self.thread = install_dependencies(pip_executable, callback)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if not self.thread.is_alive():
            if install_exception:
                self.report({"ERROR"}, str(install_exception))
            context.window_manager.event_timer_remove(self.timer)
            # TODO: this stinks :)
            redraw_ui()
            return {"FINISHED"}
        return {"PASS_THROUGH"}


def redraw_ui():
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


# TODO: Pull UI components into separate functions
class BlendQueryPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_BLENDQUERY_PANEL"
    bl_label = bl_info["name"]
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        if not cadquery:
            box = layout.box()
            box.label(
                icon="INFO",
                text="BlendQuery requires the following dependencies to be installed:",
            )
            box.label(text="    • CadQuery")
            box.label(text="    • Build123d")
            column = box.column()
            column.enabled = not installing
            install_text = (
                "Installing dependencies..." if installing else "Install dependencies"
            )
            column.operator(
                "blendquery.install",
                icon="PACKAGE",
                text=install_text,
            )
            if install_exception is not None:
                box = box.box()
                box.label(
                    icon="ERROR",
                    text="Installation failed. Please see system console for more information.",
                )
            return

        if context.active_object:
            object = context.active_object
            row = layout.row()
            row.prop(object.blendquery, "script")
            row.prop(object.blendquery, "reload")

            if script_exception is not None:
                import re

                traceback_strings = traceback.format_exception(
                    type(script_exception),
                    script_exception,
                    script_exception.__traceback__,
                )
                traceback_text = "".join(traceback_strings)
                pattern = r'File "<string>", line \d+\n([\s\S]*)'
                match = re.search(pattern, traceback_text, re.MULTILINE | re.DOTALL)
                if match:
                    box = layout.box()
                    box.label(
                        icon="ERROR",
                        text="Traceback (most recent call last):",
                    )
                    install_text = match.group(1)
                    lines = install_text.splitlines()
                    for line in lines:
                        print(line)
                        box.label(text=line)

            attributes = [
                attribute
                for attribute in object.blendquery.attribute_pointers
                if attribute.defined
            ]
            if len(attributes) > 0:
                box = layout.box()
                box.label(text="Attributes")
                for attribute in attributes:
                    row = box.row()
                    property = TYPE_TO_PROPERTY[attribute.type]
                    row.prop(attribute, property, text=attribute.key)
