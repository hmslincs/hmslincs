from __future__ import print_function
import os.path

__all__ = ['resource_path', 'create_output_path', 'print_status_accessible',
           'PASS', 'FAIL']

# Environment variable which points to the resource library.
ENV_RESOURCE_PATH = 'RESOURCE_PATH'

def resource_path(*elements):
    "Return an absolute path for a path within the resource library"
    try:
        root_path = os.environ[ENV_RESOURCE_PATH]
    except KeyError:
        msg = ('The environment variable "%s" must point to the resource '
               'library (the folder containing SignalingPage, '
               'DrugPredictionPage, etc.)' % ENV_RESOURCE_PATH)
        raise RuntimeError(msg)
    return os.path.abspath(os.path.join(root_path, *elements))

def create_output_path(*elements):
    "Create and return an absolute path for a path within the output directory"
    src_path = os.path.dirname(__file__)
    path = os.path.join(src_path, os.path.pardir, 'output')
    path = os.path.abspath(os.path.join(path, *elements))
    try:
        os.makedirs(path)
    except OSError as e:
        # pass only if error is EEXIST
        if e.errno != 17:
            raise
    return path

def print_status_accessible(*elements):
    accessible = os.access(os.path.join(*elements), os.F_OK)
    if accessible:
        PASS()
    else:
        FAIL()
    return accessible

def _print_status_inline(s):
    print(s, ' ', end='')

def PASS():
    # 'CHECK MARK'
    _print_status_inline(u'\u2713')

def FAIL():
    # 'MULTIPLICATION X'
    _print_status_inline(u'\u2715')
