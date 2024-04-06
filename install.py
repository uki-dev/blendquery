import os
import sys
import threading
from typing import Union, Callable


class BlendQueryInstallException(Exception):
    def __init__(self, message):
        super().__init__(message)


def install_dependencies(
    pip_executable: str,
    # TODO: @uki-dev change to `queue.Queue`
    callback: Callable[
        [Union[BlendQueryInstallException, None]],
        None,
    ],
):
    def install():
        import subprocess

        result = subprocess.run(
            [
                pip_executable,
                "install",
                "--pre",
                "cadquery",
                "git+https://github.com/gumyr/build123d",
            ],
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            callback(None)
        else:
            callback(BlendQueryInstallException(result.stderr.decode()))

    thread = threading.Thread(target=install)
    thread.start()
    return thread
