import os
import os.path as op
import re
import collections as co

# ---------------------------------------------------------------------------

DEFAULT_ENCODING = 'utf8'

# ---------------------------------------------------------------------------

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

import xls2py as x2p
import sdf2py as s2p

# def check_record(fields, labels, data, row=None, exc=None):
#     if exc:
#         pfx = '' if row is None else 'row %d: ' % row
#         print '%s%s' % (pfx, str(exc))

#     for j, label in enumerate(labels):
#         f = fields[j]
#         maxlen = getattr(f, 'max_length', None)
#         val = data[label]
#         pfx = '*' if (maxlen is not None and
#                       val is not None and
#                       len(str(val)) >= maxlen) else ' '
                
#         print '%s %s: %s (%s %s)' % (pfx, label, str(val)[:30],
#                                      '*' if val is None else len(str(val)),
#                                      '*' if maxlen is None else maxlen)
                                         

def totype(field):
    if isinstance(field, fl.CharField) or isinstance(field, fl.TextField):
        return unicode
    if isinstance(field, fl.IntegerField):
        return int
    if isinstance(field, fl.AutoField):
        return None

    assert False, ('(as yet) unsupported field class: %s (%s)'
                   % (type(field).__name__, type(field)))


def readtable(path, sheetname, headers=0, dataslice=None):
    sheet = x2p.Workbook(path)[sheetname]

    if isinstance(headers, int):
        labels = tuple(unicode(cell) for cell in sheet[headers])
        first_data_row = headers + 1
    else:
        labels = headers
        first_data_row = 0

    if dataslice is None:
        data = sheet[first_data_row:]
    else:
        data = sheet[dataslice]

    return x2p.Table(data, labels)


def to_python_identifier(header, _fixre=re.compile(ur'(?:^(?=\d)|\W+)')):
    return _fixre.sub('_', unicode(header).strip())


def _getfields(model):
    return tuple(model._meta.fields)

# -----------------------------------------------------------------------------

class _meta(type):
    def __new__(mcls, name, bases, dct, _functype=type(lambda: 0)):
        for k, v in dct.items():
            if isinstance(v, _functype): dct[k] = classmethod(v)

        return super(_meta, mcls).__new__(mcls, name, bases, dct)

    def __call__(this, *args, **kwargs):
        this._init(*args, **kwargs)
        this._populate()


class populate(object):
    __metaclass__ = _meta

    SKIP = object()
    NOTFOUND = object()
    MISSINGDATA = object()
    
    def _init(this, appname, modelname):
        this.model = model = mo.get_model(appname, modelname)
        this._fields = _fields = _getfields(model)
        this._typelookup = dict((f, totype(f)) for f in _fields)
        this._items = _items = tuple((f.name, f, totype(f)) for f in _fields)

    def _populate(this):
        mapr = this.maprecord
        mo = this.model

        for r in this.records():
            dbrecord = mo(**mapr(r))
            try:
                dbrecord.save()
            except Exception, e:
                # just a place-holder for a more intelligent handling
                # of database-insert errors in the future
                raise

    def maprecord(this, record, _items=[]):
        if not _items:
            _items.extend(this._items)
            assert _items
        mk = this.mapkey
        gv = this.getvalue
        cd = this.convertdata
        ret = {}
        for k, f, t in _items:
            l = mk(k)
            if l == populate.SKIP: continue
            v = gv(record, l)
            ret[k] = cd(f, v)
        return ret

    def convertdata(this, field, value, _lookup={}):
        if value is populate.MISSINGDATA or value is None:
            return None

        if not _lookup:
            _lookup.update(this._typelookup)
            assert _lookup

        t = _lookup.get(field, None)

        return value if t is None else t(value)


class populate_from_xls(populate):

    def _init(this, appname, modelname,
              path, sheetname, headers=0, dataslice=None):

        super(populate_from_xls, this)._init(appname, modelname)

        table = readtable(path, sheetname, headers, dataslice)
        this._labels = labels = table.labels
        this._records = table
        this._keymap = dict((to_python_identifier(l.lower()), l) for l in labels)

        return this

    def mapkey(this, key, _lookup={}):
        if not _lookup:
            _lookup.update(this._keymap)
            assert _lookup
        return _lookup.get(key, populate.SKIP)

    def records(this):
        return this._records

    def getvalue(this, record, field):
        return (record[field]._value if field in record
                else populate.MISSINGDATA)


class populate_from_sdf(populate):
    def _init(this, appname, modelname, path, encoding=DEFAULT_ENCODING):
        super(populate_from_sdf, this)._init(appname, modelname)

        with open(path) as fh:
            data = fh.read().decode(encoding)

        this._records = s2p.parse_sdf(data)
        return this

    def records(this):
        return this._records

    def getvalue(this, record, field):
        return record.get(field, populate.MISSINGDATA)
