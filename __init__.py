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


cadquery = None
build123d = None


def import_dependencies():
    global cadquery, build123d
    global build, Object, parse_script
    cadquery = importlib.import_module("cadquery")
    build123d = importlib.import_module("build123d")
    from .build import build, Object
    from .parse import parse_script


def are_dependencies_installed():
    return (
        importlib.util.find_spec("cadquery") is not None
        and importlib.util.find_spec("build123d") is not None
    )


def register():
    bpy.utils.register_class(AttributePropertyGroup)
    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(BlendQueryPropertyGroup)
    bpy.utils.register_class(BlendQueryInstallOperator)
    bpy.utils.register_class(BlendQueryUpdateOperator)
    bpy.utils.register_class(BlendQueryPanel)
    bpy.types.Object.blendquery = bpy.props.PointerProperty(
        type=BlendQueryPropertyGroup
    )

    setup_venv()

    if are_dependencies_installed():
        import_dependencies()
        bpy.app.handlers.load_post.append(initialise)


def unregister():
    bpy.app.handlers.load_post.remove(initialise)
    bpy.utils.unregister_class(BlendQueryPanel)
    bpy.utils.unregister_class(BlendQueryUpdateOperator)
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
        update(object)


disposers = {}


def update(object):
    blendquery = object.blendquery
    script, reload = (
        blendquery.script,
        blendquery.reload,
    )

    def invoke_operator():
        print("object", object)
        context_override = bpy.context.copy()
        context_override["active_object"] = object
        with bpy.context.temp_override(**context_override):
            bpy.ops.blendquery.update()

    if script is not None and reload is True:
        if not object in disposers:
            invoke_operator()
            # TODO: Debounce
            disposers[object] = poll.watch_for_text_changes(
                script,
                lambda: invoke_operator(),
            )
    elif object in disposers:
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
    def _update(self, _):
        update(self.id_data)

    key: bpy.props.StringProperty()
    type: bpy.props.EnumProperty(
        items=[
            ("bool", "Boolean", "Boolean Type"),
            ("int", "Integer", "Integer Type"),
            ("float", "Float", "Float Type"),
            ("str", "String", "String Type"),
        ],
    )
    bool_value: bpy.props.BoolProperty(update=_update)
    int_value: bpy.props.IntProperty(update=_update)
    float_value: bpy.props.FloatProperty(update=_update)
    str_value: bpy.props.StringProperty(update=_update)
    defined: bpy.props.BoolProperty(default=True)


class ObjectPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class BlendQueryPropertyGroup(bpy.types.PropertyGroup):
    def _update(self, _):
        update(self.id_data)

    script: bpy.props.PointerProperty(
        name="Script", type=bpy.types.Text, update=_update
    )
    reload: bpy.props.BoolProperty(name="Hot Reload", default=True, update=_update)
    attribute_pointers: bpy.props.CollectionProperty(type=AttributePropertyGroup)
    object_pointers: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


class BlendQueryUpdateOperator(bpy.types.Operator):
    bl_idname = "blendquery.update"
    bl_label = "BlendQuery Update"

    object = None

    def modal(self, context, event):
        object = self.object
        blendquery = object.blendquery
        script, attribute_pointers, object_pointers = (
            blendquery.script,
            blendquery.attribute_pointers,
            blendquery.object_pointers,
        )
        try:
            locals = parse_script(script.as_string(), attribute_pointers)
            # map_attributes(locals, attribute_pointers)
            script_objects = {
                name: value
                for name, value in locals.items()
                if isinstance(value, Object)
            }
            build(script_objects, object_pointers, object)
        except Exception as exception:
            import re

            # "ERROR" type opens a input blocking pop-up, so we report using "INFO"
            stack_trace_str = re.search(
                r'File "<string>",\s*(.*(?:\n.*)*)',
                "".join(
                    traceback.format_exception(
                        type(exception),
                        exception,
                        exception.__traceback__,
                    )
                ),
                re.MULTILINE | re.DOTALL,
            ).group(1)
            self.report(
                {"WARNING"},
                f"Failed to generate BlendQuery object: {stack_trace_str}",
            )
            # Info area seems to lag behind so we must force it to redraw
            # TODO: Find a way to avoid this
            redraw_info_area()
        return {"FINISHED"}

    def execute(self, context):
        self.object = context.active_object
        # `self.report` does not seem to work within `execute` or `invoke`, so we call it within `modal`
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


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
                import_dependencies()
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


def redraw_info_area():
    for area in bpy.context.screen.areas:
        if area.type == "INFO":
            area.tag_redraw()


# TODO: Pull UI components into separate functions
class BlendQueryPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_BLENDQUERY_PANEL"
    bl_label = bl_info["name"]
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        if not are_dependencies_installed():
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
