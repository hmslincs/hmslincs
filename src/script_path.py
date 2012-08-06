import sys
import os.path as op

def script_path(argv=None):
    """Get absolute path to current script.

    Returns None if python was invoked with the '-c' flag, or if running under
    the standard python shell.
    """

    if argv is None: argv = sys.argv
    if argv:
        sc = argv[0]
        if sc and sc != '-c':
            return op.abspath(argv[0])

def script_dir(argv=None):
    """Get absolute path to directory of current script.

    Returns None whenever script_path (q.v.) returns None.
    """

    path = script_path(argv)
    if path is not None:
        return op.dirname(path)


def script_name(argv=None):
    """Get name of current script.

    Returns None whenever script_path (q.v.) returns None.
    """

    path = script_path(argv)
    if path is not None:
        return op.basename(path)

if __name__ == '__main__':
    this = op.abspath(__file__)
    assert this == script_path()
    assert op.dirname(this) == script_dir()
    assert script_path([]) is script_path(['']) is script_path(['-c']) is None
    assert script_dir([]) is script_dir(['']) is script_dir(['-c']) is None
