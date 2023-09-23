def cadquery():
    try:
        import os
        import sys
        import importlib.util

        dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
        # ensure directory exists before adding it to `sys.path` otherwise the module wont be found after installing
        if not os.path.exists(dir):
            os.makedirs(dir)
        sys.path.append(dir)

        if importlib.util.find_spec("cadquery") is None:
            import subprocess

            executable = os.path.abspath(sys.executable)
            subprocess.run([executable, "-m", "ensurepip", "--user"])
            subprocess.run([executable, "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.run(
                [
                    executable,
                    "-m",
                    "pip",
                    "install",
                    f"--target={dir}",
                    "--pre",
                    "cadquery",
                ]
            )

        import importlib

        cadquery = importlib.import_module("cadquery")
        return cadquery
    except Exception as exception:
        import traceback

        traceback.print_exception(exception)
        return None
