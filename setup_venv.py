import os
import sys
import venv
import platform

def setup_venv():
    if platform.system() == "Windows":
        user_dir = os.environ["USERPROFILE"]
    else:
        user_dir = os.environ["HOME"]
    version_info = sys.version_info
    version_string = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    venv_dir = os.path.join(user_dir, f"blendquery/{version_string}")

    if not os.path.exists(os.path.join(venv_dir, "pyvenv.cfg")):
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(venv_dir)

    sys.path.append(os.path.join(venv_dir, "Lib", "site-packages"))

    return venv_dir
