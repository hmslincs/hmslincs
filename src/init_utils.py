import os
import os.path as op
import re
import collections as co

import typecheck as tc
import strategy as st
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


def getmodel(appname_and_modelname):
    assert tc.issequence(appname_and_modelname)
    assert len(appname_and_modelname) == 2

    return mo.get_model(*appname_and_modelname)


def readtable(tablesource):

    # tablesource is expected to be a sequence containing the
    # following positional arguments:
    # 1. pathname to xls file (mandatory)
    # 2. name of desired worksheet (mandatory)
    # 3. headers (an int [row number for headers] or a sequence of
    #    strings; optional)
    # 4. dataslice (optional; a slice specification)

    assert tc.issequence(tablesource)
    nargs = len(tablesource)
    assert 2 <= nargs <= 4

    path, sheetname = tablesource[:2]
    sheet = x2p.Workbook(path)[sheetname]

    headers = tablesource[2] if nargs > 2 else 0
    dataslice = tablesource[3] if nargs > 3 else None

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

class _meta(st.strategy):
    def __iter__(this):
        return this._iter()
    
class populate(st.Strategy):
    __metaclass__ = _meta

    SKIP = object()
    NOTFOUND = object()
    MISSINGDATA = object()
    
    def _init(this, target):
        this.model = model = getmodel(target)
        _fields = _getfields(model)
        this._typelookup = dict((f, totype(f)) for f in _fields)
        this._items = tuple((f, f.name) for f in _fields)

    def _execute(this):
        this._populate()

    def _populate(this):
        mapr = this.maprecord
        mo = this.model
        for r in this:
            dbrecord = mo(**mapr(r))
            try:
                dbrecord.save()
            except Exception, e:
                # just a place-holder for a more intelligent handling
                # of database-insert errors in the future
                raise

    def maprecord(this, record):
        mf = this.mapfname
        gv = this.getvalue
        cd = this.convertdata
        ret = {}
        for field, fname in this._items:
            l = mf(fname)
            if l == populate.SKIP: continue
            v = gv(record, l)
            assert fname not in ret
            ret[fname] = cd(field, v)
        return ret

    def convertdata(this, field, value, _typelookup={}):
        if value is populate.MISSINGDATA or value is None:
            return None

        if not _typelookup:
            _typelookup.update(this._typelookup)
            assert _typelookup

        t = _typelookup.get(field, None)

        return value if t is None else t(value)

    def _iter(this):
        return iter(this.records())

    def mapfname(this, fname):
        raise NotImplementedError()

    def records(this):
        raise NotImplementedError()

    def getvalue(this, record, label):
        raise NotImplementedError()

    def _wrapup(this): pass


class populate_from_xls(populate):

    def _init(this, source, target):
        super(populate_from_xls, this)._init(target)
        this._table = table = readtable(source)
        this._labels = labels = table.labels
        this._fnamelookup = dict((to_python_identifier(l.lower()), l)
                                 for l in labels)

    def mapfname(this, fname, _fnamelookup={}):
        if not _fnamelookup:
            _fnamelookup.update(this._fnamelookup)
            assert _fnamelookup
        return _fnamelookup.get(fname, populate.SKIP)

    def records(this):
        return this._table

    def getvalue(this, record, field):
        return (record[field]._value if field in record
                else populate.MISSINGDATA)


class populate_from_sdf(populate):

    def _init(this, source, target, encoding=DEFAULT_ENCODING):
        super(populate_from_sdf, this)._init(target)

        assert tc.isstring(source)
        with open(source) as fh:
            data = fh.read().decode(encoding)

        this._sdfrecords = s2p.parse_sdf(data)

    def records(this):
        return this._sdfrecords

    def getvalue(this, record, field):
        return record.get(field, populate.MISSINGDATA)
