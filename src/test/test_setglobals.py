# -*- coding: utf-8 -*-
import os.path as op
import sys
import os
import inspect as ins
import unittest as ut

ENVIRON = os.environ
ORIG_ENVIRON = dict(ENVIRON)
TEST_PARAM_NAME = 'TEST_TESTGLOBALS_PY__PARAM'

SCRIPTDIR = op.dirname(__file__)
sys.path.insert(0, op.join(SCRIPTDIR, 'src'))
MODNAME = 'setglobals'

def run():
    import test.test_support as ts
    ts.run_unittest(Test_setglobals)
class Test_setglobals(ut.TestCase):
#     pass
# def run():
#     Test_setglobals().test_script_case()
# class Test_setglobals(object):
#     def assertTrue(self, val):
#         assert val
#     def assertEquals(self, x, y):
#         assert x == y

    globs = globals()
    sysmodmain = sys.modules['__main__']
    orig_name = sysmodmain.__name__

    def setUp(self):
        ENVIRON[TEST_PARAM_NAME] = 'set through environment'
        sys.modules.pop(MODNAME, None)
        self.globs.pop(TEST_PARAM_NAME, None)
        self.params = {TEST_PARAM_NAME: u'default value'}

    def tearDown(self):
        ENVIRON.pop(TEST_PARAM_NAME, None)
        self.sysmodmain.__name__ = self.orig_name
        sys.modules.pop(MODNAME, None)

    def test_no_defaults(self):
        self.assertTrue(not TEST_PARAM_NAME in self.globs)

        mod = __import__(MODNAME)
        mod.setglobals({})

        self.assertTrue(not TEST_PARAM_NAME in self.globs)

    def test_no_environment(self):
        self.assertTrue(not TEST_PARAM_NAME in self.globs)

        ENVIRON.pop(TEST_PARAM_NAME, None)
        mod = __import__(MODNAME)
        mod.setglobals(self.params)

        self.assertTrue(TEST_PARAM_NAME in self.globs)
        self.assertEquals(self.globs[TEST_PARAM_NAME],
                          self.params[TEST_PARAM_NAME])

    def test_script_case(self):
        self.assertTrue(not TEST_PARAM_NAME in self.globs)

        mod = __import__(MODNAME)
        mod.setglobals(self.params)
        self.assertTrue(TEST_PARAM_NAME in self.globs)
        self.assertEquals(self.globs[TEST_PARAM_NAME],
                          ENVIRON[TEST_PARAM_NAME])

    def test_module_case(self):
        self.assertTrue(not TEST_PARAM_NAME in self.globs)
        self.sysmodmain.__name__ = ins.getmodulename(__file__)
        mod = __import__(MODNAME)
        mod.setglobals(self.params)
        self.assertTrue(TEST_PARAM_NAME in self.globs)
        self.assertEquals(self.globs[TEST_PARAM_NAME],
                          self.params[TEST_PARAM_NAME])
                            
if __name__ == "__main__":
    run()
