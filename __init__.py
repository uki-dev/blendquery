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
    global parse, build, Object
    cadquery = importlib.import_module("cadquery")
    build123d = importlib.import_module("build123d")
    from .blendquery import parse, build, Object


def are_dependencies_installed():
    return (
        importlib.util.find_spec("cadquery") is not None
        and importlib.util.find_spec("build123d") is not None
    )


def register():
    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(BlendQueryPropertyGroup)
    bpy.utils.register_class(BlendQueryInstallOperator)
    bpy.utils.register_class(BlendQueryUpdateOperator)
    bpy.utils.register_class(BlendQueryPanel)
    bpy.utils.register_class(BlendQueryWindowPropertyGroup)
    bpy.types.WindowManager.blendquery = bpy.props.PointerProperty(
        type=BlendQueryWindowPropertyGroup
    )
    bpy.types.Object.blendquery = bpy.props.PointerProperty(
        type=BlendQueryPropertyGroup
    )

    setup_venv()

    if are_dependencies_installed():
        import_dependencies()
        bpy.app.handlers.load_post.append(initialise_scene)


def unregister():
    bpy.app.handlers.load_post.remove(initialise_scene)
    del bpy.types.Object.blendquery
    del bpy.types.WindowManager.blendquery
    bpy.utils.unregister_class(BlendQueryWindowPropertyGroup)
    bpy.utils.unregister_class(BlendQueryPanel)
    bpy.utils.unregister_class(BlendQueryUpdateOperator)
    bpy.utils.unregister_class(BlendQueryInstallOperator)
    bpy.utils.unregister_class(BlendQueryPropertyGroup)
    bpy.utils.unregister_class(ObjectPropertyGroup)


@persistent
def initialise_scene(_=None):
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


class BlendQueryWindowPropertyGroup(bpy.types.PropertyGroup):
    installing_dependencies: bpy.props.BoolProperty(
        name="Installing",
        default=False,
        description="Whether BlendQuery is installing dependencies",
    )


class ObjectPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class BlendQueryPropertyGroup(bpy.types.PropertyGroup):
    def _update(self, _):
        update(self.id_data)

    script: bpy.props.PointerProperty(
        name="Script", type=bpy.types.Text, update=_update
    )
    reload: bpy.props.BoolProperty(name="Hot Reload", default=True, update=_update)
    object_pointers: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


class BlendQueryUpdateOperator(bpy.types.Operator):
    bl_idname = "blendquery.update"
    bl_label = "BlendQuery Update"

    object = None

    def modal(self, context, event):
        object = self.object
        blendquery = object.blendquery
        script, object_pointers = (
            blendquery.script,
            blendquery.object_pointers,
        )
        try:
            locals = parse(script.as_string())
            script_objects = {
                name: value
                for name, value in locals.items()
                if isinstance(value, Object)
            }
            build(script_objects, object_pointers, object)
        except Exception as exception:
            import re

            stack_trace = "".join(
                traceback.format_exception(
                    type(exception),
                    exception,
                    exception.__traceback__,
                )
            )
            script_error = re.search(
                r'File "<string>",\s*(.*(?:\n.*)*)',
                stack_trace,
                re.MULTILINE | re.DOTALL,
            )
            # "ERROR" type opens a input blocking pop-up, so we report using "WARNING"
            self.report(
                {"WARNING"},
                f"Failed to generate BlendQuery object: {script_error and script_error.group(1) or stack_trace}",
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


class BlendQueryInstallOperator(bpy.types.Operator):
    bl_idname = "blendquery.install"
    bl_label = "Install"
    bl_description = "Installs BlendQuery required dependencies."

    exception = None

    def invoke(self, context, event):
        # `self.report` does not seem to work within `execute` or `invoke`, so we call it within `modal`
        # In this case it makes slightly more sense because installing is quite an async action
        context.window_manager.modal_handler_add(self)
        context.window_manager.blendquery.installing_dependencies = True

        from .install import install_dependencies, BlendQueryInstallException

        def callback(result):
            if isinstance(result, BlendQueryInstallException):
                self.exception = result

        pip_executable = os.path.join(
            venv_dir, "Scripts" if os.name == "nt" else "bin", "pip"
        )
        self.thread = install_dependencies(pip_executable, callback)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if not self.thread.is_alive():
            context.window_manager.blendquery.installing_dependencies = False
            if self.exception:
                self.report(
                    {"WARNING"},
                    f"Failed to install BlendQuery dependencies: {self.exception}",
                )
                # Info area seems to lag behind so we must force it to redraw
                # TODO: Find a way to avoid this
                redraw_info_area()
            else:
                import_dependencies()
                initialise_scene()

            # Setting `installing_dependencies` here doesn't seem to redraw the UI despite it being a property group so we must force it to redraw
            # TODO: Find a way to avoid this
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
        if are_dependencies_installed():
            self.installed(layout, context)
        else:
            self.not_installed(layout, context)

    def installed(self, layout, context):
        if context.active_object:
            object = context.active_object
            row = layout.row()
            row.prop(object.blendquery, "script")
            row.prop(object.blendquery, "reload")

    def not_installed(self, layout, context):
        box = layout.box()
        box.label(
            icon="INFO",
            text="BlendQuery requires the following dependencies to be installed:",
        )
        box.label(text="    • CadQuery")
        box.label(text="    • Build123d")
        column = box.column()
        if context.window_manager.blendquery.installing_dependencies:
            column.enabled = False
            column.operator(
                "blendquery.install",
                icon="PACKAGE",
                text="Installing dependencies...",
            )
        else:
            column.operator(
                "blendquery.install",
                icon="PACKAGE",
                text="Install dependencies",
            )
