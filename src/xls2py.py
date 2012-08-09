# -*- coding: utf-8 -*-
import xlrd as xl
import os
import os.path as op
import errno as er
import csv
import platform as pl
import functools as ft

from typecheck import isstring, issequence

# ---------------------------------------------------------------------------
import setglobals as _sg
_params = dict(
    FIELDDELIMITER = u',',
    RECORDDELIMITER = u'\r\n' if pl.system == 'Windows' else u'\n',
    PREFIX = u'',
    SUFFIX = u'',
    PROLOGUE = u'',
    EPILOGUE = u'',
    VERBOSE = False,
    ENCODING = u'utf8',
)
_sg.setglobals(_params)
del _sg, _params

# ---------------------------------------------------------------------------
assert len(FIELDDELIMITER) > 0
assert len(RECORDDELIMITER) > 0

FIELDDELIMITER = FIELDDELIMITER.encode(ENCODING)
RECORDDELIMITER = RECORDDELIMITER.encode(ENCODING)

assert RECORDDELIMITER != FIELDDELIMITER

# ---------------------------------------------------------------------------

def _tolist(x):
    return [_tolist(i) for i in x] if issequence(x) else x

def _makedirs(path):
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != er.EEXIST: raise

def _subdict(d, keys):
    return dict((k, d[k]) for k in keys)

# ---------------------------------------------------------------------------

class _encodable(object):
    def __str__(self):
        return self.__unicode__().encode(ENCODING)

class _sequence(object):
    def __len__(self):
        return len(self._seq)

    _len = property(__len__)

    def __getitem__(self, index):
        return self._seq[index]

    def index(self, value):
        return index(self._seq, value)

    def __iter__(self):
        return iter(self._seq)

class _labeled_sequence(_sequence):
    def _toindex(self, ii):
        def __2i(i, seq=self._seq, lkp=self._label_2_index):
            try: seq[i:i]
            except TypeError, e:
                if not ('slice indices must be integers or None or have an '
                        '__index__ method' in str(e)): raise
                return lkp[i]
            else:
                return i
                    
        if isinstance(ii, slice):
            args = [__2i(i) for i in (ii.start, ii.stop)] + [ii.step]
            return slice(*args)

        return __2i(ii)

    def __getitem__(self, index_or_key):
        return self._seq[self._toindex(index_or_key)]

    # Note: the definition of index below has different *semantics* from
    # that of, e.g., list.index, and of _sequence.index for that matter.
    def index(self, label):
        return self._label_2_index[label]

    def __contains__(self, label):
        return label in self._label_2_index


# ---------------------------------------------------------------------------

class Cell(_encodable):
    def __init__(self, data, parent):
        self._value = data

    def __unicode__(self):
        return unicode(self._value)


class Row(_encodable, _sequence):
    _FORMATTING_ATTRS = tuple('fielddelimiter prefix suffix'.split())

    def __init__(self, data, parent, labels=None):
        self.__dict__.update(_subdict(parent.__dict__, self._FORMATTING_ATTRS))
        self.parent = parent
        self._cells = cols = tuple([Cell(c, parent=self) for c in data])

    _seq = property(lambda s: s._cells) # (See comments on Workbook._seq below.)
    ncells = _sequence._len

    def __unicode__(self):
        body = self.fielddelimiter.join([unicode(s) for s in self._cells])
        return '%s%s%s' % (self.prefix, body, self.suffix)


class Record(Row, _labeled_sequence):
    def __init__(self, data, parent, labels=None):
        super(Record, self).__init__(data, parent=parent)
        self._label_2_index = (dict() if labels is None else
                               dict((v, i) for i, v in enumerate(labels)))


class _Sequence_of_sequences(_encodable, _sequence):
    _FORMATTING_ATTRS = (Row._FORMATTING_ATTRS +
                         tuple('recorddelimiter prologue epilogue'.split()))

    def __init__(self, data=None,
                 fielddelimiter=FIELDDELIMITER,
                 recorddelimiter=RECORDDELIMITER,
                 prefix=PREFIX, suffix=SUFFIX,
                 prologue=PROLOGUE, epilogue=EPILOGUE):

        self._format = _subdict(locals(), self._FORMATTING_ATTRS)
        self.__dict__.update(self._format)

        self._rows = rows = self._makerows(data)
        _h = len(rows)
        self._width = _w = max(len(r) for r in rows) if _h > 0 else 0


    _seq = property(lambda s: s._rows) # (See comments on Workbook._seq below.)
    _columns = property(lambda s: zip(*s._rows))
    nrows = _sequence._len        

    def __unicode__(self):
        body = self.recorddelimiter.join([unicode(s) for s in self._rows])
        return '%s%s%s' % (self.prologue, body, self.epilogue)


class Worksheet(_Sequence_of_sequences):
    def __init__(self, data, parent, name=None):
        if name is None:
            if hasattr(data, 'name'):
                name = data.name
            else:
                raise TypeError('No name for worksheet')

        self.name = name

        assert isinstance(data, xl.sheet.Sheet)
        _data = (data.row_values(i) for i in range(data.nrows))

        fmt = _subdict(parent.__dict__, self._FORMATTING_ATTRS)
        super(Worksheet, self).__init__(data=_data, **fmt)

    def _makerows(self, data):
        return tuple([Row(r, parent=self) for r in data])

    def as_table(self, dataslice=slice(1, None), header_row_num=0,
                 formatting=None):
        header_row = None if header_row_num is None else self[header_row_num]
        if formatting is None:
            formatting = self._format
        return Table(self[dataslice], header_row, **formatting)


class Table(_Sequence_of_sequences, _labeled_sequence):
    def __init__(self, data=None, labels=None,
                 fielddelimiter=FIELDDELIMITER,
                 recorddelimiter=RECORDDELIMITER,
                 prefix=PREFIX, suffix=SUFFIX,
                 prologue=PROLOGUE, epilogue=EPILOGUE):
        self._labels = labels
        fmt = _subdict(locals(), self._FORMATTING_ATTRS)
        super(Table, self).__init__(data, **fmt)
    
    def _makerows(self, data):
        return tuple([Record(r, parent=self, labels=self._labels) for r in data])


class Workbook(_labeled_sequence):
    def __init__(self, data,
                 fielddelimiter=FIELDDELIMITER,
                 recorddelimiter=RECORDDELIMITER,
                 prefix=PREFIX, suffix=SUFFIX,
                 prologue=PROLOGUE, epilogue=EPILOGUE,
                 keep_empty=False):

        self.__dict__.update(_subdict(locals(), Worksheet._FORMATTING_ATTRS))

        assert isstring(data)
        self._path = _path = data

        _all = xl.open_workbook(_path).sheets()
        wss = _all if keep_empty else [sh for sh in _all if sh.nrows > 0]

        self._sheets = sheets = tuple([Worksheet(s, parent=self) for s in wss])
        names = [sh.name for sh in sheets]
        self._label_2_index = dict((v, i) for i, v in enumerate(names))

    # The rationale for the perverse-looking assignment below (rather
    # than simply set _seq = self._sheets in __init__) is to keep _seq
    # in sync with self._sheets.
    _seq = property(lambda s: s._sheets)
    nsheets = _labeled_sequence._len

    def items(self):
        return tuple((s.name, s) for s in self._sheets)

    def write(self, outdir=None, worksheet_to_outpath=None):

        if outdir is None:
            outdir = op.splitext(self._path)[0]

        if worksheet_to_outpath is None:
            def _ws2pth(sh):
                return op.join(outdir, '%s.csv' % sh.name)
            worksheet_to_outpath = _ws2pth

        _wrtr = ft.partial(csv.writer,
                           delimiter=self.fielddelimiter,
                           lineterminator=self.recorddelimiter)
        for sh in self:
            outpath = worksheet_to_outpath(sh)
            _makedirs(op.dirname(outpath))
            with open(outpath, 'wb') as f:
                _wrtr(f).writerows(_tolist(sh))


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        Workbook(p).write()
