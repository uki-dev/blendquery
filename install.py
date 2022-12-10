def cadquery():
    try:
        import os
        import sys
        import importlib.util
        dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
        sys.path.append(dir)
        if importlib.util.find_spec('cadquery') is None:
            import subprocess
            executable = os.path.abspath(sys.executable)
            subprocess.call([executable, '-m', 'ensurepip', '--user'])
            subprocess.call([executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
            subprocess.call([executable,'-m', 'pip', 'install', f'--target={dir}', '--pre', 'cadquery'])
        import cadquery
        return cadquery
    except Exception as exception:
        import traceback
        traceback.print_exception(exception)
        return None