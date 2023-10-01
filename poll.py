from typing import Callable

import bpy
import os

POLL_RATE = 0.1


def watch_for_text_changes(
    text: bpy.types.Text, callback: Callable, poll_rate: float = POLL_RATE
):
    abs_filepath = bpy.path.abspath(text.filepath, library=text.library)
    last_string = text.as_string()
    last_modified = not text.is_in_memory and os.path.getmtime(abs_filepath) or None

    # TODO: @uki-dev can we pull this outside of this function?
    def timer():
        nonlocal last_string, last_modified
        # Support filepath of text changing
        abs_filepath = bpy.path.abspath(text.filepath, library=text.library)
        # TODO: Find a way to avoid:
        #           - Marking the blend file as having unsaved changes due to hot reloading external file
        #           - Overwriting legitimate local changes when external file is modified
        #       Currently, because we want to load this in the background without `bpy.ops.text.reload`,
        #       we have to read the file from disk natively, and overwrite the texts contents with `from_string`.
        #       This subsequently marks the text as being dirty and modified.
        if not text.is_in_memory:
            # If text is external and it has no local changes, check if it has been modified and `revert` to reload from disk
            modified = os.path.getmtime(abs_filepath)
            if modified > last_modified:
                last_modified = modified
                reload_text(text)

        string = text.as_string()
        if string != last_string:
            last_string = string
            callback()

        return poll_rate

    bpy.app.timers.register(timer)

    def dispose():
        bpy.app.timers.unregister(timer)

    return dispose


def reload_text(text: bpy.types.Text):
    if text.is_in_memory:
        raise ValueError(f"Text object ('{text.name}') is not an external file.")
    abs_filepath = bpy.path.abspath(text.filepath, library=text.library)
    with open(abs_filepath) as file:
        print("reload text: " + abs_filepath)
        text.from_string(file.read())
