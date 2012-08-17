import os
_initdir = os.getcwd()
import os.path as op
import sys

_scriptdir = op.abspath(op.dirname(__file__))
_djangodir = op.realpath(op.join(_scriptdir, '../django'))
os.chdir(_djangodir)
sys.path.insert(0, _djangodir)
sys.path.insert(0, _scriptdir)
del _scriptdir, _djangodir

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hmslincs_server.settings")

import re
import platform as pl
import django.db.models as mo
import django.db.models.fields as fl

import xls2py as xl

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    FIELDDELIMITER = unichr(28),
    RECORDDELIMITER = u'\r\n' if pl.system == 'Windows' else u'\n',
    VERBOSE = False,
    ENCODING = u'utf8',
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------

assert len(FIELDDELIMITER) > 0
assert len(RECORDDELIMITER) > 0

FIELDDELIMITER = FIELDDELIMITER.encode(ENCODING)
RECORDDELIMITER = RECORDDELIMITER.encode(ENCODING)

assert RECORDDELIMITER != FIELDDELIMITER

# ---------------------------------------------------------------------------

def _abspath(path):
    return path if op.isabs(path) else op.join(_initdir, path)

def populate(model, inputtable):
    pass

def read_workbook(path,
                  fielddelimiter=FIELDDELIMITER,
                  recorddelimiter=RECORDDELIMITER):

    return xl.Workbook(path,
                       fielddelimiter=fielddelimiter,
                       recorddelimiter=recorddelimiter)

def totype(field):
    if isinstance(field, fl.CharField) or isinstance(field, fl.TextField):
        return unicode
    if isinstance(field, fl.IntegerField):
        return int
    if isinstance(field, fl.AutoField):
        return None

    assert False, '(as yet) unsupported field class: %s (%s)' % (type(field).__name__, type(field))

def fix(header, _nowsre=re.compile(ur'\s+')):
    return _nowsre.sub('_', unicode(header).strip())

def main(path, sheet_id, modelname,
         dataslice=slice(1, None), header_row_num=0,
         app=APPNAME):

    model = mo.get_model(app, modelname)
    fields = [f for f in model._meta.fields if not isinstance(f, fl.AutoField)]

    sheet = read_workbook(path)[sheet_id]
    header = tuple([fix(h) for h in sheet[header_row_num]])

    types = tuple([totype(f) for f in fields])
    input_table = sheet.as_table(dataslice=dataslice, header=header,
                                 types=types)

    labels = [l.lower() for l in input_table.labels]

    assert len(labels) == len(fields)

    for label, field in zip(labels, fields):
        assert label == field.name

    for i, row in enumerate(input_table):
        kw = dict(zip(labels, (cell._value for cell in row)))
        record = model(**kw)
        try:
            record.save()
        except Exception, e:
            print 'row %d: %s' % (i, str(e))
            for j, label in enumerate(labels):
                f = fields[j]
                maxlen = getattr(f, 'max_length', None)
                val = kw[label]
                pfx = '*' if maxlen is not None and val is not None and len(str(val)) >= maxlen else ' '
                        
                print '%s %s: %s (%s %s)' % (pfx, label, str(val)[:30], '*' if val is None else len(str(val)), '*' if maxlen is None else maxlen)
            exit(1)

            # import traceback as tb
            # tb.print_exc()


if __name__ == '__main__':
    nargs = len(sys.argv) - 1

    assert 3 <= nargs <= 4

    path, sheet_id, modelname = sys.argv[1:4]
    try:
        header_row_num = int(sys.argv[4])
    except IndexError:
        header_row_num = 0

    dataslice = slice(header_row_num + 1, None)

    main(_abspath(path), sheet_id, modelname, dataslice=dataslice,
         header_row_num=header_row_num)
