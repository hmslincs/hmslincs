import inspect as ins
import sys
import os

import chdir as cd

_params= dict(
    SGDEBUG__ = False
)

def _getiwd():
    return os.environ['PWD']    # yes, this is totally lame

def calling_module(level=0):
    with cd.chdir(_getiwd()):
        return(ins.getmodule(ins.currentframe(level+2)))

def _setparams(defaults, globs, fromenv,
               _environment=dict(os.environ)):
    globs.update(defaults)
    if not fromenv: return
    for key in defaults & _environment.viewkeys():
        val = unicode(_environment[key])
        globs[key] = val
        if SGDEBUG__:
            print (u'found: %s=%r' % (key, val)).encode('utf8')

def setparams(defaults, globs=None, level=0):
    mod = calling_module()
    _setparams(defaults,
                vars(mod) if globs is None else globs,
                mod.__name__ == '__main__')

_setparams(_params, globals(), True)
del _params
