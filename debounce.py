import bpy
import functools


def debounce(duration):
    def decorator(func):
        @functools.wraps(func)
        def debounced(*args, **kwargs):
            debounced._args = args
            debounced._kwargs = kwargs
            if bpy.app.timers.is_registered(debounced._invoke):
                bpy.app.timers.unregister(debounced._invoke)
            bpy.app.timers.register(
                debounced._invoke, first_interval=duration, persistent=False
            )

        debounced._invoke = lambda: func(*debounced._args, **debounced._kwargs)
        return debounced

    return decorator
