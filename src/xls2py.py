# -*- coding: utf-8 -*-
import xlrd as xl
import platform as pl
import os
import os.path as op
import errno as er
import csv
# import functools as ft

try:
    from typecheck import isstring, isiterable #, ismapping
except ImportError, e:
    print str(e)
    def isstring(x):
        return isinstance(x, basestring)

    def isiterable(x):
        try: iter(x)
        except TypeError: return False
        else: return True

    # def ismapping(x):
    #     return hasattr(x, 'items')
    

FIELDDELIMITER = u','
RECORDDELIMITER = u'\r\n' if pl.system == 'Windows' else u'\n'
VERBOSE = False
ENCODING = 'utf8'

if __name__ == '__main__':
    DEFAULTS = dict(
        FIELDDELIMITER = u',',
        RECORDDELIMITER = u'\r\n' if pl.system == 'Windows' else u'\n',
        VERBOSE = False,
        ENCODING = 'utf8',
    )

    def _param(name, env=os.environ, defaults=DEFAULTS):
        assert defaults.has_key(name)
        return env.get(name, defaults[name])

    def _update_globals(defaults=DEFAULTS, globs=globals(),
                        _env=os.environ,
                        _verbose=_param('VERBOSE'),
                        _enc=_param('ENCODING')):

        for k, v in defaults.items():
            if k in _env:
                val = unicode(_env[k])
                if len(val):
                    if _verbose:
                        print (u'found: %s=%r' % (k, val)).encode(_enc)
                    globs[k] = val
                    continue
            globs[k] = v

    _update_globals()
    del _param, _update_globals


assert len(FIELDDELIMITER) > 0
assert len(RECORDDELIMITER) > 0

FIELDDELIMITER = FIELDDELIMITER.encode(ENCODING)
RECORDDELIMITER = RECORDDELIMITER.encode(ENCODING)

assert RECORDDELIMITER != FIELDDELIMITER

# ---------------------------------------------------------------------------

def _tolist(x):
    return [_tolist(i) for i in x] if isiterable(x) else x

def _makedirs(path):
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != er.EEXIST: raise

class _encodable(object):
    def __str__(self):
        return self.__unicode__().encode(ENCODING)



BREAKPOINT = None
class Cell(_encodable):
    def __init__(self, data, parent):
        self._value = data
        self.parent = parent
        self.fielddelimiter = parent.fielddelimiter

    def __unicode__(self):
        return unicode(self._value)


class Row(_encodable):
    def __init__(self, data, parent):
        self.parent = parent
        self.fielddelimiter = parent.fielddelimiter
        self._cells = _c = tuple([Cell(c, parent= self) for c in data])
        self._len = len(_c)

    def __iter__(self):
        return iter(self._cells)

    def __unicode__(self):
        return self.fielddelimiter.join([unicode(s)
                                         for s in self._cells])

    def __len__(self):
        return self._len


class Worksheet(_encodable):
    def __init__(self, data, parent, name=None):
        self.parent = parent
        if name is None:
            if hasattr(data, 'name'):
                name = data.name
            else:
                raise TypeError('No name for worksheet')
        self.name = name

        self.fielddelimiter = parent.fielddelimiter
        self.recorddelimiter = parent.recorddelimiter

        # # ASPIRATIONAL
        # if data is None:
        #     _data = []
        # elif isinstance(data, xl.sheet.Sheet):
        #     _data = (data.row_values(i) for i in range(data.nrows))
        # elif isiterable(data):
        #     _data = data
        # else:
        #     raise TypeError('invalid type for data argument to %s constructor' %
        #                     type(self).__name__)

        _data = (data.row_values(i) for i in range(data.nrows))
        self._rows = _rows = tuple([Row(r, parent=self) for r in _data])
        self._height = _h = len(_rows)
        self._width = _w = max(len(r) for r in _rows) if _h > 0 else 0
        self._columns = zip(*_rows)
        # _holder = object()
        # _padded_rows = tuple(tuple(r) +
        #                      tuple((holder,) * (_w - len(r))) for r in _rows)

    def __iter__(self):
        return iter(self._rows)

    def __len__(self):
        return self._height

    def __unicode__(self):
        return self.recorddelimiter.join([unicode(s)
                                          for s in self._rows])

class Workbook(object):
    def __init__(self, data,
                 fielddelimiter=FIELDDELIMITER, recorddelimiter=RECORDDELIMITER,
                 prefix=u'', suffix=u''):

        _loc = locals()
        _kws = dict((k, _loc[k]) for k in
                   'fielddelimiter recorddelimiter prefix suffix'.split())
        for k, v in _kws.items(): setattr(self, k, v)

        assert isstring(data)

        _wss = xl.open_workbook(data).sheets()
        self._len = len(_wss)
        self._sheets = tuple([Worksheet(s, parent=self) for s in _wss])

        # if data is None:
        #     self._sheets = []
        #     return

        # # (ASPIRATIONAL)
        # _mksheet = ft.partial(Worksheet, parent=self, **_kws)
        # del _kws

        # _have_path = isstring(data)
        # if _have_path or isinstance(data, xlrd.Book):
        #     wb = xl.open_workbook(data) if _have_path else data
        #     sheets = [_mksheet(s) for s in wb.sheets()]
        # elif ismapping(data):
        #     sheets = [_mksheet(v, name=k) for k, v in data.items()]
        # elif isiterable(data):
        #     sheets = [_mksheet(s, name=i) for i, s in enumerte(data)]
        # else:
        #     raise TypeError('invalid type for data argument to %s constructor' %
        #                     type(self).__name__)

        # del _have_path, _mksheet

        # self._sheets = sheets

    def items(self):
        return tuple((s.name, s) for s in self._sheets)

    def __iter__(self):
        return iter(self._sheets)

    def __len__(self):
        return self._len

    nsheets = property(__len__)

    def write(self, path, worksheet_to_outpath=None):

        if worksheet_to_outpath is None:
            outdir = op.splitext(path)[0]
            def _ws2pth(sh):
                return op.join(outdir, '%s.csv' % sh.name)
            worksheet_to_outpath = _ws2pth

        for sh in self:
            outpath = worksheet_to_outpath(sh)
            _makedirs(op.dirname(outpath))
            with open(outpath, 'wb') as f:
                (csv.writer(f,
                            delimiter=self.fielddelimiter,
                            lineterminator=self.recorddelimiter)
                 .writerows(_tolist(sh)))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        xls2csv(p)



# CRUFT (SOON TO BE TOSSED)


# class Row(object):
#     def __init__(self, data=None
#                  fielddelimiter=FIELDDELIMITER, recorddelimiter=RECORDDELIMITER,
#                  prefix=u'', suffix=u''):

#         pass


# class Worksheet(object):
#     def __init__(self, data=None, name=None, parent=None,
#                  fielddelimiter=FIELDDELIMITER, recorddelimiter=RECORDDELIMITER,
#                  prefix=u'', suffix=u''):
        
#         _loc = locals()
#         _kws = dict((k, _loc[k]) for k in
#                     'parent fielddelimiter recorddelimiter prefix suffix'.split())
#         for k, v in _kws.items(): setattr(self, k, v)

#         if name is None:
#             if hasattr(data, 'name'):
#                 name = data.name
#             else:
#                 raise TypeError('No name for worksheet')
#         self.name = name
                 
#         if data is None:
#             _data = []
#         elif isinstance(data, xl.sheet.Sheet):
#             _data = (data.row_values(i) for i in range(data.nrows))
#         elif isiterable(data):
#             _data = data
#         else:
#             raise TypeError('invalid type for data argument to %s constructor' %
#                             type(self).__name__)

#         _kws.pop('parent')
#         self._rows = [Row(r, **_kws) for r in _data]


#     def __iter__(self):
#         return iter(self._rows)


# class Workbook(object):
#     def __init__(self, data=None,
#                  fielddelimiter=FIELDDELIMITER, recorddelimiter=RECORDDELIMITER,
#                  prefix=u'', suffix=u''):

#         _loc = locals()
#         _kws = dict((k, _loc[k]) for k in
#                    'fielddelimiter recorddelimiter prefix suffix'.split())
#         del _loc
#         for k, v in _kws.items(): setattr(self, k, v)

#         if data is None:
#             self._sheets = []
#             return

#         _mksheet = ft.partial(Worksheet, parent=self, **_kws)
#         del _kws

#         _have_path = isstring(data)
#         if _have_path or isinstance(data, xlrd.Book):
#             wb = xl.open_workbook(data) if _have_path else data
#             sheets = [_mksheet(s) for s in wb.sheets()]
#         elif isinstance(data, xlrd.Book):
#             sheets = [_mksheet
#         # # (ASPIRATIONAL)
#         # elif ismapping(data):
#         #     sheets = [_mksheet(v, name=k) for k, v in data.items()]
#         # elif isiterable(data):
#         #     sheets = [_mksheet(s, name=i) for i, s in enumerte(data)]
#         else:
#             raise TypeError('invalid type for data argument to %s constructor' %
#                             type(self).__name__)

#         del _have_path, _mksheet

#         self._sheets = sheets


# if __name__ == '__main__':
#     for p in sys.argv[1:]:
#         xls2csv(p)






# import sys
# import os
# import os.path as op
# import csv
# import re
# import errno as er
# import imp
# import platform as pl

# class _meta(type):
#     def __new__(mcls, name, bases, dct, _functype=type(lambda: 0)):
#         for k, v in dct.items():
#             if isinstance(v, _functype): dct[k] = classmethod(v)

#         return super(_meta, mcls).__new__(mcls, name, bases, dct)

#     def __call__(this, *args, **kwargs):
#         this.read(*args, **kwargs)

# class _x2py(object):
#     __metaclass__ = _meta

#     nsheets = lambda cl, wb: len(cl.sheets(wb))
#     def read(this, path):
#         for sh, data in xls2py(path).items():
#             pass

#     # def read(this, path, worksheet_to_outpath=None):
#     #     if worksheet_to_outpath is None:
#     #         outdir = op.splitext(path)[0]
#     #         def _ws2pth(sh):
#     #             return op.join(outdir, '%s.csv' % this.name(sh))
#     #         worksheet_to_outpath = _ws2pth

#     #     with this.open_wb(path) as wb:
#     #         for sh in this.sheets(wb):
#     #             outpath = worksheet_to_outpath(sh)
#     #             _makedirs(op.dirname(outpath))
#     #             with open(outpath, 'wb') as f:
#     #                 (csv.writer(f,
#     #                             delimiter=FIELDDELIMITER,
#     #                             lineterminator=RECORDDELIMITER)
#     #                  .writerows(this.rows(sh)))

#     def rows(this, sheet):
#         _rows = this._rows(sheet)

#         rown = 1
#         for row in _rows:
#             assert isinstance(row, list)
#             rown += 1
#             ncols = len(row)
#             if ncols:
#                 yield [_encode(value) for value in row]
#                 break
#             yield []
#         else:
#             return

#         the_sheet = "sheet '%s'" % this.name(sheet)
#         for row in _rows:
#             assert isinstance(row, list)
#             nc = len(row)
#             extra = ncols - nc
#             if extra < 0:
#                 raise ValueError('Too many columns in row %d of %s' %
#                                  (rown, the_sheet))

#             if extra:
#                 _warn('Only %d columns in row %d of %s (expected %d)' %
#                       (nc, rown, the_sheet, ncols))

#             rowlist = [_encode(value) for value in row]
                
#             yield rowlist + [''] * extra if extra else rowlist
#             rown += 1


# class _xls2py(_x2py):
#     name = lambda cl, sh: sh.name
#     sheets = lambda cl, wb: wb.sheets()

#     def _rows(this, sheet):
#         for i in range(sheet.nrows):
#             yield sheet.row_values(i)

#     import xlrd as xl
#     # NOTE: xlrd reads what may look like integers in the xlsx file as
#     # floats (e.g. a numeric value of 1 in the xls file will appear as
#     # 1.0 in the corresponding cell of the csv file).

#     def open_wb(this, path):
#         return this.xl.open_workbook(path)

# try:
#     imp.find_module('xlsxrd')
# except ImportError, e:
#     class _wbwrapper(object):
#         def __init__(self, wb): self.__dict__['_wb'] = wb
#         __enter__ = lambda s: s._wb
#         __exit__ = lambda *a: None
#         __getattr__ = lambda s, a: getattr(s._wb, a)
#         def __setattr__(self, attr, value): raise Exception, 'internal error'


#     class _xlsx2py(_x2py):
#         name = lambda cl, sh: sh.title
#         sheets = lambda cl, wb: wb.worksheets
#         def _rows(this, sheet):
#             for r in sheet.rows:
#                 yield [cell.value for cell in r]

#         def open_wb(this, path):
#             import openpyxl as xl
#             # NOTE: openpyxl renders (what may look like)
#             # "whole-number floats" (i.e. floats whose fractional part
#             # is zero) as integers (e.g. a numeric value that is
#             # displayed as 1.0 in the xlsx file will appear as 1 in
#             # the corresponding cell of the csv file); to put it
#             # differently, openpyxl preserves only non-zero fractional
#             # parts.
#             return _wbwrapper(xl.load_workbook(path))
# else:
#     class _xlsx2py(_xls2py): import xlsxrd as xl
#     # NOTE: xlsxrd reads what may look like integers in the xlsx file
#     # as floats (see note for xlrd above).

# # ------------------------------------------------------------

# def xls2py(path):
#     """
#     Convert xls file to DoL.

#     After
    
#     xls2csv('src/test/data/Protein_Profiling_Data.xls')

#     one gets:

#     src/test/data
#     ├── Protein_Profiling_Data
#     │   ├── All_pg-cell.csv
#     │   ├── All_pg-cell_noEpCAM.csv
#     │   ├── All_pg-cell_noSrc.csv
#     │   ├── pERK comparison_pg-ml.csv
#     │   ├── phospho_pg-cell.csv
#     │   ├── phospho_pg-ml.csv
#     │   ├── phospho updated 111213.csv
#     │   ├── total_pg-cell.csv
#     │   ├── total_pg-ml.csv
#     │   └── total updated 111213.csv
#     └── Protein_Profiling_Data.xls
#     """

#     orig_ext = op.splitext(path)[1][1:]
#     ext = orig_ext.lower()
#     if ext == 'xls':
#         read = _xls2csv
#     elif ext == 'xlsx':
#         read = _xlsx2csv
#     else:
#         raise ValueError, 'unsupported file type: %s' % orig_ext

#     return read(path)

# if __name__ == '__main__':

#     for p in sys.argv[1:]:
#         xls2csv(p)
