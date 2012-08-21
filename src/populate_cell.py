import sys
import init_utils as iu

# ---------------------------------------------------------------------------

import setparams as _sg
_params = dict(
    VERBOSE = False,
    APPNAME = 'example',
)
_sg.setparams(_params)
del _sg, _params

# ---------------------------------------------------------------------------


class populate_cell(iu.populate_from_xls):
    def _init(this, path, sheetname, headers=1):
        super(populate_cell, this)._init(APPNAME, 'Cell',
                                         path=path, sheetname=sheetname,
                                         headers=headers)
        return this

def main(argv=sys.argv[1:]):
    assert 2 <= len(argv) <= 3
    populate_cell(*argv)


if __name__ == '__main__':
    main()
