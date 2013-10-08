from __future__ import print_function
import os.path
import sys
import errno
import codecs
import cPickle as pickle
import shutil

__all__ = ['resource_path', 'create_output_path', 'print_status_accessible',
           'PASS', 'FAIL', 'render_template', 'copy_images', 'stash_put',
           'stash_get', 'makedirs_exist_ok', 'print_partial', 'PASS_nl']

# Environment variable which points to the resource library.
_ENV_RESOURCE_PATH = 'RESOURCE_PATH'

def resource_path(*elements):
    "Canonicalize a path relative to the resource library."
    try:
        root_path = os.environ[_ENV_RESOURCE_PATH]
    except KeyError:
        msg = ('The environment variable "%s" must point to the resource '
               'library (the folder containing SignalingPage, '
               'DrugPredictionPage, etc.)' % _ENV_RESOURCE_PATH)
        raise RuntimeError(msg)
    return os.path.abspath(os.path.join(root_path, *elements))

def create_output_path(*elements):
    "Create and canonicalize a path relative to the output directory."
    src_path = os.path.dirname(__file__)
    path = os.path.join(src_path, os.path.pardir, 'output')
    path = os.path.abspath(os.path.join(path, *elements))
    makedirs_exist_ok(path)
    return path

def print_status_accessible(*elements):
    "Print a marker and return a bool reflecting a path's accessibility."
    accessible = os.access(os.path.join(*elements), os.F_OK)
    if accessible:
        PASS()
    else:
        FAIL()
    return accessible

def print_partial(*s):
    "Print to stdout without a terminating newline, and flush."
    print(*s, end='')
    sys.stdout.flush()

def _print_status_inline(s):
    print_partial(s, ' ')  # prints two spaces due to sep=' '

def PASS():
    # 'CHECK MARK'
    _print_status_inline(u'\u2713')

def PASS_nl():
    print(u'\u2713')

def FAIL():
    # 'MULTIPLICATION X'
    _print_status_inline(u'\u2715')

def render_template(template, data, dirname, basename):
    "Render a template with data to a file specified by dirname and basename."
    out_filename = os.path.join(dirname, basename)
    content = template.render(data)
    with codecs.open(out_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)

# TODO Should probably write a simple copy_image and then rename this
# copy_images_parallel or something, implemented using copy_image. The interface
# is baroque for the single-image use case. Also should probably swap d_out,d_in
# in image_dirs for a more logical ordering.
def copy_images(image_dirs, base_filename, source_path, dest_path_elements,
                permissive=False):
    """Copy a set of same-named images in parallel subdirectories.

    permissive: Set this to True if IOErrors should be ignored.

    """
    for d_out, d_in in image_dirs:
        dest_path = list(dest_path_elements) + [d_out]
        image_path = create_output_path(*dest_path)
        source_filename = os.path.join(source_path, d_in, base_filename)
        dest_filename = os.path.join(image_path, base_filename)
        try:
            shutil.copy(source_filename, dest_filename)
        except IOError:
            if permissive:
                pass
            else:
                raise

def stash_put(name, obj):
    "Stash an object by name (to disk) for later retrieval."
    src_path = os.path.dirname(__file__)
    path = os.path.join(src_path, os.path.pardir, 'stash', name + '.pck')
    path = os.path.abspath(path)
    makedirs_exist_ok(os.path.dirname(path))
    pickle_file = open(path, 'w');
    pickle.dump(obj, pickle_file)

def stash_get(name):
    "Retrieve an object from the stash by name."
    src_path = os.path.dirname(__file__)
    path = os.path.join(src_path, os.path.pardir, 'stash', name + '.pck')
    try:
        pickle_file = open(path)
        return pickle.load(pickle_file)
    except (IOError, EOFError, pickle.UnpicklingError, ValueError):
        return None

def makedirs_exist_ok(name):
    try:
        os.makedirs(name)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
