import os
import os.path as op
import re

#------------------------------------------------------------------------------
# ugly kluge: to be eliminated once this module lives under some
# django/app/management directory

_mydir = op.abspath(op.dirname(__file__))
_djangodir = op.normpath(op.join(_mydir, '../django'))
import sys
sys.path.insert(0, _djangodir)
sys.path.insert(0, _mydir)

import chdir as cd
with cd.chdir(_djangodir):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hmslincs_server.settings')
    import django.db.models as models
    import django.db.models.fields as fields
del _mydir, _djangodir
mo = models
fl = fields
#------------------------------------------------------------------------------

# def _abspath(path, _initdir=os.getcwd()):
#     return path if op.isabs(path) else op.join(_initdir, path)

def totype(field):
    if isinstance(field, fl.CharField) or isinstance(field, fl.TextField):
        return unicode
    if isinstance(field, fl.IntegerField):
        return int
    if isinstance(field, fl.AutoField):
        return None

    assert False, ('(as yet) unsupported field class: %s (%s)'
                   % (type(field).__name__, type(field)))



def check_record(fields, labels, data, row=None, exc=None):
    if exc:
        pfx = '' if row is None else 'row %d: ' % row
        print '%s%s' % (pfx, str(exc))

    for j, label in enumerate(labels):
        f = fields[j]
        maxlen = getattr(f, 'max_length', None)
        val = data[label]
        pfx = '*' if (maxlen is not None and
                      val is not None and
                      len(str(val)) >= maxlen) else ' '
                
        print '%s %s: %s (%s %s)' % (pfx, label, str(val)[:30],
                                     '*' if val is None else len(str(val)),
                                     '*' if maxlen is None else maxlen)
                                         

def populate(model, inputtable):
    pass

def read_workbook(path):
    return xl.Workbook(path)

def to_python_identifier(header, _fixre=re.compile(ur'(?:^(?=\d)|\W+)')):
    return _fixre.sub('_', unicode(header).strip())
