import inspect as ins
import sys
import os

_params= dict(
    SGDEBUG__ = False
)

def calling_module(level=1, _mods=sys.modules, _main=sys.modules['__main__']):
    st = ins.stack()
    # frame, filename, line_num, func, source_code, source_index = st[level]
    filename = st[level][1]
    modulename = ins.getmodulename(filename)
    try:
        return _mods[modulename]
    except KeyError, e:
        assert _main.__file__ == filename
        return _main

def _setglobals(defaults, globs, fromenv,
                _environment=dict(os.environ)):
    globs.update(defaults)
    if not fromenv: return
    for key in defaults & _environment.viewkeys():
        val = unicode(_environment[key])
        globs[key] = val
        if SGDEBUG__:
            print (u'found: %s=%r' % (key, val)).encode('utf8')

def setglobals(defaults, globs=None, level=1):
    mod = calling_module(level + 1)
    _setglobals(defaults,
                vars(mod) if globs is None else globs,
                mod.__name__ == '__main__')

_setglobals(_params, globals(), True)
del _params
