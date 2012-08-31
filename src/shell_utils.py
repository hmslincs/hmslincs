from subprocess import check_output, STDOUT as sp_STDOUT
from subprocess import Popen, PIPE
import os
from os import environ, access, X_OK
from os.path import join as opjoin, exists

import errno as er

def _runcmd(cmd, dryrun):
    if dryrun:
        print ' '.join(cmd)
        return
    else:
        output = check_output(cmd, stderr=sp_STDOUT)
        if output:
            raise OSError(output)


def _find_cmd(name):
    for p in environ.get('PATH', '').split(':'):
        path = opjoin(p, name)
        if access(path, X_OK):
            return path
    raise ValueError('cannot find %s' % name)
    
    
def rmrf(path, dryrun=False):
    _runcmd([_find_cmd('rm'), '-r', '-f', path], dryrun)


# def mkdirp(path, dryrun=False):
#     _runcmd([_find_cmd('mkdir'), '-p', path], dryrun)

def mkdirp(path):
    try:
        os.makedirs(path)

    except OSError, e:
        if e.errno != er.EEXIST: raise


def cmd_with_output(cmd, *args, **kwargs):
    fail_on_error = kwargs.pop('fail_on_error', True)
    split_lines = kwargs.pop('split_lines', True)
    badkwargs = kwargs.keys()
    if badkwargs:
        raise TypeError('unsupported parameters: %s' % ', '.join(badkwargs))

    out = None
    try:
        out, err = Popen([_find_cmd(cmd)] + list(args),
                         stdout=PIPE, stderr=PIPE).communicate()
        if err:
            if fail_on_error:
                raise SystemError(err)
        else:
            return out.splitlines() if split_lines else out
    except Exception, e:
        if fail_on_error:
            raise
        else:
            err = '%s: %s' % (type(e).__name__, e)

    assert not fail_on_error
    return out, err

def firstline(path):
    (line, err) = Popen([_find_cmd('head'), '-1', path],
                        stdout=PIPE, stderr=PIPE).communicate()
    if err:
        raise SystemError(err)
    elif not line:
        raise SystemError("could not read first line of " + path)
    return line

def _id(arg, user=None):
    if user is None:
        ret = arg()
    else:
        (out, err) = Popen([_find_cmd('id'), arg, user],
                           stdout=PIPE, stderr=PIPE).communicate()
        if err: raise SystemError(err.strip())
        ret = int(out)
    return ret

def uid(user=None):
    arg = os.getuid if user is None else '-r'
    return _id(arg, user)

def euid(user=None):
    arg = os.geteuid if user is None else '-u'
    return _id(arg, user)

def gid(user=None):
    arg = os.getgid if user is None else '-g'
    return _id(arg, user)
