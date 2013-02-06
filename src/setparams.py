import inspect as ins
import sys
import os

_params= dict(
    SGDEBUG__ = False
)

def _setparams(defaults, globs, fromenv, _environment=dict(os.environ)):
    globs.update(defaults)
    if not fromenv: return
    for key in defaults & _environment.viewkeys():
        val = unicode(_environment[key])
        globs[key] = val
        if SGDEBUG__:
            print (u'found: %s=%r' % (key, val)).encode('utf8')

def setparams(defaults, globs=None, level=0):
    callers_globs = ins.currentframe(level+1).f_globals
    _setparams(defaults,
               callers_globs if globs is None else globs,
               callers_globs['__name__'] == '__main__')

_setparams(_params, globals(), True)
del _params
