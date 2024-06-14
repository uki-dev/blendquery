bl_info = {
    "name": "BlendQuery",
    "blender": (3, 0, 0),
    "category": "Parametric",
}

RELOAD_DEBOUNCE_S = 1.0

import os
import re
import sys
import traceback
import importlib
import importlib.util

import bpy
from bpy.app.handlers import persistent

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from setup_venv import setup_venv
venv_dir = setup_venv()

from poll import watch_for_text_changes

cadquery = None
build123d = None

# TODO: Find a better way to store/reset
are_dependencies_installed = False

def statusbar_progress_bar(self, context):
    if bpy.context.window_manager.blendquery.is_regenerating:
        layout = self.layout
        row = layout.row()
        row.progress(
            text="Regenerating BlendQuery Objects",
            factor=bpy.context.window_manager.blendquery.regeneration_progress,
            type="BAR",
        )
        row.scale_x = 4


def register():
    bpy.utils.register_class(ObjectPropertyGroup)
    bpy.utils.register_class(BlendQueryPropertyGroup)
    bpy.utils.register_class(BlendQueryImportDependenciesOperator)
    bpy.utils.register_class(BlendQueryInstallOperator)
    bpy.utils.register_class(BlendQueryRegenerateOperator)
    bpy.utils.register_class(BlendQueryPanel)
    bpy.utils.register_class(BlendQueryWindowPropertyGroup)
    bpy.types.WindowManager.blendquery = bpy.props.PointerProperty(
        type=BlendQueryWindowPropertyGroup
    )
    bpy.types.Object.blendquery = bpy.props.PointerProperty(
        type=BlendQueryPropertyGroup
    )

    bpy.app.handlers.load_post.append(initialise)
    bpy.types.STATUSBAR_HT_header.append(statusbar_progress_bar)


def unregister():
    try:
        bpy.types.STATUSBAR_HT_header.remove(statusbar_progress_bar)
        bpy.app.handlers.load_post.remove(initialise)
    except:
        pass
    
    del bpy.types.Object.blendquery
    del bpy.types.WindowManager.blendquery
    bpy.utils.unregister_class(BlendQueryPanel)
    bpy.utils.unregister_class(BlendQueryWindowPropertyGroup)
    bpy.utils.unregister_class(BlendQueryRegenerateOperator)
    bpy.utils.unregister_class(BlendQueryInstallOperator)
    bpy.utils.unregister_class(BlendQueryImportDependenciesOperator)
    bpy.utils.unregister_class(BlendQueryPropertyGroup)
    bpy.utils.unregister_class(ObjectPropertyGroup)


@persistent
def initialise(_=None):
    bpy.ops.blendquery.import_dependencies()
    if not are_dependencies_installed:
        return
    
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

    if script is not None and reload is True:
        if not object in disposers:
            from debounce import debounce

            def invoke_update_operator():
                context_override = bpy.context.copy()
                context_override["active_object"] = object
                with bpy.context.temp_override(**context_override):
                    bpy.ops.blendquery.regenerate()

            invoke_update_operator()
            disposers[object] = watch_for_text_changes(
                script,
                debounce(RELOAD_DEBOUNCE_S)(invoke_update_operator),
            )
    elif object in disposers:
        disposer = disposers[object]
        if callable(disposer):
            disposer()


class ObjectPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)


class BlendQueryPropertyGroup(bpy.types.PropertyGroup):
    def _update(self, _):
        update(self.id_data)

    script: bpy.props.PointerProperty(
        name="Script", type=bpy.types.Text, update=_update
    )
    reload: bpy.props.BoolProperty(name="Automatic Regeneration", default=True, update=_update)
    object_pointers: bpy.props.CollectionProperty(type=ObjectPropertyGroup)


def ui_update(self, context):
    for region in context.area.regions:
        if region.type == "UI":
            region.tag_redraw()
    return None


class BlendQueryWindowPropertyGroup(bpy.types.PropertyGroup):
    # TODO: Find a better way to store/reset
    # TODO: can we also use the `ui_update` here and for other properties?
    installing_dependencies: bpy.props.BoolProperty(
        name="Installing",
        default=False,
        description="Whether BlendQuery is installing dependencies",
    )

    is_regenerating: bpy.props.BoolProperty(
        update=ui_update
        )
    regeneration_progress: bpy.props.FloatProperty(
        update=ui_update
    )


class BlendQueryImportDependenciesOperator(bpy.types.Operator):
    bl_idname = "blendquery.import_dependencies"
    bl_label = "BlendQuery Import Dependecies"

    import_error = None

    def execute(self, context):
        global are_dependencies_installed
        try:
            global cadquery, build123d
            global regenerate_blendquery_object
            cadquery = importlib.import_module("cadquery")
            build123d = importlib.import_module("build123d")
            from .blendquery import regenerate_blendquery_object
            are_dependencies_installed = True
        except Exception:
            are_dependencies_installed = False
            exception_trace = traceback.format_exc()
            self.import_error = f"Failed to import BlendQuery dependencies: {exception_trace}"

        # `self.report` does not seem to work within `execute` or `invoke`, so we call it within `modal`
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        if self.import_error is not None:
            self.report(
                {"WARNING"},
                self.import_error,
            )
            # Info area seems to lag behind so we must force it to redraw
            # TODO: Find a way to avoid this
            redraw_info_area()
        return {"FINISHED"}


def create_parse_parametric_script_thread(script: str):
    import threading, subprocess, queue, pickle
    response = queue.Queue()

    def process():
        cwd = os.path.dirname(os.path.abspath(__file__))
        parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env = os.environ.copy()
        env['PATH'] = parent_directory
        process = subprocess.Popen([sys.executable, 'parse.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env)
        process.stdin.write(pickle.dumps(script))
        process.stdin.close()

        stdout_data = process.stdout.read();
        response.put(pickle.loads(stdout_data))

        # TODO: Investigate return code issue.
        # if process.returncode == 0:
        #     response.put(process.stdout.read().decode('utf-8'))
        # else:
        #     exception = process.stdout.read().decode('utf-8')
        #     error_output = process.stderr.read().decode('utf-8')
        #     response.put(RuntimeError("Subprocess failed with return code {}; {}; {}".format(process.returncode, error_output, exception)))

    thread = threading.Thread(target=process)
    thread.start()
    return thread, response

regenerate_operators = []

def update_regeneration_progress():
    bpy.context.window_manager.blendquery.is_regenerating = len(regenerate_operators) > 0
    bpy.context.window_manager.blendquery.regeneration_progress = 1 / (len(regenerate_operators) + 1)

class BlendQueryRegenerateOperator(bpy.types.Operator):
    bl_idname = "blendquery.regenerate"
    bl_label = "BlendQuery Regenerate"

    # `execute` is required in order to call this operator via `bpy.ops.blendquery.regenerate()`
    # (self, context) must be present in order to register modal operator in Blender
    def execute(self, context):
        self.object = context.active_object
        # TODO: kill any existing threads for this `context.active_object`
        self.thread, self.response = create_parse_parametric_script_thread(self.object.blendquery.script.as_string())

        # `self.report` does not seem to work within `execute` or `invoke`, so we call it within `modal`
        regenerate_operators.append(self)
        update_regeneration_progress()
   
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
    
        # (self, context, event) must be present in order to register modal operator in Blender
    def modal(self, context, event):
        if self.thread.is_alive():
            return {"PASS_THROUGH"}
        
        response = self.response.get()
        if isinstance(response, Exception):
            self.report_exception(response)
        else:
            regenerate_blendquery_object(response, self.object, self.object.blendquery.object_pointers)
        
        regenerate_operators.remove(self)
        update_regeneration_progress()

        context.window_manager.event_timer_remove(self.timer)


        return {"FINISHED"}

    def report_exception(self, exception):
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
        # "ERROR" type opens an input blocking pop-up, so we report using "WARNING"
        self.report(
            {"WARNING"},
            f"Failed to regenerate BlendQuery object: {script_error and script_error.group(1) or stack_trace}",
        )
        # Info area seems to lag behind so we must force it to redraw
        # TODO: Find a way to avoid this
        redraw_info_area()


class BlendQueryInstallOperator(bpy.types.Operator):
    bl_idname = "blendquery.install"
    bl_label = "Install"
    bl_description = "Installs BlendQuery required dependencies."

    exception = None

    # (self, context, event) must be present in order to register a modal operator in Blender
    def invoke(self, context, event):
        from install import install_dependencies, BlendQueryInstallException

        def callback(result):
            if isinstance(result, BlendQueryInstallException):
                self.exception = result

        # TODO: this can probably be moved into `install_dependencies` with the new `venv.py` file
        pip_executable = os.path.join(
            venv_dir, "Scripts" if os.name == "nt" else "bin", "pip"
        )
        self.thread = install_dependencies(pip_executable, callback)

        # `self.report` does not seem to work within `execute` or `invoke`, so we call it within `modal`
        self.timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        context.window_manager.blendquery.installing_dependencies = True
        return {"RUNNING_MODAL"}

    # (self, context, event) must be present in order to register a modal operator in Blender
    def modal(self, context, event):
        if not self.thread.is_alive():
            if self.exception:
                self.report(
                    {"WARNING"},
                    f"Failed to install BlendQuery dependencies: {self.exception}",
                )
                # Info area seems to lag behind so we must force it to redraw
                # TODO: Find a way to avoid this
                redraw_info_area()
            else:
                initialise()

            context.window_manager.blendquery.installing_dependencies = False
            context.window_manager.event_timer_remove(self.timer)
            # Setting `installing_dependencies` here doesn't seem to redraw the UI despite it being a property group so we must force it to redraw
            # TODO: Find a way to avoid this
            redraw_ui()
            return {"FINISHED"}
        return {"PASS_THROUGH"}


# TODO: Pull UI components into separate functions
class BlendQueryPanel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_BLENDQUERY_PANEL"
    bl_label = bl_info["name"]
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        if are_dependencies_installed:
            self.installed(layout, context)
        else:
            self.not_installed(layout, context)

    def installed(self, layout, context):
        if context.active_object:
            object = context.active_object
            column = layout.column()
            column.prop(object.blendquery, "script")
            column.separator(factor=0.5)
            row = column.row()
            row.prop(object.blendquery, "reload")
            row.operator("blendquery.regenerate", text="Regenerate")
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


def redraw_ui():
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


def redraw_info_area():
    for area in bpy.context.screen.areas:
        if area.type == "INFO":
            area.tag_redraw()
