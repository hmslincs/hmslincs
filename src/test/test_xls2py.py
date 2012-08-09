# -*- coding: utf-8 -*-
import os
import os.path as op
import shutil as shu
import errno as er
import unittest as ut


MODNAME = 'xls2py'
MOD = __import__(MODNAME)
DATADIR, SCRATCHDIR = [op.join(op.dirname(__file__), d, MODNAME)
                       for d in 'data scratch'.split()]
FIXTURES = dict((n, op.join(DATADIR, '%s.xls' % n)) for n in
                'blank ones happypath'.split())


def _tree(path, level=0, indent='    '):
    if level == 0:
        print '\n%s' % path
    else:
        print '%s%s' % (indent * level, op.basename(path))

    try:
        level += 1
        for sub in os.listdir(path):
            _tree(op.join(path, sub), level)
    except Exception, e:
        if e.errno != er.ENOTDIR:
            raise


class Test_xls2py(ut.TestCase):

    def test_workbook_compiles(self):
        ignore = MOD.Workbook(FIXTURES['blank'])

class Test_blank(ut.TestCase):
    _path = FIXTURES['blank']

    def test_blank__len(self, _path=_path):
        wb = MOD.Workbook(_path)
        self.assertEqual(len(wb), 0)

    def test_blank__keep_empty(self, _path=_path):
        wb = MOD.Workbook(_path, keep_empty=True)
        self.assertEqual([len(sh) for sh in wb], [0, 0, 0])
        self.assertEqual([sh.name for sh in wb],
                         ['Sheet%d' % (i + 1) for i in range(3)])


class Test_happypath(ut.TestCase):
    HP_PATH = op.join(SCRATCHDIR, 'happypath')

    def setUp(self):
        self._wb = MOD.Workbook(FIXTURES['happypath'])

    def tearDown(self):
        try:
            shu.rmtree(self.HP_PATH)
        except Exception, e:
            if e.errno != er.ENOENT:
                raise
    
    def test_happypath__len(self):
        wb = self._wb
        self.assertEqual(wb._len, wb.nsheets)
        self.assertEqual(len(wb), wb.nsheets)
        for sh in wb:
            self.assertEqual(sh._len, sh.nrows)
            self.assertEqual(len(sh), sh.nrows)
            for ro in sh:
                self.assertEqual(ro._len, ro.ncells)
                self.assertEqual(len(ro), ro.ncells)

    def test_happypath__table(self):
        wb = self._wb
        for sh in wb:
            hdrs = sh[0]
            trs = sh[1:]
            ta = MOD.Table(trs, hdrs, **sh._format)

    def test_happypath__enum(self):
        wb = self._wb
        nsheets = wb.nsheets
        for i, sheet in enumerate(wb):
            nrows = sheet.nrows
            for j, row in enumerate(sheet):
                if nsheets - i == 1 and nrows - j == 1:
                    self.assertEqual(str(row), '1088.8,1.0')

    def test_happypath__wb_getitem(self):
        wb = self._wb
        firstsheet = wb[0]
        self.assertEqual(firstsheet.name, u'First')
        lastsheet = wb[-1]
        self.assertEqual(lastsheet.name, u'iv')
        middlesheets = wb[1:-1]
        self.assertEqual([s.name for s in middlesheets], u'2nd Tres'.split())
        for sh in wb:
            self.assertEqual(sh, wb[sh.name])

    def test_happypath__wb_getitem(self):
        wb = self._wb

        for i, sh in enumerate(wb):
            self.assertEqual(wb[i], sh)
            for j, ro in enumerate(sh):
                self.assertEqual(sh[j], ro)
                for k, ce in enumerate(ro):
                    self.assertEqual(ro[k], ce)

        self.assertEqual(wb[0].name, u'First')
        self.assertEqual(wb[-1].name, u'iv')
        self.assertEqual([s.name for s in wb[1:-1]], u'2nd Tres'.split())

        for sh in wb:
            self.assertEqual(sh, wb[sh.name])

    def test_happypath__index(self):
        wb = self._wb
        for i, sh in enumerate(wb):
            self.assertEqual(i, wb.index(sh.name))

    def test_happypath__contains(self):
        wb = self._wb
        for sh in wb:
            self.assertTrue(sh.name in wb)

    def test_happypath__items(self):
        wb = self._wb
        for k, sheet in wb.items():
            self.assertEqual(k, sheet.name)

    def test_happypath__colindexing(self):
        def _test_ta(sh, ta):
            self.assertEquals(sh.nrows - 1, ta.nrows)
            hdrs = ta._labels
            self.assertEquals(sh[0], hdrs)
            for ro in ta:
                for i, hdr in enumerate(hdrs):
                    self.assertEqual(ro[i], ro[hdr])

        first, rest = 0, slice(1, None)
        for sh in self._wb:
            for ta in (MOD.Table(sh[rest], sh[first], **sh._format),
                       sh.as_table(rest, first), sh.as_table()):
                _test_ta(sh, ta)
                

    def test_happypath__write(self):
        wb = self._wb
        hpp = self.HP_PATH
        wb.write(hpp)
        expected = """
COUNTRY,AGE,WEIGHT,DOB
Zimbabwe,31.0,65.5,1/2/1990
Bolivia,12.0,33.7,3/5/1989
Canada,45.0,71.1,8/10/2001
Myanmar,77.0,58.48,12/12/1935
New Zealand,28.0,84.001,11/13/1950
INT,FLOAT,STRING,DATE,BOOLEAN
3.0,0.5,spam,1/1/2012,Y
1.0,3.3,ham,7/31/1999,N
4.0,0.1,eggs,12/10/1985,Y
1.0,0.002,foo,11/21/1963,Y
TIME,CONCENTRATION,NAME
10.0,0.1,ABC
0.0,0.01,DEF-1
60.0,0.001,GHIJ.2
90.0,1.1,LM_3
120.0,1.01,NOPqr/4
150.0,1.001,"s+T,Uv"
180.0,10.1,W~x.yZ
readout,YN
0.1,0.0
2.3,0.0
45.6,1.0
789.1,0.0
1.2,1.0
22.3,1.0
1088.8,1.0
""".lstrip()

        got = ''
        for bn in sorted(os.listdir(hpp)):
            got += open(op.join(hpp, bn)).read()
        self.assertEqual(expected, got)
                            
if __name__ == "__main__":
    import test.test_support as ts
    ts.run_unittest(Test_xls2py)
    ts.run_unittest(Test_blank)
    ts.run_unittest(Test_happypath)
