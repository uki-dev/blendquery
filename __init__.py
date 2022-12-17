bl_info = {
    'name': 'BAD × QUERY',
    'blender': (3, 0, 0),
    'category': 'Import-Export',
}

from bpy.app.handlers import persistent
import bpy
import os
import threading 

def register():
    global cadquery
    from . import install
    print('install.cadquery()')
    cadquery = install.cadquery()

    print('dependencies installed', cadquery)

    bpy.utils.register_class(ObjectPointerPropertyGroup)
    bpy.utils.register_class(CadQueryPropertyGroup)
    bpy.utils.register_class(CadQueryPanel)
    bpy.types.Object.cadquery = bpy.props.PointerProperty(type=CadQueryPropertyGroup)
    if cadquery:
        print('register load post')
        bpy.app.handlers.load_post.append(initialise)
        # TODO: `load_post` only runs after loading a scene, but we wish to also load our cadquery objects & set up polling whenever our addon registers
        # TODO: we add a 200ms timeout before setting up the scene to avoid accessing data before blender is ready
        # TODO: lets try find a more reliable way to do this !
        timer = threading.Timer(0.2, initialise)
        timer.start()

def unregister():
    if cadquery:
        bpy.app.handlers.load_post.remove(initialise)
    bpy.utils.unregister_class(CadQueryPanel)
    bpy.utils.unregister_class(CadQueryPropertyGroup)
    bpy.utils.unregister_class(ObjectPointerPropertyGroup)

@persistent
def initialise(_ = None):
    print('intiialise')
    for object in bpy.data.objects:
        update_object(object)

def update_object(object: bpy.types):
    from . import polling
    script = object.cadquery.script
    reload = object.cadquery.reload
    print('update_object')
    if script is not None and reload is True:
        from . import loading
        loading.load(object)
        polling.register(object)
    else:
        polling.unregister(object)

class ObjectPointerPropertyGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)

class CadQueryPropertyGroup(bpy.types.PropertyGroup):
    def update(self, _):
        print('update property', self)
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