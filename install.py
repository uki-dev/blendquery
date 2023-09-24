import os
import sys
import threading
from typing import Union, Callable


class BlendQueryInstallException(Exception):
    def __init__(self, message):
        super().__init__(message)


def install_dependencies(
    pip_executable: str,
    callback: Callable[
        [Union[BlendQueryInstallException, None]],
        None,
    ],
):
    def install():
        print("install thread")
        executable = os.path.abspath(sys.executable)
        import subprocess

        subprocess.run([executable, "-m", "ensurepip", "--user"])
        subprocess.run([executable, "-m", "pip", "install", "--upgrade", "pip"])
        result = subprocess.run(
            [
                pip_executable,
                "install",
                "--pre",
                "cadquery",
            ]
        )
        if result.returncode == 0:
            print("install succeeded")
            callback(None)
        else:
            print("install failed")
            if result.stderr is not None:
                message = result.stderr.decode()
            if result.stdout is not None:
                message = result.stdout.decode()
            message = "BlendQuery installation failed."
            callback(BlendQueryInstallException(message))

    install_thread = threading.Thread(target=install)
    install_thread.start()
