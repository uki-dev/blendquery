bl_info = {
    'name': 'BlendQuery',
    'blender': (3, 0, 0),
    'category': 'Parametric',
}

from bpy.app.handlers import persistent
import bpy

def register():
    global cadquery
    from . import install
    cadquery = install.cadquery()
    bpy.utils.register_class(ObjectPointerPropertyGroup)
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
    bpy.utils.unregister_class(ObjectPointerPropertyGroup)

@persistent
def initialise(_ = None):
    for object in bpy.data.objects:
        update_object(object)

def update_object(object: bpy.types.Object):
    from . import polling
    from . import loading
    script = object.cadquery.script
    reload = object.cadquery.reload
    if script is not None and reload is True:
        loading.load(object)
        polling.register(object)
    else:
        if script is None:
            # clean up previously generated objects if script is removed
            loading.unload(object)
        polling.unregister(object)

class ObjectPointerPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)

class CadQueryPropertyGroup(bpy.types.PropertyGroup):
    def update(self, _):
        update_object(self.id_data)
    script: bpy.props.PointerProperty(name='Script', type=bpy.types.Text, update=update)
    reload: bpy.props.BoolProperty(name='Hot Reload', default=True, update=update)
    pointers: bpy.props.CollectionProperty(type=ObjectPointerPropertyGroup)

class CadQueryPanel(bpy.types.Panel):
    bl_idname = 'OBJECT_PT_CAD_QUERY'
    bl_label = bl_info['name']
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    def draw(self, context):
        layout = self.layout
        if not cadquery:
            box = layout.box()
            box.label(text='Failed to install dependencies; See system console.', icon='ERROR')
        column = layout.row()
        column.enabled = cadquery is not None
        if len(context.selected_objects) > 0:
            object = context.selected_objects[0]
            column.prop(object.cadquery, 'script')
            column.prop(object.cadquery, 'reload')