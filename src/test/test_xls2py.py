# -*- coding: utf-8 -*-
import unittest as ut
import test.test_support as ts
import xlrd as xl

import os
import os.path as op
import script_path as sp
import shutil as sh
import errno as er


MODNAME = 'xls2py'
MOD = __import__(MODNAME)
DATADIR, SCRATCHDIR = [op.join(sp.script_dir(), d, MODNAME)
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


class Test_happypath(ut.TestCase):
    HP_PATH = op.join(SCRATCHDIR, 'happypath')

    def setUp(self):
        self._wb = MOD.Workbook(FIXTURES['happypath'])

    def tearDown(self):
        try:
            sh.rmtree(self.HP_PATH)
        except Exception, e:
            if e.errno != er.ENOENT:
                raise
    
    def test_happypath__enum(self):
        wb = self._wb
        nsheets = len(wb)
        for i, sheet in enumerate(wb):
            nrows = len(sheet)
            for j, row in enumerate(sheet):
                if nsheets - i == 1 and nrows - j == 1:
                    self.assertEqual(str(row), '1088.8,1.0')

    def test_happypath__items(self):
        wb = self._wb
        for k, sheet in wb.items():
            self.assertEqual(k, sheet.name)

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
    ts.run_unittest(Test_xls2py)
    ts.run_unittest(Test_happypath)
