import inspect as ins
import sys
import os

_params= dict(
    SGDEBUG__ = False
)

def calling_frame(level=0):
    return ins.stack()[level+2][0]

def calling_module(level=0):
    return ins.getmodule(calling_frame(1))

def _setglobals(defaults, globs, fromenv,
                _environment=dict(os.environ)):
    globs.update(defaults)
    if not fromenv: return
    for key in defaults & _environment.viewkeys():
        val = unicode(_environment[key])
        globs[key] = val
        if SGDEBUG__:
            print (u'found: %s=%r' % (key, val)).encode('utf8')

def setglobals(defaults, globs=None, level=0):
    mod = calling_module()
    _setglobals(defaults,
                vars(mod) if globs is None else globs,
                mod.__name__ == '__main__')

_setglobals(_params, globals(), True)
del _params
