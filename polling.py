from . import loading
import bpy
import os

POLL_RATE = 0.1

_registry = {}
def register(object: bpy.types.Object, poll_rate = POLL_RATE):
    global _registry
    if object in _registry:
        return _registry[object]
    
    script = object.cadquery.script
    last_string = script.as_string()
    last_modified = not script.is_in_memory and os.path.getmtime(script.filepath) or None
    def timer():
        nonlocal last_string, last_modified

        if not script.is_in_memory:
            modified = os.path.getmtime(script.filepath)
            if modified > last_modified:
                last_modified = modified
                reload_text(script)

        string = script.as_string()
        if string != last_string:
            last_string = string
            # TODO dependency inject this call?
            loading.load(object) 
        
        return poll_rate

    bpy.app.timers.register(timer)

    def unregister(): 
        bpy.app.timers.unregister(timer)
        del _registry[object]

    _registry[object] = unregister
    
    return unregister

def unregister(object: bpy.types.Object):
    global _registry
    if object in _registry:
        _registry[object]()

def reload_text(script: bpy.types.Text):
    if script.filepath == '' or not os.path.exists(script.filepath):
        return

    with open(script.filepath) as file:
        script.from_string(file.read())