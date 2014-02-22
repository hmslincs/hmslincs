from __future__ import print_function
import os
import os.path as op
import sys
import errno
import codecs
import cPickle as pickle
import shutil
import shell_utils as su
from PIL import Image
from django.template.loader import render_to_string

__all__ = ['resource_path', 'create_output_path', 'print_status_accessible',
           'PASS', 'FAIL', 'render_template', 'copy_images', 'stash_put',
           'stash_get', 'print_partial', 'PASS_nl', 'BASE_URL']

# Environment variable which points to the resource library.
_ENV_RESOURCE_PATH = 'RESOURCE_PATH'

DOCROOT = op.abspath(op.join(op.dirname(__file__), os.pardir,
                             'temp', 'breast_cancer_signaling_output'))
BASE_URL = '/explore/breast_cancer_signaling/'

def resource_path(*elements):
    "Canonicalize a path relative to the resource library."
    try:
        root_path = os.environ[_ENV_RESOURCE_PATH]
    except KeyError:
        msg = ('The environment variable "%s" must point to the resource '
               'library (the folder containing SignalingPage, '
               'DrugPredictionPage, etc.)' % _ENV_RESOURCE_PATH)
        raise RuntimeError(msg)
    return op.abspath(op.join(root_path, *elements))

def create_output_path(*elements):
    "Create and canonicalize a path relative to the output directory."
    path = op.join(DOCROOT, *elements)
    su.mkdirp(path)
    return path

def print_status_accessible(*elements):
    "Print a marker and return a bool reflecting a path's accessibility."
    accessible = os.access(op.join(*elements), os.F_OK)
    if accessible:
        PASS()
    else:
        FAIL()
    return accessible

def print_partial(*s):
    "Print to stdout with space as the terminator, and flush."
    print(*s, end=' ')
    sys.stdout.flush()

def _print_status_inline(s):
    print_partial(s, '')  # prints two spaces due to sep=' '

def PASS():
    # 'CHECK MARK'
    _print_status_inline(u'\u2713')

def PASS_nl():
    print(u'\u2713')

def FAIL():
    # 'MULTIPLICATION X'
    _print_status_inline(u'\u2715')


def render_template(template_name, data, dirname, basename):
    "Render a template with data to a file specified by dirname and basename."
    out_filename = op.join(dirname, basename)
    content = render_to_string(template_name, data)
    with codecs.open(out_filename, 'w', 'utf-8') as out_file:
        out_file.write(content)

# TODO Should probably write a simple copy_image and then rename this
# copy_images_parallel or something, implemented using copy_image. The interface
# is baroque for the single-image use case. Also should probably swap d_out,d_in
# in image_dirs for a more logical ordering.
def copy_images(image_dirs, base_filename, source_path, dest_path_elements,
                permissive=False, new_sizes={}, new_format=None,
                dest_suffix=None, format_options={}):
    """Copy a set of same-named images in parallel subdirectories.

    permissive: Optional, specify True to ignore IOErrors.
    new_sizes: Optional, dict mapping from output directory names in image_dirs
        to 2-tuples with new image dimensions for resizing.
    new_format: Optional, string such as 'jpg' or 'png' to specify a new
        image format. Target filename's extension will be changed to match.
    dest_suffix: Optional, string to be appended to the output filename between
        the root and the extension (e.g. "foo.jpg" -> "foo_suffix.jpg").
    format_options: Optional, dict with options for the encoder used to write
        the output file (see PIL.Image.save's **params argument).

    """
    for d_out, d_in in image_dirs:
        dest_path = list(dest_path_elements) + [d_out]
        image_path = create_output_path(*dest_path)
        source_filename = op.join(source_path, d_in, base_filename)
        dest_filename = op.join(image_path, base_filename)
        if dest_suffix is not None:
            dest_root, dest_ext = os.path.splitext(dest_filename)
            dest_filename = dest_root + dest_suffix + dest_ext
        try:
            # In the simplest case, just do a dumb file copy.
            if d_out not in new_sizes and new_format is None:
                shutil.copy(source_filename, dest_filename)
            # Otherwise we need to parse and rewrite the image.
            else:
                image = Image.open(source_filename)
                size = new_sizes.get(d_out)
                if size is not None:
                    image = image.resize(size, Image.ANTIALIAS)
                if new_format is not None:
                    ext_pos = dest_filename.rindex('.')
                    dest_root = os.path.splitext(dest_filename)[0]
                    dest_filename = dest_root + '.' + new_format
                image.save(dest_filename, **format_options)
        except IOError:
            if permissive:
                pass
            else:
                raise

def _stash_path(name):
    src_path = op.dirname(__file__)
    return op.abspath(op.join(src_path, op.pardir,
                              'temp', 'stash', name + '.pck'))

def stash_put(name, obj):
    "Stash an object by name (to disk) for later retrieval."
    path = _stash_path(name)
    su.mkdirp(op.dirname(path))
    pickle_file = open(path, 'w');
    pickle.dump(obj, pickle_file)

def stash_get(name):
    "Retrieve an object from the stash by name."
    path = _stash_path(name)
    try:
        pickle_file = open(path)
        return pickle.load(pickle_file)
    except (IOError, EOFError, pickle.UnpicklingError, ValueError):
        return None
